from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from economic_policy import COMPATIBILITY, EFFORT_ORDER, classify_economic_fit


def _norm(value: object) -> str:
    t = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().lower()


def _horizon_order(plazo: str) -> int:
    horizon = _canonical_horizon(plazo)
    if horizon == "Short term":
        return 1
    if horizon == "Medium term":
        return 2
    if horizon == "Long term":
        return 3
    return 4


def _canonical_horizon(value: object) -> str:
    return {
        "corto plazo": "Short term", "short term": "Short term",
        "mediano plazo": "Medium term", "medium term": "Medium term",
        "largo plazo": "Long term", "long term": "Long term",
    }.get(_norm(value), "Unclassified")



def _to_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        if isinstance(value, str):
            clean = value.strip().replace(",", ".")
            if not clean:
                return default
            return float(clean)
        return float(value)
    except Exception:
        return default


@dataclass
class EngineConfig:
    max_recommendations: int = 60
    max_candidates_per_kpi: int = 6
    max_per_provider: int = 5
    max_per_kpi: int = 3
    enforce_unique_solution: bool = True
    diversify_domains: bool = True
    min_domain_coverage: int = 4
    weight_priority: float = 0.34
    weight_impact: float = 0.26
    weight_risk: float = 0.12
    weight_effort: float = 0.12
    penalty_repeat_provider: float = 0.08
    penalty_repeat_domain: float = 0.04
    budget_capacity: str = ""


@dataclass(frozen=True)
class _SelectionDecision:
    stage: str
    order: int
    score: float
    provider_penalty: float = 0.0
    domain_penalty: float = 0.0


_SELECTION_STAGE_SUMMARIES = {
    "compatible_transition": "Seleccionada como acción compatible para una transición requerida.",
    "conditional_transition": "Seleccionada como acción condicionada para una transición sin selección compatible.",
    "domain_diversification": "Seleccionada en la etapa de diversificación por dominio.",
    "supplementary_ranking": "Seleccionada en la clasificación complementaria de acciones compatibles.",
}


def _apply_dict_config(cfg: EngineConfig, raw: dict[str, Any]) -> EngineConfig:
    for key, value in raw.items():
        if not hasattr(cfg, key):
            continue
        current = getattr(cfg, key)
        if isinstance(current, bool):
            setattr(cfg, key, str(value).strip().lower() in {"1", "true", "yes", "on"})
        elif isinstance(current, int):
            iv = _to_float(value)
            if iv is not None:
                setattr(cfg, key, int(iv))
        elif isinstance(current, float):
            fv = _to_float(value)
            if fv is not None:
                setattr(cfg, key, float(fv))
        elif current is None:
            nv = _to_float(value, default=None)
            setattr(cfg, key, nv)
        else:
            setattr(cfg, key, value)
    return cfg


