from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from recommendation_engine import build_engine_config
from roadmap_core import build_roadmap, load_answers, save_txt


HORIZON_ORDER = ["Corto plazo", "Mediano plazo", "Largo plazo", "Sin clasificar"]


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip().lower()


def _canonical_horizon(value: object) -> str:
    key = _norm(value)
    if "corto" in key:
        return "Corto plazo"
    if "mediano" in key:
        return "Mediano plazo"
    if "largo" in key:
        return "Largo plazo"
    return "Sin clasificar"


def _safe_case_id(value: object, fallback: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9_-]+", "-", _norm(value))
    clean = raw.strip("-")
    return clean or fallback


def _normalize_answers(raw: object) -> dict[int, int] | list[int]:
    if isinstance(raw, list):
        return [int(x) for x in raw]
    if isinstance(raw, dict):
        if "answers" in raw:
            return _normalize_answers(raw["answers"])
        return {int(k): int(v) for k, v in raw.items()}
    raise RuntimeError("Formato de respuestas no soportado en caso piloto.")


def _load_case_answers(case: dict[str, Any], root: Path) -> dict[int, int] | list[int]:
    if "answers" in case:
        return _normalize_answers(case["answers"])
    answers_file = case.get("answers_file")
    if not answers_file:
        raise RuntimeError("El caso no incluye 'answers' ni 'answers_file'.")
    answers_path = Path(str(answers_file))
    if not answers_path.is_absolute():
        answers_path = root / answers_path
    if not answers_path.exists():
        raise RuntimeError(f"No existe answers_file: {answers_path}")
    return load_answers(answers_path)


def _horizon_distribution(entries: list[dict[str, object]]) -> dict[str, int]:
    counts = {h: 0 for h in HORIZON_ORDER}
    for row in entries:
        horizon = _canonical_horizon(row.get("plazo", ""))
        counts[horizon] = counts.get(horizon, 0) + 1
    return counts


def _merge_overrides(global_overrides: dict[str, Any], case_overrides: object) -> dict[str, Any]:
    merged = dict(global_overrides)
    if isinstance(case_overrides, dict):
        for key, value in case_overrides.items():
            if value is not None:
                merged[str(key)] = value
    return merged


