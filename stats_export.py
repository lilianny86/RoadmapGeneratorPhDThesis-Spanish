from __future__ import annotations

import csv
import hashlib
import hmac
import io
import re
from datetime import datetime

from collections import Counter

from economic_policy import BUDGET_LABELS


CAPACITY_LABEL_ES = {"low": "Baja", "medium": "Media", "high": "Alta"}
ACTION_FIELDS = [
    ("compatible_actions", "Acciones compatibles", "Acciones compatibles por perfil y capacidad según la matriz."),
    ("effort_conditional_actions", "Acciones condicionadas por esfuerzo", "Acciones de mayor esfuerzo sin alternativa compatible de menor esfuerzo para la transición."),
    ("cofinancing_actions", "Acciones sujetas a cofinanciamiento", "Acciones pendientes de postulación y adjudicación."),
    ("quotation_actions", "Acciones que requieren cotización", "Acciones pendientes de confirmación comercial."),
    ("low_effort_actions", "Acciones de esfuerzo económico bajo", "Acciones cuyo esfuerzo económico integral es bajo."),
    ("medium_effort_actions", "Acciones de esfuerzo económico medio", "Acciones cuyo esfuerzo económico integral es medio."),
    ("high_effort_actions", "Acciones de esfuerzo económico alto", "Acciones cuyo esfuerzo económico integral es alto."),
    ("unassessed_effort_actions", "Acciones de esfuerzo económico no evaluable", "Acciones sin evidencia suficiente para clasificar el esfuerzo."),
]
TRANSITION_FIELDS = [
    ("matched_transitions_total", "Transiciones con coincidencia en catálogo", "Transiciones requeridas con al menos una coincidencia estricta."),
    ("conditional_transitions_total", "Transiciones con alternativa condicionada", "Transiciones sin acción compatible cuya alternativa seleccionada requiere confirmación."),
    ("economic_excluded_transitions_total", "Transiciones no compatibles con la matriz", "Transiciones cuyos candidatos directos o gratuitos fueron incompatibles con la capacidad relativa."),
    ("insufficient_evidence_transitions_total", "Transiciones sin evidencia económica suficiente", "Transiciones que no pudieron priorizarse por falta de datos económicos suficientes."),
    ("selection_limited_transitions_total", "Transiciones limitadas por reglas de selección", "Transiciones sin acción compatible o condicionada debido a otras reglas de selección."),
    ("catalog_missing_transitions_total", "Transiciones sin solución en catálogo", "Transiciones para las que el catálogo no entregó candidatos."),
]


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
    ("budget_capacity", "Capacidad presupuestaria relativa", "Categoría del rango dentro del perfil de empresa; no es un tope de gasto.", "Baja, Media o Alta"),
    ("global_target_level", "Nivel objetivo global", "Nivel de madurez objetivo seleccionado antes del cuestionario.", "Número entero"),
    ("questionnaire_instrument_version", "Versión del cuestionario", "Versión del instrumento que originó las respuestas.", "Texto"),
    ("engine_version", "Versión del motor de recomendaciones", "Versión del algoritmo que priorizó las soluciones.", "Texto"),
    ("catalog_schema_version", "Versión del catálogo de soluciones", "Versión del esquema del catálogo consultado.", "Texto"),
    ("questionnaire_kpis_total", "KPI respondidos", "Cantidad de KPI del cuestionario aplicable a la empresa.", "Número entero"),
    ("kpis_with_gap", "KPI con brecha", "KPI cuyo nivel seleccionado está bajo la meta aplicable.", "Número entero"),
    ("kpis_at_or_above_target", "KPI sin brecha hacia la meta", "KPI que ya alcanza o supera la meta aplicable.", "Número entero"),
    ("weighted_gap_total", "Brecha ponderada total", "Suma de las brechas por KPI multiplicadas por su peso.", "Número decimal"),
    ("current_maturity_score", "Puntaje de madurez actual", "Promedio ponderado de los niveles seleccionados.", "Número decimal"),
    ("selected_target_maturity_score", "Puntaje de referencia de la meta seleccionada", "Promedio ponderado asociado al nivel objetivo seleccionado antes de conservar los KPI que ya estaban sobre esa meta.", "Número decimal"),
    ("target_maturity_score", "Puntaje de madurez objetivo ajustado", "Promedio ponderado de la meta aplicable al caso; conserva el nivel actual de los KPI que ya superan la meta seleccionada.", "Número decimal"),
    ("maturity_gap", "Brecha global de madurez pendiente", "Diferencia no negativa entre el puntaje objetivo ajustado y el puntaje actual.", "Número decimal"),
    ("target_progress_pct", "Avance hacia la meta", "Proporción de transiciones de madurez ya cumplidas, ponderada por KPI. Solo alcanza 100% cuando no quedan brechas.", "Porcentaje entre 0 y 100"),
    ("candidate_solutions_total", "Soluciones candidatas", "Soluciones del catálogo que llegaron a la etapa de optimización.", "Número entero"),
    ("recommendations_total", "Recomendaciones seleccionadas", "Acciones incluidas en el roadmap final.", "Número entero"),
    *((key, label, definition, "Número entero") for key, label, definition in ACTION_FIELDS),
    ("short_term_count", "Acciones de corto plazo", "Recomendaciones clasificadas en el horizonte de corto plazo.", "Número entero"),
    ("medium_term_count", "Acciones de mediano plazo", "Recomendaciones clasificadas en el horizonte de mediano plazo.", "Número entero"),
    ("long_term_count", "Acciones de largo plazo", "Recomendaciones clasificadas en el horizonte de largo plazo.", "Número entero"),
    ("unclassified_count", "Acciones sin plazo clasificado", "Recomendaciones sin horizonte temporal reconocido.", "Número entero"),
    ("required_transitions_total", "Transiciones requeridas", "Cambios de nivel necesarios para cerrar las brechas detectadas.", "Número entero"),
    ("covered_transitions_total", "Transiciones con acción compatible", "Transiciones requeridas con al menos una acción compatible.", "Número entero"),
    ("uncovered_transitions_total", "Transiciones sin acción compatible", "Transiciones requeridas sin acción compatible, aunque exista una alternativa condicionada.", "Número entero"),
    ("transition_coverage_ratio", "Cobertura con acciones compatibles", "Proporción de transiciones requeridas con una acción compatible.", "Proporción entre 0 y 1"),
    *((key, label, definition, "Número entero") for key, label, definition in TRANSITION_FIELDS),
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
    ("budget_capacity", "Capacidad presupuestaria relativa", "Categoría del rango dentro del perfil de empresa; no es un tope de gasto.", "Baja, Media o Alta"),
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
    ("covered_transitions_total", "Transiciones del KPI con acción compatible", "Cambios de nivel del KPI con al menos una acción compatible.", "Número entero"),
    ("uncovered_transitions_total", "Transiciones del KPI sin acción compatible", "Cambios de nivel del KPI sin acción compatible, aunque exista una alternativa condicionada.", "Número entero"),
    ("transition_coverage_ratio", "Cobertura del KPI con acciones compatibles", "Proporción de cambios de nivel del KPI con una acción compatible.", "Proporción entre 0 y 1"),
    *((key, label, definition, "Número entero") for key, label, definition in TRANSITION_FIELDS),
    ("recommendations_total", "Recomendaciones del KPI", "Cantidad de acciones del roadmap relacionadas con este KPI.", "Número entero"),
    *((key, label, definition, "Número entero") for key, label, definition in ACTION_FIELDS),
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
    effort = Counter(row.get("economic_effort") for row in entries)
    status = Counter(row.get("selection_status") for row in entries)
    return {
        "total": len(entries),
        "horizons": _horizon_counts(entries),
        "compatible_actions": status["compatible"],
        "effort_conditional_actions": status["conditional_effort"],
        "cofinancing_actions": status["cofinancing_pending"],
        "quotation_actions": status["quotation_pending"],
        "low_effort_actions": effort["low"],
        "medium_effort_actions": effort["medium"],
        "high_effort_actions": effort["high"],
        "unassessed_effort_actions": effort["not_assessable"],
    }


