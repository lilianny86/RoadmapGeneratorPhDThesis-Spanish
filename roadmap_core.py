from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from catalog_quality import build_catalog_v3, catalog_report_to_text
from en_localization import (
    localize_domain,
    localize_kda,
    localize_kpi,
    localize_option_text,
    localize_question_prompt,
    localize_solution_description,
    localize_solution_name,
)
from pdf_export import export_friendly_pdf, export_technical_pdf
from recommendation_engine import build_engine_config, match_solutions, optimize_recommendations
from security_config import load_security_config, scan_hardcoded_secrets, validate_smtp_config

NS_X = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
NS_W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().lower()


_ENGINE_TEXT_EN = {
    "Seleccionada por alto desempeÃ±o multicriterio.": "Selected due to strong multi-criteria performance.",
    "Seleccionada por alto desempeño multicriterio.": "Selected due to strong multi-criteria performance.",
    "Costo estimado por defecto (sin precio pÃºblico confirmado).": "Default estimated cost applied (no confirmed public price).",
    "Costo estimado por defecto (sin precio público confirmado).": "Default estimated cost applied (no confirmed public price).",
    "Costo referido a esquema de suscripciÃ³n.": "Cost based on a subscription scheme.",
    "Costo referido a esquema de suscripción.": "Cost based on a subscription scheme.",
    "PenalizaciÃ³n por proveedor repetido para mejorar diversidad.": "Penalty applied for repeated provider to improve diversity.",
    "Penalización por proveedor repetido para mejorar diversidad.": "Penalty applied for repeated provider to improve diversity.",
    "PenalizaciÃ³n por dominio repetido para ampliar cobertura.": "Penalty applied for repeated domain to broaden coverage.",
    "Penalización por dominio repetido para ampliar cobertura.": "Penalty applied for repeated domain to broaden coverage.",
    "Sin candidatos para optimizar.": "No candidates available for optimization.",
}

_ENGINE_COMPONENT_KEY_EN = {
    "prioridad_kpi": "kpi_priority",
    "impacto": "impact",
    "costo": "cost",
    "riesgo": "risk",
    "esfuerzo": "effort",
    "factor_horizonte": "horizon_factor",
}


def _localize_engine_text(text: object, language: str) -> str:
    raw = str(text or "")
    if str(language).lower() != "en":
        return raw
    return _ENGINE_TEXT_EN.get(raw, raw)


def _localize_engine_driver(driver: object, language: str) -> str:
    raw = str(driver or "")
    if str(language).lower() != "en":
        return raw
    if "=" not in raw:
        return _localize_engine_text(raw, language)
    key, value = raw.split("=", 1)
    key_txt = _ENGINE_COMPONENT_KEY_EN.get(key.strip(), key.strip())
    return f"{key_txt}={value}"


def _localize_engine_explanation(expl: object, language: str) -> object:
    if not isinstance(expl, dict) or str(language).lower() != "en":
        return expl
    out = dict(expl)
    out["summary"] = _localize_engine_text(out.get("summary", ""), language)

    assumptions = out.get("assumptions", [])
    if isinstance(assumptions, list):
        out["assumptions"] = [_localize_engine_text(item, language) for item in assumptions]
    elif assumptions:
        out["assumptions"] = [_localize_engine_text(assumptions, language)]
    else:
        out["assumptions"] = []

    drivers = out.get("main_drivers", [])
    if isinstance(drivers, list):
        out["main_drivers"] = [_localize_engine_driver(item, language) for item in drivers]
    elif drivers:
        out["main_drivers"] = [_localize_engine_driver(drivers, language)]
    else:
        out["main_drivers"] = []

    component_scores = out.get("component_scores", {})
    if isinstance(component_scores, dict):
        out["component_scores"] = {_ENGINE_COMPONENT_KEY_EN.get(str(k), str(k)): v for k, v in component_scores.items()}
    return out


def _localize_engine_summary(summary: object, language: str) -> object:
    if not isinstance(summary, dict) or str(language).lower() != "en":
        return summary
    out = dict(summary)
    if "reason" in out:
        out["reason"] = _localize_engine_text(out.get("reason", ""), language)
    return out


def _localize_level_description(text: object, language: str) -> str:
    raw = str(text or "").strip()
    if str(language).lower() != "en" or not raw:
        return raw
    key = norm(raw)
    if key.startswith("sin conocimiento ni aplicacion de estandares de certificacion"):
        return (
            "No knowledge or application of certification standards.\n\n"
            "The company sells mainly in the local market and does not face certification requirements.\n"
            "It has limited information on applicable standards or compliance protocols."
        )
    return raw


def clean_solution_description(text: object) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    if not compact:
        return ""
    # Keep only actionable detail and avoid truncated fragments with "...".
    # These fragments come from the KPI transition explanatory block.
    marker = re.search(r"\b(?:Se propone para la transici[o\u00f3]n|It is proposed for the transition)\b", compact, flags=re.IGNORECASE)
    if marker:
        compact = compact[: marker.start()].strip()
    compact = re.sub(r"\s*,\s*$", "", compact).strip()
    compact = re.sub(r"\s*\.\.\.\s*$", ".", compact).strip()
    return compact


def _col_idx(cell_ref: str) -> int:
    m = re.match(r"([A-Z]+)", cell_ref)
    if not m:
        return 0
    n = 0
    for c in m.group(1):
        n = n * 26 + ord(c) - 64
    return n - 1