def _render_summary_txt(report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("PILOTO ROADMAP - RESUMEN")
    lines.append("")
    lines.append(f"Generado: {report.get('generated_at', '')}")
    lines.append(f"Total casos: {report.get('total_cases', 0)}")
    lines.append(f"Exitosos: {report.get('success_cases', 0)}")
    lines.append(f"Fallidos: {report.get('failed_cases', 0)}")
    lines.append(f"Promedio acciones: {report.get('avg_actions', 0)}")
    lines.append(f"Promedio score actual: {report.get('avg_current_score', 0)}")
    lines.append(f"Promedio score objetivo: {report.get('avg_target_score', 0)}")
    lines.append(f"Presupuesto total usado (CLP): {report.get('sum_budget_used_clp', 0)}")
    lines.append("")
    lines.append("Detalle por caso:")
    for case in report.get("cases", []):
        row = case if isinstance(case, dict) else {}
        lines.append(
            f"- {row.get('case_id','')} | estado={row.get('status','')} | "
            f"empresa={row.get('company_name','')} | acciones={row.get('actions',0)} | "
            f"presupuesto={row.get('budget_used_clp',0)}"
        )
        if row.get("status") != "ok" and row.get("error"):
            lines.append(f"  error: {row.get('error')}")
    lines.append("")
    return "\n".join(lines)


def _aggregate_results(rows: list[dict[str, object]]) -> dict[str, object]:
    success_rows = [r for r in rows if r.get("status") == "ok"]
    total_cases = len(rows)
    success_cases = len(success_rows)
    failed_cases = total_cases - success_cases
    if success_rows:
        avg_actions = round(sum(float(r.get("actions", 0) or 0) for r in success_rows) / len(success_rows), 2)
        avg_current = round(sum(float(r.get("current_score", 0) or 0) for r in success_rows) / len(success_rows), 4)
        avg_target = round(sum(float(r.get("target_score", 0) or 0) for r in success_rows) / len(success_rows), 4)
        budget_sum = round(sum(float(r.get("budget_used_clp", 0) or 0) for r in success_rows), 2)
    else:
        avg_actions = 0.0
        avg_current = 0.0
        avg_target = 0.0
        budget_sum = 0.0

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_cases": total_cases,
        "success_cases": success_cases,
        "failed_cases": failed_cases,
        "avg_actions": avg_actions,
        "avg_current_score": avg_current,
        "avg_target_score": avg_target,
        "sum_budget_used_clp": budget_sum,
        "cases": rows,
    }


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejecucion batch de piloto (3-5 casos reales)")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--cases-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--engine-config-file", type=Path, default=None)
    parser.add_argument("--strict-catalog", action="store_true")
    parser.add_argument("--with-pdf", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--budget-total-clp", type=float, default=None)
    parser.add_argument("--budget-short-clp", type=float, default=None)
    parser.add_argument("--budget-medium-clp", type=float, default=None)
    parser.add_argument("--budget-long-clp", type=float, default=None)
    parser.add_argument("--max-recommendations", type=int, default=None)
    parser.add_argument("--max-per-provider", type=int, default=None)
    parser.add_argument("--max-per-kpi", type=int, default=None)
    parser.add_argument("--max-candidates-per-kpi", type=int, default=None)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    cases_path = args.cases_file.resolve() if args.cases_file.is_absolute() else (root / args.cases_file).resolve()
    out_dir = args.output_dir.resolve() if args.output_dir is not None else (root / "outputs" / "pilot")
    engine_config_file = args.engine_config_file.resolve() if args.engine_config_file is not None else None

    if not cases_path.exists():
        raise RuntimeError(f"No existe archivo de casos: {cases_path}")

    payload = json.loads(cases_path.read_text(encoding="utf-8"))
    cases_raw = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(cases_raw, list) or not cases_raw:
        raise RuntimeError("El archivo de casos debe contener una lista o un objeto con 'cases'.")

    out_dir.mkdir(parents=True, exist_ok=True)

    global_overrides = {
        "budget_total_clp": args.budget_total_clp,
        "budget_short_clp": args.budget_short_clp,
        "budget_medium_clp": args.budget_medium_clp,
        "budget_long_clp": args.budget_long_clp,
        "max_recommendations": args.max_recommendations,
        "max_per_provider": args.max_per_provider,
        "max_per_kpi": args.max_per_kpi,
        "max_candidates_per_kpi": args.max_candidates_per_kpi,
    }

    if args.with_pdf:
        from pdf_export import export_friendly_pdf, export_technical_pdf

    case_results: list[dict[str, object]] = []
    for idx, raw_case in enumerate(cases_raw, start=1):
        if not isinstance(raw_case, dict):
            case_results.append(
                {
                    "case_id": f"case_{idx}",
                    "status": "error",
                    "error": "Caso invalido: se esperaba objeto JSON.",
                }
            )
            if args.fail_fast:
                break
            continue

        case_id = _safe_case_id(raw_case.get("case_id"), f"case_{idx}")
        try:
            company_type = str(raw_case.get("company_type", "")).strip().lower()
            if company_type not in {"small", "medium"}:
                raise RuntimeError("company_type debe ser 'small' o 'medium'.")

            answers = _load_case_answers(raw_case, root)
            target_level = int(raw_case.get("target_level", 3))
            company_name = str(raw_case.get("company_name", f"Piloto {case_id}"))
            company_rut = str(raw_case.get("company_rut", ""))
            company_email = str(raw_case.get("company_email", ""))

            engine_cfg = build_engine_config(
                engine_config_file,
                _merge_overrides(global_overrides, raw_case.get("engine_overrides")),
            )

            result_payload = build_roadmap(
                root=root,
                company_type=company_type,
                answers=answers,
                target_level=target_level,
                company_name=company_name,
                company_rut=company_rut,
                company_email=company_email,
                engine_cfg=engine_cfg,
            )

            result = result_payload.get("result", {})
            catalog = result.get("catalog_summary", {}) if isinstance(result, dict) else {}
            if args.strict_catalog and int(catalog.get("error_count", 0)) > 0:
                raise RuntimeError(f"Catalogo invalido ({catalog.get('error_count', 0)} errores).")

            out_json = out_dir / f"{case_id}_result.json"
            out_txt = out_dir / f"{case_id}_result.txt"
            out_json.write_text(json.dumps(result_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            save_txt(result_payload, out_txt)

            generated_files = [str(out_json), str(out_txt)]
            if args.with_pdf:
                out_pdf_tech = out_dir / f"{case_id}_tecnico.pdf"
                out_pdf_friendly = out_dir / f"{case_id}_amigable.pdf"
                export_technical_pdf(result_payload, out_pdf_tech)
                export_friendly_pdf(result_payload, out_pdf_friendly)
                generated_files.extend([str(out_pdf_tech), str(out_pdf_friendly)])

            entries = result.get("roadmap_entries", []) if isinstance(result, dict) else []
            eng = result.get("engine_summary", {}) if isinstance(result, dict) else {}
            horizon_dist = _horizon_distribution(entries if isinstance(entries, list) else [])
            case_results.append(
                {
                    "case_id": case_id,
                    "status": "ok",
                    "company_name": company_name,
                    "company_type": company_type,
                    "target_level": target_level,
                    "current_score": result.get("current_score", 0),
                    "target_score": result.get("target_score", 0),
                    "kpi_gaps": len(result.get("kpi_results", [])),
                    "actions": len(entries if isinstance(entries, list) else []),
                    "budget_used_clp": eng.get("used_budget_total_clp", 0),
                    "catalog_errors": catalog.get("error_count", 0),
                    "catalog_warnings": catalog.get("warning_count", 0),
                    "short_actions": horizon_dist.get("Corto plazo", 0),
                    "medium_actions": horizon_dist.get("Mediano plazo", 0),
                    "long_actions": horizon_dist.get("Largo plazo", 0),
                    "generated_files": generated_files,
                }
            )
            print(f"[REL-02] Caso {case_id}: OK (acciones={len(entries)}, presupuesto={eng.get('used_budget_total_clp', 0)})")
        except Exception as exc:
            case_results.append(
                {
                    "case_id": case_id,
                    "status": "error",
                    "company_name": str(raw_case.get("company_name", "")),
                    "error": str(exc),
                }
            )
            print(f"[REL-02] Caso {case_id}: ERROR -> {exc}")
            if args.fail_fast:
                break

    report = _aggregate_results(case_results)
    summary_json = out_dir / "pilot_summary.json"
    summary_txt = out_dir / "pilot_summary.txt"
    summary_csv = out_dir / "pilot_summary.csv"
    summary_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_txt.write_text(_render_summary_txt(report), encoding="utf-8")

    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "status",
                "company_name",
                "company_type",
                "target_level",
                "current_score",
                "target_score",
                "kpi_gaps",
                "actions",
                "short_actions",
                "medium_actions",
                "long_actions",
                "budget_used_clp",
                "catalog_errors",
                "catalog_warnings",
                "error",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in case_results:
            writer.writerow(row)

    print(f"[REL-02] Resumen JSON: {summary_json}")
    print(f"[REL-02] Resumen TXT: {summary_txt}")
    print(f"[REL-02] Resumen CSV: {summary_csv}")
    return 0 if int(report.get("failed_cases", 0)) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(cli())
