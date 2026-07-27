from __future__ import annotations


def to_float(value: object, default: float = 0.0) -> float:
    """Convert numeric values safely without changing the underlying data."""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if not raw:
        return default

    try:
        return float(raw.replace(",", "."))
    except (TypeError, ValueError):
        return default


def format_decimal(value: object, decimal_places: int = 2) -> str:
    """Format visible numeric values with a decimal comma."""
    amount = to_float(value)
    return f"{amount:.{decimal_places}f}".replace(".", ",")


def format_integer(value: object) -> str:
    """Format discrete counts and maturity levels without decimal places."""
    amount = int(round(to_float(value)))
    return f"{amount:,}".replace(",", ".")


def format_percentage(value: object, decimal_places: int = 2) -> str:
    return f"{format_decimal(value, decimal_places)}%"


def format_clp(value: object, unavailable: str) -> str:
    """Format CLP with periods for thousands and a decimal comma."""
    if value is None:
        return unavailable
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return unavailable

    formatted = f"{amount:,.2f}"
    localized = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"CLP $ {localized}"


def format_timestamp(value: object) -> str:
    """Render ISO-like timestamps in a form intended for people."""
    return str(value or "").strip().replace("T", " ", 1)
