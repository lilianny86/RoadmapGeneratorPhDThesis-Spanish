from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse


from economic_policy import CATALOG_EFFORT, CATALOG_FINANCING

SCHEMA_VERSION = "catalog_v4.0"
ALLOWED_HORIZONS = {"Corto plazo", "Mediano plazo", "Largo plazo", "Sin clasificar"}
REQUIRED_FIELDS = ["model", "domain", "kda", "kpi", "transition", "name", "description", "horizon"]


def _norm(text: object) -> str:
    value = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", value).strip().lower()


def _split_urls(value: object) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in re.split(r"\s*\|\s*|\s*;\s*|\s*,\s*", raw) if p.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


def _is_valid_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def _horizon(value: object) -> str:
    return {
        "corto": "Corto plazo",
        "mediano": "Mediano plazo",
        "largo": "Largo plazo",
        "": "Sin clasificar",
    }.get(_norm(value), str(value).strip())



def _level_from_score(score: float) -> str:
    if score >= 4.0:
        return "Alto"
    if score >= 2.6:
        return "Medio"
    return "Bajo"


def _infer_dependencies(text: str) -> list[str]:
    k = _norm(text)
    deps: list[str] = []
    if any(w in k for w in ["sensor", "iot", "monitoreo", "riego"]):
        deps.append("Conectividad estable en terreno")
    if any(w in k for w in ["erp", "software", "sistema", "defontana"]):
        deps.append("Datos maestros y procesos estandarizados")
    if any(w in k for w in ["online", "ecommerce", "jumpseller", "digital"]):
        deps.append("Catálogo digital actualizado")
    if any(w in k for w in ["certificacion", "certific", "export"]):
        deps.append("Documentación y trazabilidad operativa")
    if not deps:
        deps.append("Capacitación básica del equipo")
    return deps


def _enrich_row(row: dict[str, object]) -> dict[str, object]:
    text_blob = " ".join([str(row.get("name", "")), str(row.get("description", "")), str(row.get("kpi", ""))])
    key = _norm(text_blob)
    impact = 2.6
    if any(w in key for w in ["automat", "integr", "analit", "tiempo real", "control"]):
        impact += 1.0

    # Preserve the technical criteria without treating cost or stage as technical evidence.
    effort = 2.0
    risk = 1.9
    if any(w in key for w in ["integracion", "on premise", "infraestructura"]):
        risk += 0.5


    impact = min(max(impact, 1.0), 5.0)
    effort = min(max(effort, 1.0), 5.0)
    risk = min(max(risk, 1.0), 5.0)

    enriched = dict(row)
    enriched["impact_score"] = round(impact, 2)
    enriched["effort_score"] = round(effort, 2)
    enriched["risk_score"] = round(risk, 2)
    enriched["impact_level"] = _level_from_score(impact)
    enriched["effort_level"] = _level_from_score(effort)
    enriched["risk_level"] = _level_from_score(risk)
    enriched["dependencies"] = _infer_dependencies(text_blob)
    return enriched


def _validate_row(row: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    row_id = str(row.get("code") or f"row-{row.get('row_number', '?')}")
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []

    for field in REQUIRED_FIELDS:
        if not str(row.get(field, "")).strip():
            errors.append({"row_id": row_id, "field": field, "message": "Campo obligatorio vacío"})

    horizon = str(row.get("horizon", "Sin clasificar"))
    if horizon not in ALLOWED_HORIZONS:
        errors.append({"row_id": row_id, "field": "horizon", "message": f"Horizonte inválido: {horizon}"})

    for f in ["provider_urls", "source_urls"]:
        for url in row.get(f, []):
            if not _is_valid_url(url):
                warnings.append({"row_id": row_id, "field": f, "message": f"URL inválida: {url}"})

    if row.get("economic_effort") not in CATALOG_EFFORT.values():
        errors.append({"row_id": row_id, "field": "economic_effort", "message": "Categoria economica invalida"})
    if row.get("financing_mode") not in CATALOG_FINANCING.values():
        errors.append({"row_id": row_id, "field": "financing_mode", "message": "Modalidad de financiamiento invalida"})


    return errors, warnings


def build_catalog_v4(raw_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows_out: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []

    seen_keys: set[tuple[str, str, str, str, str, str]] = set()
    code_counts: dict[str, int] = {}
    duplicated_rows: list[str] = []

    for raw in raw_rows:
        row = {
            "schema_version": SCHEMA_VERSION,
            "row_number": raw.get("row_number"),
            "code": str(raw.get("code", "")).strip(),
            "model": str(raw.get("model", "")).strip(),
            "domain": str(raw.get("domain", "")).strip(),
            "kda": str(raw.get("kda", "")).strip(),
            "kpi": str(raw.get("kpi", "")).strip(),
            "transition": str(raw.get("transition", "")).strip(),
            "origin": str(raw.get("origin", "")).strip(),
            "target": str(raw.get("target", "")).strip(),
            "option": int(raw.get("option", 0) or 0),
            "name": str(raw.get("name", "")).strip(),
            "description": str(raw.get("description", "")).strip(),
            "provider": str(raw.get("provider", "")).strip(),
            "provider_urls": _split_urls(raw.get("provider_url")),
            "source": str(raw.get("source", "")).strip(),
            "source_urls": _split_urls(raw.get("source_url")),
            "plazo_raw": str(raw.get("plazo_raw", "")).strip(),
            "horizon": _horizon(raw.get("plazo_raw")),
            "economic_effort": CATALOG_EFFORT.get(str(raw.get("economic_effort", "")), ""),
            "financing_mode": CATALOG_FINANCING.get(str(raw.get("financing_mode", "")), ""),
            "economic_components": str(raw.get("economic_components", "")).strip(),
            "economic_rationale": str(raw.get("economic_rationale", "")).strip(),
            "expert_comments": str(raw.get("expert_comments", "")).strip(),
            "vigencia_source": str(raw.get("source_date", "")).strip(),
        }

        row = _enrich_row(row)
        row_errors, row_warnings = _validate_row(row)
        errors.extend(row_errors)
        warnings.extend(row_warnings)

        duplicate_key = (
            _norm(row["model"]),
            _norm(row["domain"]),
            _norm(row["kda"]),
            _norm(row["kpi"]),
            _norm(row["transition"]),
            _norm(row["name"]),
        )
        if duplicate_key in seen_keys:
            duplicated_rows.append(str(row.get("code") or f"row-{row.get('row_number')}"))
        else:
            seen_keys.add(duplicate_key)

        code = _norm(row["code"])
        if code:
            code_counts[code] = code_counts.get(code, 0) + 1

        rows_out.append(row)

    if duplicated_rows:
        warnings.append(
            {
                "row_id": "catalog",
                "field": "duplicados",
                "message": f"Se detectaron combinaciones duplicadas en {len(duplicated_rows)} filas",
            }
        )

    repeated_codes = sorted([(k, v) for k, v in code_counts.items() if v > 1], key=lambda x: x[1], reverse=True)
    if repeated_codes:
        sample_codes = ", ".join(code for code, _ in repeated_codes[:10])
        warnings.append(
            {
                "row_id": "catalog",
                "field": "code",
                "message": f"Hay {len(repeated_codes)} códigos reutilizados en múltiples filas (ej.: {sample_codes})",
            }
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "rows_in_catalog": len(raw_rows),
            "rows_processed": len(rows_out),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "duplicate_combinations": len(duplicated_rows),
        },
        "errors": errors,
        "warnings": warnings,
    }
    return rows_out, report