def read_xlsx(path: Path) -> dict[str, list[list[str]]]:
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", NS_X):
                shared.append("".join((n.text or "") for n in si.findall(".//a:t", NS_X)))

        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {r.attrib["Id"]: r.attrib["Target"] for r in rels.findall("pr:Relationship", NS_X)}

        out: dict[str, list[list[str]]] = {}
        for s in wb.findall("a:sheets/a:sheet", NS_X):
            name = s.attrib["name"]
            rid = s.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
            target = rel_map[rid]
            if target.startswith("/"):
                target = target.lstrip("/")
            elif not target.startswith("xl/"):
                target = "xl/" + target
            sx = ET.fromstring(zf.read(target))
            rows: list[list[str]] = []
            for r in sx.findall(".//a:sheetData/a:row", NS_X):
                vals: dict[int, str] = {}
                for c in r.findall("a:c", NS_X):
                    t = c.attrib.get("t", "")
                    if t == "inlineStr":
                        txt = "".join((n.text or "") for n in c.findall(".//a:t", NS_X)).strip()
                    else:
                        v = c.find("a:v", NS_X)
                        if v is None:
                            i = c.find("a:is", NS_X)
                            txt = "".join((n.text or "") for n in i.findall(".//a:t", NS_X)).strip() if i is not None else ""
                        else:
                            txt = (v.text or "").strip()
                            if t == "s" and txt.isdigit():
                                idx = int(txt)
                                txt = shared[idx].strip() if 0 <= idx < len(shared) else txt
                    vals[_col_idx(c.attrib.get("r", "A1"))] = txt
                if vals:
                    m = max(vals)
                    row = [""] * (m + 1)
                    for k, v in vals.items():
                        row[k] = v
                    rows.append(row)
            out[name] = rows
        return out


def read_docx_questions(path: Path) -> list[dict[str, object]]:
    with zipfile.ZipFile(path) as zf:
        doc = ET.fromstring(zf.read("word/document.xml"))
    paras = []
    for p in doc.findall(".//w:p", NS_W):
        txt = "".join((n.text or "") for n in p.findall(".//w:t", NS_W)).strip()
        if txt:
            paras.append(txt)
    q = []
    prompt = ""
    opts: list[str] = []
    for line in paras:
        if line.startswith("Question ") or line.startswith("Pregunta "):
            if prompt:
                q.append({"prompt": prompt, "options": opts})
            prompt = line
            opts = []
        elif prompt:
            opts.append(line)
    if prompt:
        q.append({"prompt": prompt, "options": opts})
    return q


def pick_sheet(names: list[str], hint: str) -> str:
    h = norm(hint)
    for n in names:
        if h in norm(n):
            return n
    raise RuntimeError(f"sheet not found for hint: {hint}")


def to_float(txt: str, default: float = 1.0) -> float:
    try:
        return float(str(txt).replace(",", "."))
    except Exception:
        return default


def profile_cfg(profile: str, language: str = "es") -> dict[str, str]:
    lang = str(language).lower()
    label_small = "Small-sized enterprise" if lang == "en" else "Pequeña empresa"
    label_medium = "Medium-sized enterprise" if lang == "en" else "Mediana empresa"
    cfg = {
        "small": {"label": label_small, "q_file": "Cuestionario pequenas empresas.docx", "model_hint": "pequen", "weight_hint": "pequen", "sol_hint": "pequen"},
        "medium": {"label": label_medium, "q_file": "Cuestionario medianas empresas.docx", "model_hint": "median", "weight_hint": "median", "sol_hint": "median"},
    }
    if profile not in cfg:
        raise RuntimeError("company type must be small or medium")
    return cfg[profile]


def load_profile_data(root: Path, profile: str, language: str = "es") -> dict[str, object]:
    cfg = profile_cfg(profile, language=language)
    model_xlsx = root / "assets" / "modelo_de_madurez" / "MM Adopcion-Tec-Pymes v2.0 validado expertos INIA.xlsx"
    weights_xlsx = root / "assets" / "modelo_de_madurez" / "Ponderaciones por KPI.xlsx"
    q_docx = root / "assets" / "cuestionarios" / cfg["q_file"]

    m_sheets = read_xlsx(model_xlsx)
    w_sheets = read_xlsx(weights_xlsx)
    model_rows = m_sheets[pick_sheet(list(m_sheets.keys()), cfg["model_hint"])]
    weight_rows = w_sheets[pick_sheet(list(w_sheets.keys()), cfg["weight_hint"])]
    questionnaire = read_docx_questions(q_docx)

    levels = []
    if len(model_rows) > 2:
        for c in model_rows[2][3:12]:
            if c and c.upper().startswith("N"):
                levels.append(c)
    n_levels = len(levels)
    if n_levels == 0:
        raise RuntimeError("no maturity levels found")

    weights = {}
    for r in weight_rows[1:]:
        if len(r) >= 4 and r[2].strip():
            key = (norm(r[0]), norm(r[1]), norm(r[2]))
            weights[key] = to_float(r[3], 1.0)

    parsed_model = []
    last_domain = ""
    last_kda = ""
    for r in model_rows[3:]:
        if len(r) < 3 or not r[2].strip():
            continue
        domain = r[0].strip() if len(r) > 0 and r[0].strip() else last_domain
        kda = r[1].strip() if len(r) > 1 and r[1].strip() else last_kda
        kpi = r[2].strip()
        last_domain = domain or last_domain
        last_kda = kda or last_kda
        texts = [(r[3 + i].strip() if len(r) > 3 + i else "") for i in range(n_levels)]
        parsed_model.append({"domain": domain, "kda": kda, "kpi": kpi, "level_labels": levels, "level_texts": texts})

    total = min(len(questionnaire), len(parsed_model))
    questions = []
    for i in range(total):
        qm = parsed_model[i]
        qd = questionnaire[i]
        key = (norm(qm["domain"]), norm(qm["kda"]), norm(qm["kpi"]))
        weight = weights.get(key, 1.0)
        raw_options = [str(o).strip() for o in qd["options"] if str(o).strip()]
        options = [localize_option_text(o, language=language) for o in raw_options]
        mapping = [min(idx + 1, len(qm["level_labels"])) for idx in range(len(options))]
        questions.append(
            {
                "number": i + 1,
                "domain": qm["domain"],
                "kda": qm["kda"],
                "kpi": qm["kpi"],
                "weight": weight,
                "prompt": localize_question_prompt(str(qd["prompt"]), i + 1, language=language),
                "options": options,
                "level_labels": qm["level_labels"],
                "level_texts": qm["level_texts"],
                "mapping": mapping,
            }
        )

    return {"label": cfg["label"], "sol_hint": cfg["sol_hint"], "questions": questions}


