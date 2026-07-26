from __future__ import annotations

import math
import re
import unicodedata
from typing import Any


HORIZON_MAX_MONTHS = {
    "short": 3,
    "medium": 6,
    "long": 12,
}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text).strip().lower()


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            clean = value.strip().replace(",", ".")
            if not clean:
                return None
            return float(clean)
        return float(value)
    except (TypeError, ValueError):
        return None


def horizon_months(entry: dict[str, object]) -> int:
    """Return the conservative upper duration of the entry's implementation horizon."""
    explicit_max = _to_float(entry.get("months_max"))
    if explicit_max is not None and explicit_max > 0:
        return max(1, int(math.ceil(explicit_max)))

    horizon = _norm(entry.get("plazo") or entry.get("horizon"))
    if "corto" in horizon or "short" in horizon:
        return HORIZON_MAX_MONTHS["short"]
    if "mediano" in horizon or "medium" in horizon:
        return HORIZON_MAX_MONTHS["medium"]
    if "largo" in horizon or "long" in horizon:
        return HORIZON_MAX_MONTHS["long"]
    return 1


def is_monthly_subscription(entry: dict[str, object]) -> bool:
    return _norm(entry.get("price_type")) == "subscription"


def estimate_cost_clp(
    entry: dict[str, object],
    *,
    fallback_cost: float | None = None,
    use_existing_estimate: bool = False,
) -> float | None:
    """Estimate a solution's CLP cost, projecting monthly prices across its horizon."""
    if use_existing_estimate and not is_monthly_subscription(entry):
        existing = _to_float(entry.get("cost_estimated_clp"))
        if existing is not None:
            return max(existing, 0.0)

    if _norm(entry.get("price_type")) == "free":
        return 0.0

    price = _to_float(entry.get("price_max_clp"))
    if price is None:
        price = _to_float(entry.get("price_min_clp"))
    if price is None:
        price = fallback_cost
    if price is None:
        return None

    amount = max(price, 0.0)
    if is_monthly_subscription(entry):
        amount *= horizon_months(entry)
    return amount