def build_engine_config(config_file: Path | None, overrides: dict[str, Any] | None = None) -> EngineConfig:
    cfg = EngineConfig()
    if config_file is not None and config_file.exists():
        raw = json.loads(config_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            cfg = _apply_dict_config(cfg, raw)
    if overrides:
        clean = {k: v for k, v in overrides.items() if v is not None}
        cfg = _apply_dict_config(cfg, clean)
    return cfg


def match_solutions(
    solutions: list[dict[str, object]],
    *,
    sol_hint: str,
    domain: str,
    kda: str,
    kpi: str,
    transition: str,
    origin: str,
    target: str,
    max_candidates: int,
    allow_kpi_fallback: bool = False,
) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    for s in solutions:
        if _norm(sol_hint) not in _norm(s.get("model", "")):
            continue
        if _norm(domain) != _norm(s.get("domain", "")):
            continue
        if _norm(kda) != _norm(s.get("kda", "")):
            continue
        if _norm(kpi) != _norm(s.get("kpi", "")):
            continue
        same_transition = _norm(s.get("transition", "")) == _norm(transition)
        same_levels = _norm(s.get("origin", "")) == _norm(origin) and _norm(s.get("target", "")) == _norm(target)
        if same_transition or same_levels:
            selected.append(s)

    if not selected and allow_kpi_fallback:
        for s in solutions:
            if _norm(sol_hint) in _norm(s.get("model", "")) and _norm(kpi) == _norm(s.get("kpi", "")):
                selected.append(s)

    selected.sort(
        key=lambda s: (
            int(s.get("option", 9999) or 9999),
            -float(s.get("impact_score", 0) or 0),
            _norm(s.get("name", "")),
        )
    )
    return selected[: max(1, max_candidates)]


def _score_candidates(candidates: list[dict[str, object]], cfg: EngineConfig) -> list[dict[str, object]]:
    max_priority = max((float(c.get("priority", 0) or 0) for c in candidates), default=0.0)
    scored: list[dict[str, object]] = []
    for candidate in candidates:
        row = dict(candidate)
        priority = float(row.get("priority", 0) or 0)
        impact = float(row.get("impact_score", 3.0) or 3.0)
        risk = float(row.get("risk_score", 3.0) or 3.0)
        effort = float(row.get("effort_score", 3.0) or 3.0)
        components = {
            "prioridad_kpi": cfg.weight_priority * (priority / max_priority if max_priority else 0.0),
            "impacto": cfg.weight_impact * (impact / 5.0),
            "riesgo": cfg.weight_risk * (1.0 - risk / 5.0),
            "esfuerzo": cfg.weight_effort * (1.0 - effort / 5.0),
        }
        row["_base_score"] = max(sum(components.values()), 0.0)
        row["_score_components"] = {key: round(value, 4) for key, value in components.items()}
        row["selection_status"] = classify_economic_fit(
            cfg.budget_capacity, str(row.get("economic_effort", "")), str(row.get("financing_mode", ""))
        )
        scored.append(row)
    return scored


def _economic_order(candidate: dict[str, object]) -> int:
    effort = candidate.get("economic_effort")
    return EFFORT_ORDER.index(effort) if effort in EFFORT_ORDER else len(EFFORT_ORDER)


def _solution_key(candidate: dict[str, object]) -> str:
    return _norm(candidate.get("catalog_solution_name") or candidate.get("solution_name"))



def _build_explanation(
    candidate: dict[str, object],
    *,
    rank: int,
    decision: _SelectionDecision,
) -> dict[str, object]:
    comps = candidate.get("_score_components", {})
    ordered = sorted(
        [(k, float(v)) for k, v in comps.items() if k != "factor_horizonte"],
        key=lambda x: x[1],
        reverse=True,
    )
    top_bits = [f"{k}={v:.2f}" for k, v in ordered[:2]]
    assumptions: list[str] = []
    if decision.provider_penalty > 0:
        assumptions.append("Penalización por proveedor repetido para mejorar diversidad.")
    if decision.domain_penalty > 0:
        assumptions.append("Penalización por dominio repetido para ampliar cobertura.")

    return {
        "rank": rank,
        "selection_order": decision.order,
        "selection_stage": decision.stage,
        "base_score": candidate["_base_score"],
        "selection_score": round(decision.score, 4),
        "applied_penalties": {
            "repeated_provider": decision.provider_penalty,
            "repeated_domain": decision.domain_penalty,
        },
        "summary": _SELECTION_STAGE_SUMMARIES[decision.stage],
        "main_drivers": top_bits,
        "component_scores": comps,
        "assumptions": assumptions,
        "dependencies": candidate.get("dependencies", []),
    }


def optimize_recommendations(
    candidate_entries: list[dict[str, object]],
    cfg: EngineConfig,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if cfg.budget_capacity not in COMPATIBILITY:
        raise ValueError("A valid profile-specific budget capacity is required.")
    scored = _score_candidates(candidate_entries, cfg)
    selected: list[dict[str, object]] = []
    provider_count: dict[str, int] = {}
    domain_count: dict[str, int] = {}
    kpi_count: dict[str, int] = {}
    used_solution_names: set[str] = set()
    selected_transitions: set[str] = set()
    required_transition_groups: dict[str, list[dict[str, object]]] = {}
    pending_states = {"conditional_effort", "cofinancing_pending", "quotation_pending"}
    for c in scored:
        key = str(c.get("required_transition_key", "")).strip()
        if key:
            required_transition_groups.setdefault(key, []).append(c)

    # An effort-based exception is only allowed without a lower-effort compatible match.
    for candidates in required_transition_groups.values():
        for candidate in candidates:
            if candidate["selection_status"] == "conditional_effort" and any(
                alternative["selection_status"] == "compatible"
                and _economic_order(alternative) < _economic_order(candidate)
                for alternative in candidates
            ):
                candidate["selection_status"] = "lower_effort_available"

    def kpi_key(c: dict[str, object]) -> str:
        return _norm(c.get("question_number") or c.get("kpi"))

    def can_select(c: dict[str, object]) -> bool:
        provider = _norm(c.get("provider"))
        kpi = kpi_key(c)
        name = _solution_key(c)
        return (
            len(selected) < cfg.max_recommendations
            and not c.get("_selected")
            and (not provider or provider_count.get(provider, 0) < cfg.max_per_provider)
            and (not kpi or kpi_count.get(kpi, 0) < cfg.max_per_kpi)
            and (not cfg.enforce_unique_solution or not name or name not in used_solution_names)
        )

    def register_selection(c: dict[str, object], decision: _SelectionDecision) -> None:
        provider = _norm(c.get("provider"))
        domain = _norm(c.get("catalog_domain") or c.get("domain"))
        kpi = kpi_key(c)
        name = _solution_key(c)
        provider_count[provider] = provider_count.get(provider, 0) + 1
        domain_count[domain] = domain_count.get(domain, 0) + 1
        kpi_count[kpi] = kpi_count.get(kpi, 0) + 1
        if name:
            used_solution_names.add(name)
        if c.get("required_transition_key"):
            selected_transitions.add(str(c["required_transition_key"]))
        c["_selected"] = True
        c["_selection_decision"] = decision
        selected.append(c)

    def rank(c: dict[str, object], score: float | None = None) -> tuple:
        return (
            -float(c["_base_score"] if score is None else score),
            _economic_order(c),
            _solution_key(c),
        )

    # Preserve the transition-first pass, reserving its first pass for compatible actions.
    for allowed, stage in (({"compatible"}, "compatible_transition"), (pending_states, "conditional_transition")):
        for key, candidates in sorted(required_transition_groups.items()):
            if key in selected_transitions:
                continue
            eligible = [c for c in candidates if c["selection_status"] in allowed and can_select(c)]
            if eligible:
                best = min(eligible, key=rank)
                register_selection(best, _SelectionDecision(stage, len(selected) + 1, float(best["_base_score"])))

    compatible = [c for c in scored if c["selection_status"] == "compatible"]
    if cfg.diversify_domains:
        best_by_domain: dict[str, dict[str, object]] = {}
        for c in sorted(compatible, key=rank):
            domain = _norm(c.get("catalog_domain") or c.get("domain"))
            if domain and can_select(c):
                best_by_domain.setdefault(domain, c)
        for c in list(best_by_domain.values())[:max(0, cfg.min_domain_coverage)]:
            if can_select(c):
                register_selection(c, _SelectionDecision("domain_diversification", len(selected) + 1, float(c["_base_score"])))

    def supplementary_decision(c: dict[str, object]) -> _SelectionDecision:
        provider = _norm(c.get("provider"))
        domain = _norm(c.get("catalog_domain") or c.get("domain"))
        provider_penalty = cfg.penalty_repeat_provider * provider_count.get(provider, 0)
        domain_penalty = cfg.penalty_repeat_domain * domain_count.get(domain, 0)
        return _SelectionDecision(
            "supplementary_ranking",
            len(selected) + 1,
            float(c["_base_score"]) - provider_penalty - domain_penalty,
            provider_penalty,
            domain_penalty,
        )

    while len(selected) < cfg.max_recommendations:
        eligible = [(supplementary_decision(c), c) for c in compatible if can_select(c)]
        if not eligible:
            break
        decision, best = min(eligible, key=lambda item: rank(item[1], item[0].score))
        if decision.score <= -1.0:
            break
        register_selection(best, decision)

    selected.sort(key=lambda c: (
        _horizon_order(str(c.get("plazo", ""))),
        c["selection_status"] != "compatible",
        *rank(c, c["_selection_decision"].score),
    ))
    explained = []
    for i, c in enumerate(selected, 1):
        row = dict(c)
        row["engine_explanation"] = _build_explanation(row, rank=i, decision=c["_selection_decision"])
        for field in ("_base_score", "_score_components", "_selected", "_selection_decision", "catalog_solution_name", "catalog_domain"):
            row.pop(field, None)
        explained.append(row)

    outcomes = {}
    for key, candidates in required_transition_groups.items():
        chosen = {c["selection_status"] for c in candidates if c.get("_selected")}
        candidate_states = {str(c["selection_status"]) for c in candidates}
        if "compatible" in chosen:
            outcome = "compatible"
        elif chosen:
            outcome = next(iter(chosen))
        elif candidate_states == {"not_compatible"}:
            outcome = "not_compatible"
        elif candidate_states <= {"not_compatible", "insufficient_evidence"}:
            outcome = "insufficient_evidence"
        else:
            outcome = "selection_constraints"
        outcomes[key] = {"status": outcome, "candidate_statuses": sorted(candidate_states)}

    return explained, {
        "engine_version": "eng_v2.0",
        "candidate_count": len(scored),
        "selected_count": len(explained),
        "transition_outcomes": outcomes,
        "config": {
            "max_recommendations": cfg.max_recommendations,
            "max_candidates_per_kpi": cfg.max_candidates_per_kpi,
            "max_per_provider": cfg.max_per_provider,
            "max_per_kpi": cfg.max_per_kpi,
            "diversify_domains": cfg.diversify_domains,
            "min_domain_coverage": cfg.min_domain_coverage,
            "budget_capacity": cfg.budget_capacity,
            "weights": {
                "priority": cfg.weight_priority,
                "impact": cfg.weight_impact,
                "risk": cfg.weight_risk,
                "effort": cfg.weight_effort,
            },
        },
    }
