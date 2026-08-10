from __future__ import annotations

import csv
import hashlib
import hmac
import io
import re
from datetime import datetime

from costing import estimate_cost_clp


BUDGET_RANGE_NUMERIC = {
    "up_to_1m": 1,
    "between_1m_3m": 2,
    "between_3m_5m": 3,
    "between_1m_5m": 2,
    "between_5m_10m": 3,
}

BUDGET_RANGE_LABEL_ES = {
    "up_to_1m": "Hasta CLP $ 1.000.000,00",
    "between_1m_3m": "Desde CLP $ 1.000.001,00 hasta CLP $ 3.000.000,00",
    "between_3m_5m": "Desde CLP $ 3.000.001,00 hasta CLP $ 5.000.000,00",
    "between_1m_5m": "Desde CLP $ 1.000.001,00 hasta CLP $ 5.000.000,00",
    "between_5m_10m": "Desde CLP $ 5.000.001,00 hasta CLP $ 10.000.000,00",
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
    if budget_range == "between_1m_3m":
        return 3_000_000.0
    if budget_range == "between_3m_5m":
        return 5_000_000.0
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


def build_stable_participant_code(company_rut: object, *, secret: str) -> str:
    """Return a stable, non-reversible research code from the company's RUT."""
    normalized_rut = re.sub(r"[^0-9Kk]", "", str(company_rut or "")).upper()
    if len(normalized_rut) < 2:
        raise ValueError("A valid company RUT is required to create the statistical participant code.")

    secret_value = str(secret or "").strip()
    if not secret_value:
        raise ValueError("ROADMAP_PARTICIPANT_SALT is required for stable statistical participant codes.")

    digest = hmac.new(
        secret_value.encode("utf-8"),
        normalized_rut.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().upper()[:16]
    return f"RGN-P-{digest}"


SUMMARY_VARIABLES = [
    ("generated_at", "Fecha y hora de generación", "Momento en que RoGen generó el roadmap.", "AAAA-MM-DDTHH:MM:SS"),
    ("case_id", "ID anónimo del caso", "Identificador técnico no derivado de nombre, RUT ni correo.", "RGN-AAAAMMDD-XXXXXXXX"),
    ("participant_code", "Código seudonimizado estable de empresa", "Identificador estable derivado del RUT normalizado mediante HMAC con una clave privada. Permite vincular mediciones de una misma empresa sin exponer su identidad.", "RGN-P-XXXXXXXXXXXXXXXX"),
    ("company_size", "Tamaño de empresa", "Tipo de empresa seleccionado en la aplicación.", "Pequeña empresa o Mediana empresa"),
    ("budget_range", "Rango de presupuesto seleccionado", "Texto del rango anual elegido por la persona entrevistada.", "Texto en CLP"),
    ("budget_range_code", "Código del rango de presupuesto", "Código estable del rango para análisis estadístico.", "Texto"),
    ("budget_range_numeric", "Nivel ordinal del rango de presupuesto", "Orden del rango de presupuesto, de menor a mayor.", "Número entero"),
    ("budget_cap_clp", "Tope de presupuesto (CLP)", "Máximo anual que el motor usa para seleccionar recomendaciones.", "Pesos chilenos"),
    ("global_target_level", "Nivel objetivo global", "Nivel de madurez objetivo seleccionado antes del cuestionario.", "Número entero"),
    ("questionnaire_instrument_version", "Versión del cuestionario", "Versión del instrumento que originó las respuestas.", "Texto"),
    ("engine_version", "Versión del motor de recomendaciones", "Versión del algoritmo que priorizó las soluciones.", "Texto"),
    ("catalog_schema_version", "Versión del catálogo de soluciones", "Versión del esquema del catálogo consultado.", "Texto"),
    ("questionnaire_kpis_total", "KPI respondidos", "Cantidad de KPI del cuestionario aplicable a la empresa.", "Número entero"),
    ("kpis_with_gap", "KPI con brecha", "KPI cuyo nivel seleccionado está bajo la meta aplicable.", "Número entero"),
    ("kpis_at_or_above_target", "KPI sin brecha hacia la meta", "KPI que ya alcanza o supera la meta aplicable.", "Número entero"),
    ("weighted_gap_total", "Brecha ponderada total", "Suma de las brechas por KPI multiplicadas por su peso.", "Número decimal"),
    ("current_maturity_score", "Puntaje de madurez actual", "Promedio ponderado de los niveles seleccionados.", "Número decimal"),
    ("target_maturity_score", "Puntaje de madurez objetivo", "Promedio ponderado asociado al nivel objetivo seleccionado.", "Número decimal"),
    ("maturity_gap", "Brecha global de madurez", "Diferencia entre el puntaje objetivo y el puntaje actual.", "Número decimal"),
    ("candidate_solutions_total", "Soluciones candidatas", "Soluciones del catálogo que llegaron a la etapa de optimización.", "Número entero"),
    ("recommendations_total", "Recomendaciones seleccionadas", "Acciones incluidas en el roadmap final.", "Número entero"),
    ("recommendations_with_value", "Recomendaciones con costo conocido", "Acciones con un costo calculable para el presupuesto.", "Número entero"),
    ("recommendations_without_value", "Recomendaciones con costo no confirmado", "Acciones cuyo precio requiere cotización o no se pudo verificar.", "Número entero"),
    ("short_term_count", "Acciones de corto plazo", "Recomendaciones clasificadas en el horizonte de corto plazo.", "Número entero"),
    ("medium_term_count", "Acciones de mediano plazo", "Recomendaciones clasificadas en el horizonte de mediano plazo.", "Número entero"),
    ("long_term_count", "Acciones de largo plazo", "Recomendaciones clasificadas en el horizonte de largo plazo.", "Número entero"),
    ("unclassified_count", "Acciones sin plazo clasificado", "Recomendaciones sin horizonte temporal reconocido.", "Número entero"),
    ("recommendations_known_value_total_clp", "Costo conocido de las recomendaciones (CLP)", "Suma de los costos calculables de las acciones seleccionadas.", "Pesos chilenos"),
    ("engine_used_budget_clp", "Presupuesto usado por el motor (CLP)", "Costo que el motor considera al aplicar el tope presupuestario.", "Pesos chilenos"),
    ("budget_remaining_clp", "Presupuesto remanente (CLP)", "Diferencia no utilizada entre el tope y el presupuesto usado por el motor.", "Pesos chilenos"),
    ("budget_utilization_ratio", "Uso del presupuesto", "Proporción del tope presupuestario utilizada por el motor.", "Proporción entre 0 y 1"),
    ("required_transitions_total", "Transiciones requeridas", "Cambios de nivel necesarios para cerrar las brechas detectadas.", "Número entero"),
    ("covered_transitions_total", "Transiciones cubiertas", "Transiciones requeridas con al menos una solución seleccionada.", "Número entero"),
    ("uncovered_transitions_total", "Transiciones no cubiertas", "Transiciones requeridas que quedaron sin solución seleccionada.", "Número entero"),
    ("transition_coverage_ratio", "Cobertura de transiciones", "Proporción de transiciones requeridas que fueron cubiertas.", "Proporción entre 0 y 1"),
    ("budget_excluded_transitions_total", "Transiciones excluidas por presupuesto", "Transiciones descartadas porque sus soluciones excedían el tope.", "Número entero"),
    ("catalog_missing_transitions_total", "Transiciones sin solución en catálogo", "Transiciones para las que el catálogo no entregó candidatos.", "Número entero"),
    ("catalog_error_count", "Errores detectados en catálogo", "Errores de validación encontrados al cargar el catálogo.", "Número entero"),
    ("catalog_warning_count", "Advertencias detectadas en catálogo", "Advertencias de calidad encontradas al cargar el catálogo.", "Número entero"),
]


KPI_DETAIL_VARIABLES = [
    ("generated_at", "Fecha y hora de generación", "Momento en que RoGen generó el roadmap.", "AAAA-MM-DDTHH:MM:SS"),
    ("case_id", "ID anónimo del caso", "Identificador técnico del caso para vincularlo con el resumen.", "RGN-AAAAMMDD-XXXXXXXX"),
    ("participant_code", "Código seudonimizado estable de empresa", "Identificador estable que permite vincular mediciones de una misma empresa sin exponer su identidad.", "RGN-P-XXXXXXXXXXXXXXXX"),
    ("company_size", "Tamaño de empresa", "Tipo de empresa seleccionado en la aplicación.", "Pequeña empresa o Mediana empresa"),
    ("budget_range", "Rango de presupuesto seleccionado", "Texto del rango anual elegido por la persona entrevistada.", "Texto en CLP"),
    ("budget_range_code", "Código del rango de presupuesto", "Código estable del rango para análisis estadístico.", "Texto"),
    ("budget_range_numeric", "Nivel ordinal del rango de presupuesto", "Orden del rango de presupuesto, de menor a mayor.", "Número entero"),
    ("global_target_level", "Nivel objetivo global", "Nivel de madurez objetivo seleccionado antes del cuestionario.", "Número entero"),
    ("questionnaire_instrument_version", "Versión del cuestionario", "Versión del instrumento que originó las respuestas.", "Texto"),
    ("question_number", "Número de pregunta", "Número de la pregunta asociada al KPI.", "Número entero"),
    ("domain", "Dominio", "Dominio del modelo de madurez al que pertenece el KPI.", "Texto"),
    ("kda", "Área clave de decisión (KDA)", "Área clave de decisión asociada al KPI.", "Texto"),
    ("kpi", "Indicador (KPI)", "Nombre del indicador evaluado.", "Texto"),
    ("kpi_weight", "Peso del KPI", "Ponderación definida para ese indicador en el modelo.", "Número decimal"),
    ("available_maturity_levels", "Niveles válidos del KPI", "Niveles disponibles para el KPI en el modelo; por ejemplo, 1|2|4.", "Lista separada por |"),
    ("selected_option_index", "Posición de la opción marcada", "Orden de la alternativa elegida dentro de las opciones de la pregunta.", "Número entero"),
    ("selected_maturity_level", "Nivel de madurez seleccionado", "Nivel asignado a la respuesta marcada en el cuestionario.", "Número entero"),
    ("target_maturity_level", "Nivel meta aplicable al KPI", "Meta del KPI según el nivel objetivo global y los niveles válidos del indicador.", "Número entero"),
    ("effective_target_maturity_level", "Meta efectiva del KPI", "Meta usada para análisis sin reducir un KPI que ya está sobre la meta global.", "Número entero"),
    ("gap_steps", "Brecha en pasos de madurez", "Cantidad de transiciones de nivel pendientes para llegar a la meta efectiva.", "Número entero"),
    ("weighted_gap_priority", "Prioridad ponderada de la brecha", "Brecha en pasos multiplicada por el peso del KPI.", "Número decimal"),
    ("requires_action", "Requiere acción", "Indica si el KPI tiene una brecha que requiere una acción en el roadmap.", "0 = no; 1 = sí"),
    ("required_transitions_total", "Transiciones requeridas del KPI", "Cantidad de cambios de nivel que el KPI necesita.", "Número entero"),
    ("covered_transitions_total", "Transiciones cubiertas del KPI", "Cambios de nivel del KPI con una solución seleccionada.", "Número entero"),
    ("uncovered_transitions_total", "Transiciones no cubiertas del KPI", "Cambios de nivel del KPI que quedaron sin solución seleccionada.", "Número entero"),
    ("transition_coverage_ratio", "Cobertura de transiciones del KPI", "Proporción de cambios de nivel del KPI cubiertos por el roadmap.", "Proporción entre 0 y 1"),
    ("recommendations_total", "Recomendaciones del KPI", "Cantidad de acciones del roadmap relacionadas con este KPI.", "Número entero"),
    ("recommendations_with_value", "Recomendaciones del KPI con costo conocido", "Acciones de este KPI con costo calculable.", "Número entero"),
    ("recommendations_without_value", "Recomendaciones del KPI con costo no confirmado", "Acciones de este KPI cuyo costo requiere cotización o no se verificó.", "Número entero"),
    ("recommendations_known_value_total_clp", "Costo conocido del KPI (CLP)", "Suma de costos calculables de las acciones relacionadas con el KPI.", "Pesos chilenos"),
    ("short_term_count", "Acciones de corto plazo del KPI", "Acciones de este KPI en el horizonte de corto plazo.", "Número entero"),
    ("medium_term_count", "Acciones de mediano plazo del KPI", "Acciones de este KPI en el horizonte de mediano plazo.", "Número entero"),
    ("long_term_count", "Acciones de largo plazo del KPI", "Acciones de este KPI en el horizonte de largo plazo.", "Número entero"),
    ("unclassified_count", "Acciones sin plazo clasificado del KPI", "Acciones de este KPI sin horizonte temporal reconocido.", "Número entero"),
]

SUMMARY_FIELDNAMES = [key for key, _, _, _ in SUMMARY_VARIABLES]
SUMMARY_CSV_HEADERS = [label for _, label, _, _ in SUMMARY_VARIABLES]
KPI_DETAIL_FIELDNAMES = [key for key, _, _, _ in KPI_DETAIL_VARIABLES]
KPI_DETAIL_CSV_HEADERS = [label for _, label, _, _ in KPI_DETAIL_VARIABLES]
GUIDE_CSV_HEADERS = ["Archivo CSV", "Columna", "Qué guarda", "Formato o interpretación"]


def _to_int(value: object, default: int = 0) -> int:
    numeric = _to_float(value)
    return int(numeric) if numeric is not None else default


def _as_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _as_dict_list(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _assessment_rows(result: dict[str, object]) -> list[dict[str, object]]:
    """Return all assessed KPIs; older payloads only expose gap KPI rows."""
    rows = _as_dict_list(result.get("kpi_assessment_results"))
    return rows if rows else _as_dict_list(result.get("kpi_results"))


def _available_levels_text(value: object) -> str:
    if not isinstance(value, list):
        return ""
    return "|".join(str(_to_int(level)) for level in value)


def _horizon_counts(entries: list[dict[str, object]]) -> dict[str, int]:
    counts = {"short": 0, "medium": 0, "long": 0, "unclassified": 0}
    for row in entries:
        counts[_horizon_key(row.get("plazo"))] += 1
    return counts


def _entry_metrics(entries: list[dict[str, object]]) -> dict[str, object]:
    values = [_price_value_clp(row) for row in entries]
    known_values = [value for value in values if value is not None]
    return {
        "total": len(entries),
        "known_count": len(known_values),
        "unknown_count": len(entries) - len(known_values),
        "known_total": round(sum(known_values), 2),
        "horizons": _horizon_counts(entries),
    }


def build_statistical_record(
    payload: dict[str, object],
    *,
    company_type: str,
    budget_range: str,
    participant_code: str,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    generated_at = generated_at or datetime.now()
    result = _as_dict(payload.get("result")) if isinstance(payload, dict) else {}
    entries = _as_dict_list(result.get("roadmap_entries"))
    assessments = _assessment_rows(result)
    engine_summary = _as_dict(result.get("engine_summary"))
    engine_config = _as_dict(engine_summary.get("config"))
    catalog_summary = _as_dict(result.get("catalog_summary"))

    current = _to_float(result.get("current_score")) or 0.0
    target = _to_float(result.get("target_score")) or 0.0
    entry_metrics = _entry_metrics(entries)
    horizon_counts = entry_metrics["horizons"]
    budget_cap = _to_float(engine_config.get("budget_total_clp")) or _budget_cap_clp(str(budget_range or ""))
    used_budget = _to_float(engine_summary.get("used_budget_total_clp"))
    if used_budget is None:
        used_budget = float(entry_metrics["known_total"])
    budget_remaining = round(max(budget_cap - used_budget, 0.0), 2) if budget_cap is not None else ""
    budget_utilization = round(used_budget / budget_cap, 4) if budget_cap else ""

    required_transitions = _to_int(engine_summary.get("required_transition_count"))
    if not required_transitions:
        required_transitions = sum(_to_int(row.get("gap")) for row in assessments)
    if "covered_required_transition_count" in engine_summary:
        covered_transitions = _to_int(engine_summary.get("covered_required_transition_count"))
    else:
        covered_transitions = min(
            required_transitions,
            len(
                {
                    str(entry.get("required_transition_key", "")).strip()
                    for entry in entries
                    if str(entry.get("required_transition_key", "")).strip()
                }
            ),
        )
    uncovered_transitions = max(required_transitions - covered_transitions, 0)
    transition_coverage = round(covered_transitions / required_transitions, 4) if required_transitions else ""

    kpis_with_gap = sum(1 for row in assessments if _to_int(row.get("gap")) > 0)
    kpis_at_or_above_target = len(assessments) - kpis_with_gap

    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "case_id": _case_id(generated_at=generated_at, company_type=company_type, payload=payload),
        "participant_code": str(participant_code).strip(),
        "company_size": company_type,
        "budget_range": BUDGET_RANGE_LABEL_ES.get(str(budget_range or ""), str(budget_range or "")),
        "budget_range_code": str(budget_range or ""),
        "budget_range_numeric": BUDGET_RANGE_NUMERIC.get(str(budget_range or ""), ""),
        "budget_cap_clp": round(budget_cap, 2) if budget_cap is not None else "",
        "global_target_level": _to_int(result.get("target_level_index")),
        "questionnaire_instrument_version": str(result.get("questionnaire_instrument_version", "")),
        "engine_version": str(engine_summary.get("engine_version", "")),
        "catalog_schema_version": str(catalog_summary.get("schema_version", "")),
        "questionnaire_kpis_total": len(assessments),
        "kpis_with_gap": kpis_with_gap,
        "kpis_at_or_above_target": kpis_at_or_above_target,
        "weighted_gap_total": round(sum(_to_float(row.get("priority")) or 0.0 for row in assessments), 4),
        "current_maturity_score": round(current, 4),
        "target_maturity_score": round(target, 4),
        "maturity_gap": round(target - current, 4),
        "candidate_solutions_total": _to_int(engine_summary.get("candidate_count")),
        "recommendations_total": entry_metrics["total"],
        "recommendations_with_value": entry_metrics["known_count"],
        "recommendations_without_value": entry_metrics["unknown_count"],
        "short_term_count": horizon_counts["short"],
        "medium_term_count": horizon_counts["medium"],
        "long_term_count": horizon_counts["long"],
        "unclassified_count": horizon_counts["unclassified"],
        "recommendations_known_value_total_clp": entry_metrics["known_total"],
        "engine_used_budget_clp": round(used_budget, 2),
        "budget_remaining_clp": budget_remaining,
        "budget_utilization_ratio": budget_utilization,
        "required_transitions_total": required_transitions,
        "covered_transitions_total": covered_transitions,
        "uncovered_transitions_total": uncovered_transitions,
        "transition_coverage_ratio": transition_coverage,
        "budget_excluded_transitions_total": len(engine_summary.get("budget_excluded_required_transitions", [])) if isinstance(engine_summary.get("budget_excluded_required_transitions"), list) else 0,
        "catalog_missing_transitions_total": len(engine_summary.get("missing_catalog_transitions", [])) if isinstance(engine_summary.get("missing_catalog_transitions"), list) else 0,
        "catalog_error_count": _to_int(catalog_summary.get("error_count")),
        "catalog_warning_count": _to_int(catalog_summary.get("warning_count")),
    }


def build_kpi_statistical_records(payload: dict[str, object], record: dict[str, object]) -> list[dict[str, object]]:
    """Create a pseudonymized longitudinal record for every questionnaire KPI."""
    result = _as_dict(payload.get("result")) if isinstance(payload, dict) else {}
    entries = _as_dict_list(result.get("roadmap_entries"))
    by_question: dict[int, list[dict[str, object]]] = {}
    for entry in entries:
        question_number = _to_int(entry.get("question_number"))
        by_question.setdefault(question_number, []).append(entry)

    detail_rows: list[dict[str, object]] = []
    for row in _assessment_rows(result):
        question_number = _to_int(row.get("question_number"))
        kpi_entries = by_question.get(question_number, [])
        metrics = _entry_metrics(kpi_entries)
        required = _to_int(row.get("gap"))
        covered = min(required, len({str(entry.get("transition", "")).strip() for entry in kpi_entries if str(entry.get("transition", "")).strip()}))
        coverage = round(covered / required, 4) if required else ""
        horizons = metrics["horizons"]
        detail_rows.append(
            {
                "generated_at": record.get("generated_at", ""),
                "case_id": record.get("case_id", ""),
                "participant_code": record.get("participant_code", ""),
                "company_size": record.get("company_size", ""),
                "budget_range": record.get("budget_range", ""),
                "budget_range_code": record.get("budget_range_code", ""),
                "budget_range_numeric": record.get("budget_range_numeric", ""),
                "global_target_level": record.get("global_target_level", ""),
                "questionnaire_instrument_version": record.get("questionnaire_instrument_version", ""),
                "question_number": question_number,
                "domain": str(row.get("domain", "")),
                "kda": str(row.get("kda", "")),
                "kpi": str(row.get("kpi", "")),
                "kpi_weight": _to_float(row.get("weight")) or 0.0,
                "available_maturity_levels": _available_levels_text(row.get("available_levels")),
                "selected_option_index": _to_int(row.get("selected_option_index")),
                "selected_maturity_level": _to_int(row.get("selected_level", row.get("current_level"))),
                "target_maturity_level": _to_int(row.get("target_level")),
                "effective_target_maturity_level": _to_int(row.get("effective_target_level", row.get("target_level"))),
                "gap_steps": required,
                "weighted_gap_priority": _to_float(row.get("priority")) or 0.0,
                "requires_action": int(required > 0),
                "required_transitions_total": required,
                "covered_transitions_total": covered,
                "uncovered_transitions_total": max(required - covered, 0),
                "transition_coverage_ratio": coverage,
                "recommendations_total": metrics["total"],
                "recommendations_with_value": metrics["known_count"],
                "recommendations_without_value": metrics["unknown_count"],
                "recommendations_known_value_total_clp": metrics["known_total"],
                "short_term_count": horizons["short"],
                "medium_term_count": horizons["medium"],
                "long_term_count": horizons["long"],
                "unclassified_count": horizons["unclassified"],
            }
        )
    return detail_rows


def _friendly_csv_value(key: str, value: object) -> object:
    if key == "company_size":
        return {"small": "Pequeña empresa", "medium": "Mediana empresa"}.get(str(value), value)
    return value


def _friendly_csv_row(record: dict[str, object], variables: list[tuple[str, str, str, str]]) -> dict[str, object]:
    return {label: _friendly_csv_value(key, record.get(key, "")) for key, label, _, _ in variables}


def build_statistical_csv_bytes(record: dict[str, object]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=SUMMARY_CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(_friendly_csv_row(record, SUMMARY_VARIABLES))
    return buffer.getvalue().encode("utf-8-sig")


def build_kpi_statistical_csv_bytes(records: list[dict[str, object]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=KPI_DETAIL_CSV_HEADERS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(_friendly_csv_row(record, KPI_DETAIL_VARIABLES) for record in records)
    return buffer.getvalue().encode("utf-8-sig")


def build_statistical_data_guide_csv_bytes() -> bytes:
    """Explain every column included in the internal, pseudonymized exports."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=GUIDE_CSV_HEADERS)
    writer.writeheader()
    for file_name, variables in (
        ("Resumen estadístico", SUMMARY_VARIABLES),
        ("Detalle estadístico por KPI", KPI_DETAIL_VARIABLES),
    ):
        for _, label, description, data_format in variables:
            writer.writerow(
                {
                    "Archivo CSV": file_name,
                    "Columna": label,
                    "Qué guarda": description,
                    "Formato o interpretación": data_format,
                }
            )
    return buffer.getvalue().encode("utf-8-sig")