def load_solutions(root: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    xlsx = root / "assets" / "roadmap" / "Catalogo_Soluciones_MM_Agro_Pymes_v2-Chile.xlsx"
    sheets = read_xlsx(xlsx)
    sheet_name = "Catalogo_Soluciones" if "Catalogo_Soluciones" in sheets else next(iter(sheets.keys()))
    rows = sheets[sheet_name]
    if not rows:
        empty_report = {
            "schema_version": "catalog_v3.0",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "summary": {"rows_in_catalog": 0, "rows_processed": 0, "error_count": 0, "warning_count": 0, "duplicate_combinations": 0},
            "errors": [],
            "warnings": [],
        }
        return [], empty_report
    headers = rows[0]
    idx = {h: i for i, h in enumerate(headers) if h}

    def val(row: list[str], *keys: str) -> str:
        for k in keys:
            if k in idx and idx[k] < len(row):
                return row[idx[k]].strip()
        return ""

    raw_rows: list[dict[str, object]] = []
    for row_idx, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        name = val(r, "nombre_solucion", "solucion", "name")
        if not name:
            continue
        opt_txt = val(r, "opcion", "option")
        digits = "".join(ch for ch in opt_txt if ch.isdigit())
        raw_rows.append(
            {
                "row_number": row_idx,
                "code": val(r, "codigo_solucion", "code"),
                "model": val(r, "modelo"),
                "domain": val(r, "dominio", "domain"),
                "kda": val(r, "kda"),
                "kpi": val(r, "kpi"),
                "transition": val(r, "transicion", "transition"),
                "origin": val(r, "nivel_origen"),
                "target": val(r, "nivel_destino"),
                "option": int(digits) if digits else 0,
                "name": name,
                "description": val(r, "descripcion_solucion", "descripcion"),
                "plazo_raw": val(r, "plazo_implementacion", "plazo"),
                "provider": val(r, "proveedor_programa_chileno_preferente", "proveedor", "provider"),
                "provider_url": val(r, "url_proveedor_programa_chileno", "provider_url"),
                "source": val(r, "fuente_contexto_territorial", "source", "fuente", "source_context"),
                # Prioriza la URL de la solución específica (fuente) y deja contexto como respaldo.
                "source_url": val(r, "url_fuente", "url_fuente_contexto_territorial", "source_url"),
                "price_reference": val(r, "precio_referencial", "price_reference", "price"),
                "price_clp_raw": val(r, "precio_referencial_clp", "precio_referencial", "price"),
                "currency": val(r, "moneda", "currency"),
                "fx_date": val(r, "fecha_tipo_cambio_clp", "fx_date"),
                "source_date": val(r, "fecha_vigencia", "vigencia", "updated_at"),
            }
        )

    catalog_rows, catalog_report = build_catalog_v3(raw_rows)
    out: list[dict[str, object]] = []
    for row in catalog_rows:
        out.append(
            {
                "model": row["model"],
                "domain": row["domain"],
                "kda": row["kda"],
                "kpi": row["kpi"],
                "transition": row["transition"],
                "origin": row["origin"],
                "target": row["target"],
                "option": row["option"],
                "name": row["name"],
                "description": row["description"],
                "plazo": row["horizon"],
                "provider": row["provider"],
                "provider_url": " | ".join(row["provider_urls"]),
                "source": row["source"],
                "source_url": " | ".join(row["source_urls"]),
                "price": row["price_display"],
                "price_type": row["price_type"],
                "price_min_clp": row["price_min_clp"],
                "price_max_clp": row["price_max_clp"],
                "impact_level": row["impact_level"],
                "impact_score": row["impact_score"],
                "effort_level": row["effort_level"],
                "effort_score": row["effort_score"],
                "risk_level": row["risk_level"],
                "risk_score": row["risk_score"],
                "dependencies": row["dependencies"],
                "schema_version": row["schema_version"],
            }
        )
    return out, catalog_report

def _horizon(plazo: str) -> str:
    t = norm(plazo)
    if "corto" in t or "short" in t:
        return "Short term"
    if "mediano" in t or "medium" in t:
        return "Medium term"
    if "largo" in t or "long" in t:
        return "Long term"
    months = _extract_timeline_months(plazo)
    if months is not None:
        if months <= 3:
            return "Short term"
        if months <= 6:
            return "Medium term"
        if months <= 12:
            return "Long term"
    return "Unclassified"


def _extract_timeline_months(value: object) -> float | None:
    if value is None:
        return None
    text = str(value)
    normalized = norm(text)
    numbers = [float(token.replace(",", ".")) for token in re.findall(r"\d+(?:[.,]\d+)?", text)]
    if not numbers:
        return None
    if "mes" in normalized:
        return max(numbers)
    if "anio" in normalized:
        return max(numbers) * 12.0
    return None


def _horizon_order(plazo: str) -> int:
    p = _horizon(plazo)
    return {"Short term": 1, "Medium term": 2, "Long term": 3}.get(p, 4)


def weighted_avg(values: list[tuple[float, float]]) -> float:
    tw = sum(w for _, w in values)
    if tw <= 0:
        return 0.0
    return sum(v * w for v, w in values) / tw


def build_traceability_entries(
    kpi_results: list[dict[str, object]],
    roadmap_entries: list[dict[str, object]],
    engine_summary: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    by_question: dict[int, dict[str, object]] = {}
    by_kpi_transition: dict[tuple[str, str], dict[str, object]] = {}
    for row in kpi_results:
        qn = row.get("question_number")
        if isinstance(qn, int):
            by_question[qn] = row
        kpi_key = norm(str(row.get("kpi", "")))
        transition = f"{row.get('current_label', '')}->{row.get('target_label', '')}"
        by_kpi_transition[(kpi_key, norm(transition))] = row

    cfg = engine_summary.get("config", {}) if isinstance(engine_summary, dict) else {}
    weights = cfg.get("weights", {}) if isinstance(cfg, dict) else {}

    out: list[dict[str, object]] = []
    for idx, row in enumerate(roadmap_entries, start=1):
        qn = row.get("question_number")
        kpi = str(row.get("kpi", ""))
        transition = str(row.get("transition", ""))
        kpi_row = by_question.get(int(qn)) if isinstance(qn, int) else None
        if kpi_row is None:
            kpi_row = by_kpi_transition.get((norm(kpi), norm(transition)))

        expl = row.get("engine_explanation", {})
        drivers = expl.get("main_drivers", []) if isinstance(expl, dict) else []
        assumptions = expl.get("assumptions", []) if isinstance(expl, dict) else []
        dependencies = row.get("dependencies", [])
        if not isinstance(dependencies, list):
            dependencies = [str(dependencies)] if dependencies else []

        out.append(
            {
                "trace_id": idx,
                "question_number": qn,
                "domain": row.get("domain", kpi_row.get("domain", "") if isinstance(kpi_row, dict) else ""),
                "kda": row.get("kda", kpi_row.get("kda", "") if isinstance(kpi_row, dict) else ""),
                "kpi": kpi,
                "selected_option_text": kpi_row.get("selected_option_text", "") if isinstance(kpi_row, dict) else "",
                "current_label": row.get("current_label", kpi_row.get("current_label", "") if isinstance(kpi_row, dict) else ""),
                "target_label": row.get("target_label", kpi_row.get("target_label", "") if isinstance(kpi_row, dict) else ""),
                "gap": kpi_row.get("gap", row.get("gap", 0)) if isinstance(kpi_row, dict) else row.get("gap", 0),
                "priority": row.get("priority", kpi_row.get("priority", 0) if isinstance(kpi_row, dict) else 0),
                "transition": transition,
                "horizon": row.get("plazo", ""),
                "recommendation": row.get("solution_name", ""),
                "provider": row.get("provider", ""),
                "dependencies": dependencies,
                "engine_score": expl.get("selection_score", 0) if isinstance(expl, dict) else 0,
                "engine_main_drivers": drivers if isinstance(drivers, list) else [str(drivers)],
                "engine_assumptions": assumptions if isinstance(assumptions, list) else [str(assumptions)],
                "rule_weights": weights if isinstance(weights, dict) else {},
                "rule_constraints": {
                    "max_recommendations": cfg.get("max_recommendations") if isinstance(cfg, dict) else None,
                    "max_per_provider": cfg.get("max_per_provider") if isinstance(cfg, dict) else None,
                    "max_per_kpi": cfg.get("max_per_kpi") if isinstance(cfg, dict) else None,
                    "budget_total_clp": cfg.get("budget_total_clp") if isinstance(cfg, dict) else None,
                    "budget_short_clp": cfg.get("budget_short_clp") if isinstance(cfg, dict) else None,
                    "budget_medium_clp": cfg.get("budget_medium_clp") if isinstance(cfg, dict) else None,
                    "budget_long_clp": cfg.get("budget_long_clp") if isinstance(cfg, dict) else None,
                },
            }
        )
    return out


def build_roadmap(
    root: Path,
    company_type: str,
    answers: dict[int, int] | list[int],
    target_level: int,
    company_name: str,
    company_rut: str,
    company_email: str,
    engine_cfg: object,
    language: str = "es",
) -> dict[str, object]:
    profile = load_profile_data(root, company_type, language=language)
    solutions, catalog_report = load_solutions(root)
    questions = profile["questions"]

    if isinstance(answers, list):
        answer_map = {i + 1: int(v) for i, v in enumerate(answers)}
    else:
        answer_map = {int(k): int(v) for k, v in answers.items()}

    missing = [q["number"] for q in questions if q["number"] not in answer_map]
    if missing:
        raise RuntimeError("Missing answers for questions: " + ", ".join(str(x) for x in missing))

    max_level = max(len(q["level_labels"]) for q in questions if q["level_labels"])
    target_level = max(1, min(int(target_level), max_level))

    domain_current: dict[str, list[tuple[float, float]]] = defaultdict(list)
    domain_target: dict[str, list[tuple[float, float]]] = defaultdict(list)
    kpi_results = []
    candidate_entries: list[dict[str, object]] = []

    for q in questions:
        n = int(q["number"])
        opt = int(answer_map[n])
        options = q["options"]
        mapping = q["mapping"]
        labels = q["level_labels"]
        texts = q["level_texts"]
        if opt < 1:
            opt = 1
        if opt > len(options):
            opt = len(options)

        current = mapping[opt - 1] if mapping else min(opt, len(labels))
        current = max(1, min(current, len(labels)))
        target = min(target_level, len(labels))
        domain_localized = localize_domain(str(q["domain"]), language=language)
        kda_localized = localize_kda(str(q["kda"]), language=language)
        kpi_localized = localize_kpi(str(q["kpi"]), language=language)

        domain_current[domain_localized].append((float(current), float(q["weight"])))
        domain_target[domain_localized].append((float(target), float(q["weight"])))

        if target <= current:
            continue

        gap = target - current
        priority = round(gap * float(q["weight"]), 4)
        c_label = labels[current - 1]
        t_label = labels[target - 1]
        transition = f"{c_label}->{t_label}"

        kpi_results.append(
            {
                "question_number": n,
                "domain": domain_localized,
                "kda": kda_localized,
                "kpi": kpi_localized,
                "weight": q["weight"],
                "current_level": current,
                "target_level": target,
                "current_label": c_label,
                "target_label": t_label,
                "gap": gap,
                "priority": priority,
                "selected_option_text": options[opt - 1],
                "current_description": _localize_level_description(texts[current - 1] if current - 1 < len(texts) else "", language),
                "target_description": _localize_level_description(texts[target - 1] if target - 1 < len(texts) else "", language),
            }
        )

        matches = match_solutions(
            solutions,
            sol_hint=str(profile["sol_hint"]),
            domain=q["domain"],
            kda=q["kda"],
            kpi=q["kpi"],
            transition=transition,
            origin=c_label,
            target=t_label,
            max_candidates=int(getattr(engine_cfg, "max_candidates_per_kpi", 4)),
        )
        for s in matches:
            cleaned_description = clean_solution_description(s.get("description", ""))
            candidate_entries.append(
                {
                    "domain": domain_localized,
                    "kda": kda_localized,
                    "kpi": kpi_localized,
                    "transition": transition,
                    "plazo": _horizon(str(s.get("plazo", ""))),
                    "solution_name": localize_solution_name(str(s.get("name", "")), language=language),
                    "solution_description": localize_solution_description(cleaned_description, language=language),
                    "provider": s.get("provider", ""),
                    "provider_url": s.get("provider_url", ""),
                    "source": s.get("source", ""),
                    "source_url": s.get("source_url", ""),
                    "price": s.get("price", "No informado" if str(language).lower() != "en" else "Not reported") or ("No informado" if str(language).lower() != "en" else "Not reported"),
                    "price_type": s.get("price_type", "unknown"),
                    "price_min_clp": s.get("price_min_clp"),
                    "price_max_clp": s.get("price_max_clp"),
                    "impact_level": s.get("impact_level", "Medio" if str(language).lower() != "en" else "Medium"),
                    "impact_score": s.get("impact_score", 3.0),
                    "effort_level": s.get("effort_level", "Medio" if str(language).lower() != "en" else "Medium"),
                    "effort_score": s.get("effort_score", 3.0),
                    "risk_level": s.get("risk_level", "Medio" if str(language).lower() != "en" else "Medium"),
                    "risk_score": s.get("risk_score", 3.0),
                    "dependencies": s.get("dependencies", []),
                    "priority": priority,
                    "option": s.get("option", 0),
                    "question_number": n,
                    "current_label": c_label,
                    "target_label": t_label,
                }
            )

    kpi_results.sort(key=lambda x: (float(x["priority"]), float(x["gap"])), reverse=True)

    optimized_entries, engine_report = optimize_recommendations(candidate_entries, engine_cfg)
    dedup: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for e in optimized_entries:
        key = (norm(str(e["kpi"])), norm(str(e["transition"])), norm(str(e["solution_name"])), norm(str(e["plazo"])))
        score = float(e.get("engine_explanation", {}).get("selection_score", 0) or 0)
        prev = dedup.get(key)
        prev_score = float(prev.get("engine_explanation", {}).get("selection_score", 0) or 0) if prev else -1.0
        if prev is None or score > prev_score:
            dedup[key] = e
    roadmap_entries = sorted(
        dedup.values(),
        key=lambda e: (
            _horizon_order(str(e["plazo"])),
            -float(e.get("engine_explanation", {}).get("selection_score", 0) or 0),
            -float(e.get("priority", 0) or 0),
            norm(str(e["solution_name"])),
        ),
    )
    if str(language).lower() == "en":
        localized_entries: list[dict[str, object]] = []
        for row in roadmap_entries:
            item = dict(row)
            item["engine_explanation"] = _localize_engine_explanation(item.get("engine_explanation", {}), language)
            localized_entries.append(item)
        roadmap_entries = localized_entries
        engine_report = _localize_engine_summary(engine_report, language)
    traceability_entries = build_traceability_entries(kpi_results, roadmap_entries, engine_report)

    domain_results = []
    for d in sorted(domain_current.keys(), key=norm):
        cs = weighted_avg(domain_current[d])
        ts = weighted_avg(domain_target[d])
        domain_results.append({"domain": d, "current_score": round(cs, 4), "target_score": round(ts, 4), "gap": round(ts - cs, 4)})

    current_score = weighted_avg([x for vals in domain_current.values() for x in vals])
    target_score = weighted_avg([x for vals in domain_target.values() for x in vals])

    catalog_summary = catalog_report.get("summary", {}) if isinstance(catalog_report, dict) else {}
    return {
        "company": {"name": company_name, "rut": company_rut, "email": company_email, "company_type": profile["label"]},
        "result": {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "target_level_index": target_level,
            "current_score": round(current_score, 4),
            "target_score": round(target_score, 4),
            "kpi_results": kpi_results,
            "domain_results": domain_results,
            "roadmap_entries": roadmap_entries,
            "traceability_entries": traceability_entries,
            "catalog_summary": {
                "schema_version": catalog_report.get("schema_version", "catalog_v3.0"),
                "rows_in_catalog": catalog_summary.get("rows_in_catalog", 0),
                "rows_processed": catalog_summary.get("rows_processed", 0),
                "error_count": catalog_summary.get("error_count", 0),
                "warning_count": catalog_summary.get("warning_count", 0),
                "duplicate_combinations": catalog_summary.get("duplicate_combinations", 0),
            },
            "engine_summary": engine_report,
        },
        "catalog_validation_report": catalog_report,
    }


def load_answers(path: Path) -> dict[int, int] | list[int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [int(x) for x in payload]
    if isinstance(payload, dict):
        if "answers" in payload:
            a = payload["answers"]
            if isinstance(a, list):
                return [int(x) for x in a]
            if isinstance(a, dict):
                return {int(k): int(v) for k, v in a.items()}
        return {int(k): int(v) for k, v in payload.items()}
    raise RuntimeError("Unsupported answers format")


def save_txt(payload: dict[str, object], path: Path) -> None:
    c = payload["company"]
    r = payload["result"]
    cat = r.get("catalog_summary", {}) if isinstance(r, dict) else {}
    eng = r.get("engine_summary", {}) if isinstance(r, dict) else {}
    lines = [
        "ROADMAP SUMMARY",
        "",
        f"Company: {c.get('name','')}",
        f"Tipo: {c.get('company_type','')}",
        f"RUT: {c.get('rut','')}",
        f"Email: {c.get('email','')}",
        f"Generado: {r.get('timestamp','')}",
        "",
        f"Current score: {r.get('current_score',0)}",
        f"Target score: {r.get('target_score',0)}",
        f"Target level: {r.get('target_level_index',0)}",
        "",
        f"Catalog ({cat.get('schema_version','catalog_v3.0')}): "
        f"rows={cat.get('rows_processed',0)}, "
        f"errors={cat.get('error_count',0)}, "
        f"warnings={cat.get('warning_count',0)}",
        "",
        f"Motor recomendaciones ({eng.get('engine_version','eng_v1.0')}): "
        f"candidatas={eng.get('candidate_count',0)}, "
        f"seleccionadas={eng.get('selected_count',0)}, "
        f"presupuesto_usado_clp={eng.get('used_budget_total_clp',0)}",
        "",
        f"Brechas KPI: {len(r.get('kpi_results',[]))}",
    ]
    for row in r.get("kpi_results", [])[:12]:
        lines.append(
            f"- [{row['priority']}] {row['kpi']} | {row['current_label']} -> {row['target_label']} | brecha={row['gap']}"
        )
    lines.append("")
    lines.append("Roadmap actions:")
    for row in r.get("roadmap_entries", []):
        expl = row.get("engine_explanation", {})
        drivers = ", ".join(expl.get("main_drivers", [])[:2]) if isinstance(expl, dict) else ""
        lines.append(
            f"- {row['plazo']} | {row['kpi']} | {row['solution_name']} | {row['price']} | "
            f"score={expl.get('selection_score',0)} | drivers={drivers}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _slug(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", norm(value))
    return clean.strip("-") or "company"


def save_preview(payload: dict[str, object], path: Path) -> None:
    result = payload.get("result", {})
    preview = {
        "generated_at": result.get("timestamp", ""),
        "company": payload.get("company", {}),
        "engine_summary": result.get("engine_summary", {}),
        "catalog_summary": result.get("catalog_summary", {}),
        "roadmap_entries": result.get("roadmap_entries", []),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")


def save_traceability_json(payload: dict[str, object], path: Path) -> None:
    result = payload.get("result", {})
    data = {
        "generated_at": result.get("timestamp", ""),
        "company": payload.get("company", {}),
        "traceability_entries": result.get("traceability_entries", []),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def save_traceability_csv(payload: dict[str, object], path: Path) -> None:
    result = payload.get("result", {})
    rows = result.get("traceability_entries", [])
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "trace_id",
        "question_number",
        "domain",
        "kda",
        "kpi",
        "selected_option_text",
        "current_label",
        "target_label",
        "gap",
        "priority",
        "transition",
        "horizon",
        "recommendation",
        "provider",
        "dependencies",
        "engine_score",
        "engine_main_drivers",
        "engine_assumptions",
        "rule_weights",
        "rule_constraints",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            out_row = dict(row)
            for key in ("dependencies", "engine_main_drivers", "engine_assumptions"):
                val = out_row.get(key, [])
                if isinstance(val, list):
                    out_row[key] = " | ".join(str(x) for x in val)
            for key in ("rule_weights", "rule_constraints"):
                val = out_row.get(key, {})
                if isinstance(val, dict):
                    out_row[key] = json.dumps(val, ensure_ascii=False, sort_keys=True)
            writer.writerow({k: out_row.get(k, "") for k in fields})


def apply_roadmap_edits(payload: dict[str, object], edits_path: Path) -> dict[str, object]:
    edits = json.loads(edits_path.read_text(encoding="utf-8"))
    candidate_rows = edits.get("roadmap_entries") if isinstance(edits, dict) else edits
    if not isinstance(candidate_rows, list):
        raise RuntimeError("The edit file must contain a list in 'roadmap_entries' or a root list.")

    valid_rows: list[dict[str, object]] = []
    for row in candidate_rows:
        if not isinstance(row, dict):
            continue
        if not str(row.get("solution_name", "")).strip():
            continue
        if not str(row.get("kpi", "")).strip():
            continue
        if not str(row.get("plazo", "")).strip():
            continue
        valid_rows.append(row)

    if not valid_rows:
        raise RuntimeError("No valid actions were found in the edit file.")

    payload_out = dict(payload)
    result = dict(payload_out.get("result", {}))
    result["roadmap_entries"] = sorted(
        valid_rows,
        key=lambda e: (
            _horizon_order(str(e.get("plazo", ""))),
            -float(e.get("engine_explanation", {}).get("selection_score", e.get("priority", 0)) or 0),
            norm(str(e.get("solution_name", ""))),
        ),
    )
    result["traceability_entries"] = build_traceability_entries(
        result.get("kpi_results", []) if isinstance(result.get("kpi_results"), list) else [],
        result["roadmap_entries"] if isinstance(result["roadmap_entries"], list) else [],
        result.get("engine_summary", {}) if isinstance(result.get("engine_summary"), dict) else {},
    )
    payload_out["result"] = result
    return payload_out


def autosave_session(payload: dict[str, object], session_dir: Path) -> Path:
    company = payload.get("company", {})
    name = str(company.get("name", "company"))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_path = session_dir / f"{_slug(name)}_{stamp}.json"
    session_dir.mkdir(parents=True, exist_ok=True)
    session_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return session_path


def _rebuild_engine_budget_summary(entries: list[dict[str, object]]) -> tuple[float, dict[str, float]]:
    total = 0.0
    by_horizon: dict[str, float] = {}
    for row in entries:
        cost_raw = row.get("price_max_clp")
        if cost_raw is None:
            cost_raw = row.get("price_min_clp")
        if cost_raw is None:
            cost_raw = row.get("cost_estimated_clp")
        try:
            cost = float(cost_raw)
        except Exception:
            continue
        if cost < 0:
            continue
        total += cost
        horizon = str(row.get("plazo", "Unclassified"))
        by_horizon[horizon] = by_horizon.get(horizon, 0.0) + cost
    by_horizon = {k: round(v, 2) for k, v in by_horizon.items()}
    return round(total, 2), by_horizon


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RoadmapGenerator CLI")
    parser.add_argument("--company-type", choices=["small", "medium"], required=True)
    parser.add_argument("--target-level", type=int, required=True)
    parser.add_argument("--answers-file", type=Path, required=True)
    parser.add_argument("--company-name", default="Company")
    parser.add_argument("--company-rut", default="")
    parser.add_argument("--company-email", default="")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output-json", type=Path, default=None)
    parser.add_argument("--output-txt", type=Path, default=None)
    parser.add_argument("--output-pdf-tech", type=Path, default=None)
    parser.add_argument("--output-pdf-friendly", type=Path, default=None)
    parser.add_argument("--output-catalog-report-json", type=Path, default=None)
    parser.add_argument("--output-catalog-report-txt", type=Path, default=None)
    parser.add_argument("--output-trace-json", type=Path, default=None)
    parser.add_argument("--output-trace-csv", type=Path, default=None)
    parser.add_argument("--engine-config-file", type=Path, default=None)
    parser.add_argument("--budget-total-clp", type=float, default=None)
    parser.add_argument("--budget-short-clp", type=float, default=None)
    parser.add_argument("--budget-medium-clp", type=float, default=None)
    parser.add_argument("--budget-long-clp", type=float, default=None)
    parser.add_argument("--max-recommendations", type=int, default=None)
    parser.add_argument("--max-per-provider", type=int, default=None)
    parser.add_argument("--max-per-kpi", type=int, default=None)
    parser.add_argument("--max-candidates-per-kpi", type=int, default=None)
    parser.add_argument(
        "--output-preview-json",
        type=Path,
        default=None,
        help="Generates an editable preview of the roadmap (lightweight JSON).",
    )
    parser.add_argument(
        "--apply-edits-file",
        type=Path,
        default=None,
        help="Applies manual edits from a JSON file with roadmap_entries.",
    )
    parser.add_argument(
        "--autosave-session",
        action="store_true",
        help="Saves an execution snapshot for traceability.",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=None,
        help="Directory for session snapshots (default: outputs/sessions).",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip PDF generation to iterate faster.",
    )
    parser.add_argument(
        "--strict-catalog",
        action="store_true",
        help="Fail execution if the catalog contains validation errors.",
    )
    parser.add_argument(
        "--security-check",
        action="store_true",
        help="Runs security checks (environment SMTP validation + hardcoded-secret detection).",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    out_json = args.output_json or (root / "outputs" / "roadmap_result.json")
    out_txt = args.output_txt or (root / "outputs" / "roadmap_result.txt")
    out_pdf_tech = args.output_pdf_tech or (root / "outputs" / "roadmap_tecnico.pdf")
    out_pdf_friendly = args.output_pdf_friendly or (root / "outputs" / "roadmap_friendly.pdf")
    out_catalog_report_json = args.output_catalog_report_json or (root / "outputs" / "catalog_validation_report.json")
    out_catalog_report_txt = args.output_catalog_report_txt or (root / "outputs" / "catalog_validation_report.txt")
    out_trace_json = args.output_trace_json or (root / "outputs" / "roadmap_traceability.json")
    out_trace_csv = args.output_trace_csv or (root / "outputs" / "roadmap_traceability.csv")
    out_preview = args.output_preview_json.resolve() if args.output_preview_json is not None else None
    engine_config_file = args.engine_config_file.resolve() if args.engine_config_file is not None else None
    edits_file = args.apply_edits_file.resolve() if args.apply_edits_file is not None else None
    session_dir = args.session_dir.resolve() if args.session_dir is not None else (root / "outputs" / "sessions")

    sec_cfg, env_file = load_security_config(root)
    smtp_errors = validate_smtp_config(sec_cfg, strict=False)
    if smtp_errors:
        for msg in smtp_errors:
            print(f"[SEC] {msg}")
        return 2

    if args.security_check:
        findings = scan_hardcoded_secrets(root)
        if findings:
            print("[SEC] Potential hardcoded secrets were detected:")
            for row in findings:
                print(f"[SEC] - {row}")
            return 2
        print("[SEC] Security check OK (no hardcoded secret patterns found).")
        if not sec_cfg.require_smtp:
            print("[SEC] ROADMAP_REQUIRE_SMTP=0 (local mode). SMTP is not mandatory in this environment.")
        if env_file is not None:
            print(f"[SEC] .env file loaded from: {env_file}")

    engine_cfg = build_engine_config(
        engine_config_file,
        overrides={
            "budget_total_clp": args.budget_total_clp,
            "budget_short_clp": args.budget_short_clp,
            "budget_medium_clp": args.budget_medium_clp,
            "budget_long_clp": args.budget_long_clp,
            "max_recommendations": args.max_recommendations,
            "max_per_provider": args.max_per_provider,
            "max_per_kpi": args.max_per_kpi,
            "max_candidates_per_kpi": args.max_candidates_per_kpi,
        },
    )

    answers = load_answers(args.answers_file)
    payload = build_roadmap(
        root,
        args.company_type,
        answers,
        args.target_level,
        args.company_name,
        args.company_rut,
        args.company_email,
        engine_cfg,
    )
    catalog_report = payload.get("catalog_validation_report", {})
    catalog_summary = payload.get("result", {}).get("catalog_summary", {})

    if args.strict_catalog and int(catalog_summary.get("error_count", 0)) > 0:
        print(f"[DATA] Invalid catalog: {catalog_summary.get('error_count', 0)} errors.")
        return 3

    if edits_file is not None:
        payload = apply_roadmap_edits(payload, edits_file)
        result = payload.get("result", {})
        if isinstance(result, dict):
            entries = result.get("roadmap_entries", [])
            eng = result.get("engine_summary", {})
            if isinstance(eng, dict):
                eng["selected_count"] = len(entries) if isinstance(entries, list) else 0
                if isinstance(entries, list):
                    total_budget, budget_by_horizon = _rebuild_engine_budget_summary(entries)
                    eng["used_budget_total_clp"] = total_budget
                    eng["used_budget_by_horizon"] = budget_by_horizon
                eng["manual_edits_applied"] = True

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_catalog_report_json.parent.mkdir(parents=True, exist_ok=True)
    out_catalog_report_txt.parent.mkdir(parents=True, exist_ok=True)
    out_trace_json.parent.mkdir(parents=True, exist_ok=True)
    out_trace_csv.parent.mkdir(parents=True, exist_ok=True)
    if out_preview is not None:
        out_preview.parent.mkdir(parents=True, exist_ok=True)
    if not args.skip_pdf:
        out_pdf_tech.parent.mkdir(parents=True, exist_ok=True)
        out_pdf_friendly.parent.mkdir(parents=True, exist_ok=True)

    out_catalog_report_json.write_text(json.dumps(catalog_report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_catalog_report_txt.write_text(catalog_report_to_text(catalog_report), encoding="utf-8")

    payload_export = dict(payload)
    if "catalog_validation_report" in payload_export:
        payload_export.pop("catalog_validation_report")
    out_json.write_text(json.dumps(payload_export, ensure_ascii=False, indent=2), encoding="utf-8")
    save_txt(payload, out_txt)
    save_traceability_json(payload, out_trace_json)
    save_traceability_csv(payload, out_trace_csv)
    if out_preview is not None:
        save_preview(payload, out_preview)
    if args.autosave_session:
        autosaved = autosave_session(payload, session_dir)
        print(f"[UX] Session saved to: {autosaved}")
    if not args.skip_pdf:
        export_technical_pdf(payload, out_pdf_tech)
        export_friendly_pdf(payload, out_pdf_friendly)

    print(f"JSON generado en: {out_json}")
    print(f"TXT generado en: {out_txt}")
    if out_preview is not None:
        print(f"Preview JSON generated at: {out_preview}")
    print(f"Traceability (JSON) generated at: {out_trace_json}")
    print(f"Traceability (CSV) generated at: {out_trace_csv}")
    if not args.skip_pdf:
        print(f"Technical PDF generated at: {out_pdf_tech}")
        print(f"Friendly PDF generated at: {out_pdf_friendly}")
    else:
        print("[UX] PDFs skipped by --skip-pdf")
    print(f"Catalog report (JSON) generated at: {out_catalog_report_json}")
    print(f"Catalog report (TXT) generated at: {out_catalog_report_txt}")
    print(
        f"[DATA] Catalog v3 -> rows={catalog_summary.get('rows_processed',0)} "
        f"errors={catalog_summary.get('error_count',0)} warnings={catalog_summary.get('warning_count',0)}"
    )
    engine_summary = payload.get("result", {}).get("engine_summary", {})
    print(
        f"[ENG] Motor -> candidatas={engine_summary.get('candidate_count',0)} "
        f"seleccionadas={engine_summary.get('selected_count',0)} "
        f"presupuesto_usado={engine_summary.get('used_budget_total_clp',0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