def _transition_metrics(outcomes: list[dict[str, object]]) -> dict[str, int]:
    counts = Counter(row.get("status") for row in outcomes)
    return {
        "matched_transitions_total": len(outcomes) - counts["no_catalog_match"],
        "conditional_transitions_total": sum(counts[s] for s in ("conditional_effort", "cofinancing_pending", "quotation_pending")),
        "economic_excluded_transitions_total": counts["not_compatible"],
        "insufficient_evidence_transitions_total": counts["insufficient_evidence"],
        "selection_limited_transitions_total": counts["selection_constraints"],
        "catalog_missing_transitions_total": counts["no_catalog_match"],
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
    catalog_summary = _as_dict(result.get("catalog_summary"))

    current = _to_float(result.get("current_score")) or 0.0
    target = _to_float(result.get("target_score")) or 0.0
    entry_metrics = _entry_metrics(entries)
    horizon_counts = entry_metrics["horizons"]
    outcomes = list(_as_dict(engine_summary.get("transition_outcomes")).values())
    required_transitions = len(outcomes)
    covered_transitions = sum(row.get("status") == "compatible" for row in outcomes)
    uncovered_transitions = max(required_transitions - covered_transitions, 0)
    transition_coverage = round(covered_transitions / required_transitions, 4) if required_transitions else ""

    kpis_with_gap = sum(1 for row in assessments if _to_int(row.get("gap")) > 0)
    kpis_at_or_above_target = len(assessments) - kpis_with_gap

    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "case_id": _case_id(generated_at=generated_at, company_type=company_type, payload=payload),
        "participant_code": str(participant_code).strip(),
        "company_size": company_type,
        "budget_range": BUDGET_LABELS["es"].get(budget_range, budget_range),
        "budget_range_code": budget_range,
        "budget_capacity": CAPACITY_LABEL_ES.get(budget_range.rsplit("_", 1)[-1], ""),
        "global_target_level": _to_int(result.get("target_level_index")),
        "questionnaire_instrument_version": str(result.get("questionnaire_instrument_version", "")),
        "engine_version": str(engine_summary.get("engine_version", "")),
        "catalog_schema_version": str(catalog_summary.get("schema_version", "")),
        "questionnaire_kpis_total": len(assessments),
        "kpis_with_gap": kpis_with_gap,
        "kpis_at_or_above_target": kpis_at_or_above_target,
        "weighted_gap_total": round(sum(_to_float(row.get("priority")) or 0.0 for row in assessments), 4),
        "current_maturity_score": round(current, 4),
        "selected_target_maturity_score": round(_to_float(result.get("selected_target_score")) or target, 4),
        "target_maturity_score": round(target, 4),
        "maturity_gap": round(target - current, 4),
        "target_progress_pct": round(_to_float(result.get("target_progress_pct")) or 0.0, 4),
        "candidate_solutions_total": _to_int(engine_summary.get("candidate_count")),
        "recommendations_total": entry_metrics["total"],
        **{key: entry_metrics[key] for key, _, _ in ACTION_FIELDS},
        "short_term_count": horizon_counts["short"],
        "medium_term_count": horizon_counts["medium"],
        "long_term_count": horizon_counts["long"],
        "unclassified_count": horizon_counts["unclassified"],
        "required_transitions_total": required_transitions,
        "covered_transitions_total": covered_transitions,
        "uncovered_transitions_total": uncovered_transitions,
        "transition_coverage_ratio": transition_coverage,
        **_transition_metrics(outcomes),
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

    engine = _as_dict(result.get("engine_summary"))
    outcomes_by_question: dict[int, list[dict[str, object]]] = {}
    for outcome in _as_dict(engine.get("transition_outcomes")).values():
        outcomes_by_question.setdefault(_to_int(outcome.get("question_number")), []).append(outcome)

    detail_rows: list[dict[str, object]] = []
    for row in _assessment_rows(result):
        question_number = _to_int(row.get("question_number"))
        kpi_entries = by_question.get(question_number, [])
        metrics = _entry_metrics(kpi_entries)
        required = _to_int(row.get("gap"))
        outcomes = outcomes_by_question.get(question_number, [])
        covered = sum(outcome.get("status") == "compatible" for outcome in outcomes)
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
                "budget_capacity": record.get("budget_capacity", ""),
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
                **{key: metrics[key] for key, _, _ in ACTION_FIELDS},
                **_transition_metrics(outcomes),
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


def build_statistical_csv_documents(payload: dict[str, object], record: dict[str, object]) -> dict[str, bytes]:
    case_id = record["case_id"]
    return {
        f"rogen_estadisticas_resumen_{case_id}.csv": build_statistical_csv_bytes(record),
        f"rogen_estadisticas_detalle_kpi_{case_id}.csv": build_kpi_statistical_csv_bytes(
            build_kpi_statistical_records(payload, record)
        ),
        "rogen_estadisticas_guia_de_variables.csv": build_statistical_data_guide_csv_bytes(),
    }
