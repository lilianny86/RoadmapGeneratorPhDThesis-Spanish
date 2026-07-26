from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import datetime

from costing import estimate_cost_clp


BUDGET_RANGE_NUMERIC = {
    "up_to_1m": 1,
    "between_1m_5m": 2,
    "between_5m_10m": 3,
}

BUDGET_RANGE_LABEL_ES = {
    "up_to_1m": "Hasta CLP 1.000.000",
    "between_1m_5m": "Desde CLP 1.000.001 a CLP 5.000.000",
    "between_5m_10m": "Desde CLP 5.000.001 a CLP 10.000.000",
}


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    cleaned = re.sub(r"[^0-9,.-]", "", text).replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _price_value_clp(row: dict[str, object]) -> float | None:
    if str(row.get("price_type", "")).strip().lower() in {"variable", "unknown"}:
        return None
    return estimate_cost_clp(row, use_existing_estimate=True)


def _budget_cap_clp(budget_range: str) -> float | None:
    if budget_range == "up_to_1m":
        return 1_000_000.0
    if budget_range == "between_1m_5m":
        return 5_000_000.0
    if budget_range == "between_5m_10m":
        return 10_000_000.0
    return None


def _horizon_key(value: object) -> str:
    text = str(value or "").strip().lower()
    if "corto" in text or "short" in text:
        return "short"
    if "mediano" in text or "medium" in text:
        return "medium"
    if "largo" in text or "long" in text:
        return "long"
    return "unclassified"


def _case_id(*, generated_at: datetime, company_type: str, payload: dict[str, object]) -> str:
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    seed = "|".join(
        [
            generated_at.isoformat(timespec="seconds"),
            str(company_type or ""),
            str(result.get("current_score", "")) if isinstance(result, dict) else "",
            str(result.get("target_score", "")) if isinstance(result, dict) else "",
            str(len(result.get("roadmap_entries", []))) if isinstance(result, dict) and isinstance(result.get("roadmap_entries", []), list) else "0",
        ]
    )
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8].upper()
    return f"RGN-{generated_at.strftime('%Y%m%d')}-{digest}"


def build_statistical_record(
    payload: dict[str, object],
    *,
    company_type: str,
    budget_range: str,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    generated_at = generated_at or datetime.now()
    result = payload.get("result", {}) if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        result = {}
    entries = result.get("roadmap_entries", [])
    if not isinstance(entries, list):
        entries = []

    current = _to_float(result.get("current_score")) or 0.0
    target = _to_float(result.get("target_score")) or 0.0
    values = [_price_value_clp(e) for e in entries if isinstance(e, dict)]
    known_values = [v for v in values if v is not None]
    unknown_count = max(len(entries) - len(known_values), 0)
    budget_cap = _budget_cap_clp(str(budget_range or ""))
    if budget_cap is None:
        budget_fit_count = len(entries)
    else:
        budget_fit_count = sum(1 for v in values if v is not None and v <= budget_cap)
    budget_fit_ratio = (budget_fit_count / len(entries)) if entries else 0.0

    horizon_counts = {"short": 0, "medium": 0, "long": 0, "unclassified": 0}
    for row in entries:
        if isinstance(row, dict):
            horizon_counts[_horizon_key(row.get("plazo"))] += 1

    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "case_id": _case_id(generated_at=generated_at, company_type=company_type, payload=payload),
        "company_size": company_type,
        "budget_range": BUDGET_RANGE_LABEL_ES.get(str(budget_range or ""), str(budget_range or "")),
        "budget_range_code": str(budget_range or ""),
        "budget_range_numeric": BUDGET_RANGE_NUMERIC.get(str(budget_range or ""), ""),
        "current_maturity_score": round(current, 4),
        "target_maturity_score": round(target, 4),
        "maturity_gap": round(target - current, 4),
        "recommendations_total": len(entries),
        "recommendations_with_value": len(known_values),
        "recommendations_without_value": unknown_count,
        "budget_fit_ratio": round(budget_fit_ratio, 4),
        "short_term_count": horizon_counts["short"],
        "medium_term_count": horizon_counts["medium"],
        "long_term_count": horizon_counts["long"],
        "unclassified_count": horizon_counts["unclassified"],
        "total_estimated_value_clp": round(sum(known_values), 2),
    }


def build_statistical_csv_bytes(record: dict[str, object]) -> bytes:
    buffer = io.StringIO(newline="")
    fieldnames = [
        "generated_at",
        "case_id",
        "company_size",
        "budget_range",
        "budget_range_code",
        "budget_range_numeric",
        "current_maturity_score",
        "target_maturity_score",
        "maturity_gap",
        "recommendations_total",
        "recommendations_with_value",
        "recommendations_without_value",
        "budget_fit_ratio",
        "short_term_count",
        "medium_term_count",
        "long_term_count",
        "unclassified_count",
        "total_estimated_value_clp",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(record)
    return buffer.getvalue().encode("utf-8-sig")
