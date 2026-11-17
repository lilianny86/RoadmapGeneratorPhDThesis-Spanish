from __future__ import annotations

CATALOG_RELATIVE_PATH = (
    "assets/catalogo_soluciones/Catalogo_Soluciones_MM_Agro_Pymes_v4-Var_Proxies- revisado expertos INIA.xlsx"
)

BUDGET_OPTIONS = {
    "small": ("small_low", "small_medium", "small_high"),
    "medium": ("medium_low", "medium_medium", "medium_high"),
}
BUDGET_LABELS = {
    "es": {
        "small_low": "Hasta CLP 5.000.000",
        "small_medium": "Desde CLP 5.000.001 hasta CLP 10.000.000",
        "small_high": "Más de CLP 10.000.000",
        "medium_low": "Hasta CLP 10.000.000",
        "medium_medium": "Desde CLP 10.000.001 hasta CLP 20.000.000",
        "medium_high": "Más de CLP 20.000.000",
    },
    "en": {
        "small_low": "Up to CLP 5,000,000",
        "small_medium": "CLP 5,000,001 to CLP 10,000,000",
        "small_high": "More than CLP 10,000,000",
        "medium_low": "Up to CLP 10,000,000",
        "medium_medium": "CLP 10,000,001 to CLP 20,000,000",
        "medium_high": "More than CLP 20,000,000",
    },
}

EFFORT_ORDER = ("low", "medium", "high")
COMPATIBILITY = {
    "small_low": ("compatible", "conditional_effort", "not_compatible"),
    "small_medium": ("compatible", "compatible", "conditional_effort"),
    "small_high": ("compatible", "compatible", "compatible"),
    "medium_low": ("compatible", "compatible", "conditional_effort"),
    "medium_medium": ("compatible", "compatible", "compatible"),
    "medium_high": ("compatible", "compatible", "compatible"),
}

CATALOG_EFFORT = {"Bajo": "low", "Medio": "medium", "Alto": "high", "No evaluable": "not_assessable"}
CATALOG_FINANCING = {
    "Directa": "direct", "Gratuita": "free", "Cofinanciable": "cofinancing",
    "Requiere cotización": "quotation_required",
}
ECONOMIC_LABELS = {
    "es": {
        **{code: label for label, code in CATALOG_EFFORT.items()},
        **{code: label for label, code in CATALOG_FINANCING.items()},
        "direct": "Financiamiento directo",
        "free": "Acceso gratuito",
        "compatible": "Compatible según la matriz",
        "conditional_effort": "Condicionada al esfuerzo económico",
        "cofinancing_pending": "Sujeta a postulación y adjudicación",
        "quotation_pending": "Requiere cotización",
        "not_compatible": "No compatible",
        "insufficient_evidence": "Esfuerzo económico no evaluable",
    },
    "en": {
        "low": "Low", "medium": "Medium", "high": "High", "not_assessable": "Not assessable",
        "direct": "Direct financing", "free": "Free access", "cofinancing": "Co-financing option",
        "quotation_required": "Quotation required", "compatible": "Compatible under the matrix",
        "conditional_effort": "Conditional on economic effort",
        "cofinancing_pending": "Subject to application and award",
        "quotation_pending": "Quotation required", "not_compatible": "Not compatible",
        "insufficient_evidence": "Economic effort not assessable",
    },
}


def classify_economic_fit(capacity: str, effort: str, financing: str) -> str:
    if financing == "quotation_required":
        return "quotation_pending"
    if financing == "cofinancing":
        return "cofinancing_pending"
    if financing in {"direct", "free"} and effort in EFFORT_ORDER:
        return dict(zip(EFFORT_ORDER, COMPATIBILITY[capacity]))[effort]
    return "insufficient_evidence"


def economic_label(code: object, language: str) -> str:
    return ECONOMIC_LABELS["en" if language == "en" else "es"].get(str(code), "")


def action_economics(action: dict[str, object], language: str) -> str:
    effort = economic_label(action.get("economic_effort"), language)
    status_code = action.get("selection_status")
    status = "" if status_code == "compatible" else economic_label(status_code, language)
    financing = economic_label(action.get("financing_mode"), language)
    fields = [f"{'Economic effort' if language == 'en' else 'Esfuerzo económico'}: {effort}"] if effort else []
    if financing and financing != status:
        fields.append(financing)
    if status:
        fields.append(status)
    return " | ".join(fields)
