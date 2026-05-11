from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from urllib.parse import urlparse


SCHEMA_VERSION = "catalog_v3.0"
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


def _parse_months(plazo_raw: object) -> tuple[str, int | None, int | None]:
    text = str(plazo_raw or "").strip()
    key = _norm(text)
    if not key:
        return "Sin clasificar", None, None
    if "corto" in key:
        return "Corto plazo", 1, 3
    if "mediano" in key:
        return "Mediano plazo", 3, 6
    if "largo" in key:
        return "Largo plazo", 6, 12

    nums = [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", text)]
    if not nums:
        return "Sin clasificar", None, None
    if "anio" in key:
        nums = [n * 12 for n in nums]
    if len(nums) >= 2:
        lo = int(min(nums))
        hi = int(max(nums))
    else:
        lo = int(nums[0])
        hi = int(nums[0])

    if hi <= 3:
        return "Corto plazo", lo, hi
    if hi <= 6:
        return "Mediano plazo", lo, hi
    if hi <= 12:
        return "Largo plazo", lo, hi
    return "Sin clasificar", lo, hi


def _extract_numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in re.findall(r"\d[\d\.,]*", text):
        digits = re.sub(r"[^\d]", "", m)
        if digits:
            out.append(float(digits))
    return out


def _parse_price(price_ref: object, price_clp: object, currency: object) -> dict[str, object]:
    raw_ref = str(price_ref or "").strip()
    raw_clp = str(price_clp or "").strip()
    raw_currency = str(currency or "").strip()
    raw = raw_clp or raw_ref
    key = _norm(f"{raw} {raw_currency}")

    if not raw:
        return {
            "price_display": "No informado",
            "price_type": "unknown",
            "currency": raw_currency or "CLP",
            "price_min_clp": None,
            "price_max_clp": None,
        }

    numbers = _extract_numbers(raw)
    is_free = (numbers and max(numbers) == 0) or any(w in key for w in ["gratis", "sin costo", "gratuito"])
    is_subscription = any(w in key for w in ["/month", "mensual", "month", "/mes", "mes"])
    is_variable = any(w in key for w in ["postulacion", "cofinanciado", "sin precio", "convenio", "proyecto"])
    is_range = len(numbers) >= 2 and ("-" in raw or "entre" in key or " a " in f" {key} ")

    if is_free:
        return {
            "price_display": "0 CLP",
            "price_type": "free",
            "currency": "CLP",
            "price_min_clp": 0.0,
            "price_max_clp": 0.0,
        }
    if not numbers:
        return {
            "price_display": raw,
            "price_type": "variable" if is_variable else "unknown",
            "currency": raw_currency or "CLP",
            "price_min_clp": None,
            "price_max_clp": None,
        }

    min_v = min(numbers)
    max_v = max(numbers)
    price_type = "range" if is_range else "fixed"
    if is_subscription:
        price_type = "subscription"
    if is_variable and price_type == "fixed":
        price_type = "variable"

    return {
        "price_display": raw,
        "price_type": price_type,
        "currency": raw_currency or "CLP",
        "price_min_clp": float(min_v),
        "price_max_clp": float(max_v),
    }


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
    horizon = str(row.get("horizon", "Sin clasificar"))
    pmax = row.get("price_max_clp")
    ptype = str(row.get("price_type", "unknown"))
    text_blob = " ".join([str(row.get("name", "")), str(row.get("description", "")), str(row.get("kpi", ""))])
    key = _norm(text_blob)

    impact = 2.6
    if any(w in key for w in ["automat", "integr", "analit", "tiempo real", "control"]):
        impact += 1.0
    if horizon == "Corto plazo":
        impact += 0.4
    if pmax is None:
        impact -= 0.3

    effort = 2.0
    if horizon == "Largo plazo":
        effort += 1.3
    elif horizon == "Mediano plazo":
        effort += 0.7
    if isinstance(pmax, float):
        if pmax > 500000:
            effort += 1.0
        elif pmax > 120000:
            effort += 0.6
    if ptype == "free":
        effort -= 0.7

    risk = 1.9 + ((effort - 2.0) * 0.7)
    if ptype in {"unknown", "variable"}:
        risk += 0.8
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

    fx_date = str(row.get("fx_date", "")).strip()
    if fx_date:
        try:
            parsed = datetime.strptime(fx_date, "%Y-%m-%d")
            age_days = (datetime.now() - parsed).days
            if age_days > 540:
                warnings.append(
                    {
                        "row_id": row_id,
                        "field": "fx_date",
                        "message": f"Referencia de tipo de cambio antigua ({age_days} días)",
                    }
                )
        except ValueError:
            warnings.append({"row_id": row_id, "field": "fx_date", "message": f"Fecha no parseable: {fx_date}"})

    if row.get("price_type") == "unknown":
        warnings.append({"row_id": row_id, "field": "price_type", "message": "Precio no estructurable"})

    return errors, warnings


def build_catalog_v3(raw_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows_out: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []

    seen_keys: set[tuple[str, str, str, str, str, str]] = set()
    code_counts: dict[str, int] = {}
    duplicated_rows: list[str] = []

    for raw in raw_rows:
        horizon, mmin, mmax = _parse_months(raw.get("plazo_raw"))
        price_data = _parse_price(raw.get("price_reference"), raw.get("price_clp_raw"), raw.get("currency"))
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
            "horizon": horizon,
            "months_min": mmin,
            "months_max": mmax,
            "currency": str(price_data["currency"]),
            "price_display": str(price_data["price_display"]),
            "price_type": str(price_data["price_type"]),
            "price_min_clp": price_data["price_min_clp"],
            "price_max_clp": price_data["price_max_clp"],
            "price_reference": str(raw.get("price_reference", "")).strip(),
            "price_clp_raw": str(raw.get("price_clp_raw", "")).strip(),
            "fx_date": str(raw.get("fx_date", "")).strip(),
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


def catalog_report_to_text(report: dict[str, object]) -> str:
    summary = report.get("summary", {})
    lines = [
        "REPORTE DE CALIDAD DE CATALOGO (v3)",
        f"Schema: {report.get('schema_version', 'catalog_v3.0')}",
        f"Generado: {report.get('generated_at', '')}",
        "",
        f"Filas en catalogo: {summary.get('rows_in_catalog', 0)}",
        f"Filas procesadas: {summary.get('rows_processed', 0)}",
        f"Errores: {summary.get('error_count', 0)}",
        f"Advertencias: {summary.get('warning_count', 0)}",
        f"Duplicados: {summary.get('duplicate_combinations', 0)}",
        "",
        "Top errores:",
    ]
    for row in report.get("errors", [])[:25]:
        lines.append(f"- [{row.get('row_id','?')}] {row.get('field','?')}: {row.get('message','')}")
    lines.append("")
    lines.append("Top advertencias:")
    for row in report.get("warnings", [])[:25]:
        lines.append(f"- [{row.get('row_id','?')}] {row.get('field','?')}: {row.get('message','')}")
    lines.append("")
    return "\n".join(lines)
