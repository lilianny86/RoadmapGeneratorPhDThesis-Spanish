from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _norm(value: object) -> str:
    t = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).strip().lower()


def _horizon_order(plazo: str) -> int:
    key = _norm(plazo)
    if "corto" in key:
        return 1
    if "mediano" in key:
        return 2
    if "largo" in key:
        return 3
    return 4


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
    max_recommendations: int = 40
    max_candidates_per_kpi: int = 4
    max_per_provider: int = 5
    max_per_kpi: int = 2
    enforce_unique_solution: bool = True
    diversify_domains: bool = True
    min_domain_coverage: int = 4
    weight_priority: float = 0.34
    weight_impact: float = 0.26
    weight_cost: float = 0.16
    weight_risk: float = 0.12
    weight_effort: float = 0.12
    penalty_unknown_cost: float = 0.05
    penalty_repeat_provider: float = 0.08
    penalty_repeat_domain: float = 0.04
    budget_total_clp: float | None = None
    budget_short_clp: float | None = None
    budget_medium_clp: float | None = None
    budget_long_clp: float | None = None
    horizon_factor: dict[str, float] = field(
        default_factory=lambda: {
            "Corto plazo": 1.0,
            "Mediano plazo": 0.92,
            "Largo plazo": 0.84,
            "Sin clasificar": 0.75,
        }
    )

    def budget_for(self, horizon: str) -> float | None:
        key = _norm(horizon)
        if "corto" in key:
            return self.budget_short_clp
        if "mediano" in key:
            return self.budget_medium_clp
        if "largo" in key:
            return self.budget_long_clp
        return None


def _apply_dict_config(cfg: EngineConfig, raw: dict[str, Any]) -> EngineConfig:
    for key, value in raw.items():
        if not hasattr(cfg, key):
            continue
        if key == "horizon_factor" and isinstance(value, dict):
            hf = dict(cfg.horizon_factor)
            for h_key, h_val in value.items():
                v = _to_float(h_val)
                if v is not None:
                    hf[str(h_key)] = v
            cfg.horizon_factor = hf
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

    if not selected:
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


def _estimate_cost(candidate: dict[str, object], fallback_cost: float) -> float | None:
    ptype = _norm(candidate.get("price_type", "unknown"))
    pmax = _to_float(candidate.get("price_max_clp"), default=None)
    pmin = _to_float(candidate.get("price_min_clp"), default=None)
    if ptype == "free":
        return 0.0
    if pmax is not None:
        return max(pmax, 0.0)
    if pmin is not None:
        return max(pmin, 0.0)
    if fallback_cost <= 0:
        return None
    return fallback_cost


def _score_candidates(candidates: list[dict[str, object]], cfg: EngineConfig) -> list[dict[str, object]]:
    if not candidates:
        return []
    max_priority = max(float(c.get("priority", 0) or 0) for c in candidates)
    known_costs = [
        _to_float(c.get("price_max_clp"), default=None)
        for c in candidates
        if _to_float(c.get("price_max_clp"), default=None) is not None
    ]
    fallback_cost = (sum(known_costs) / len(known_costs)) if known_costs else 0.0
    max_cost = max(known_costs) if known_costs else 1.0

    scored: list[dict[str, object]] = []
    for c in candidates:
        row = dict(c)
        priority = float(row.get("priority", 0) or 0)
        impact = float(row.get("impact_score", 3.0) or 3.0)
        risk = float(row.get("risk_score", 3.0) or 3.0)
        effort = float(row.get("effort_score", 3.0) or 3.0)
        cost_est = _estimate_cost(row, fallback_cost=fallback_cost)
        has_known_cost = _to_float(row.get("price_max_clp"), default=None) is not None or _to_float(row.get("price_min_clp"), default=None) is not None

        priority_n = (priority / max_priority) if max_priority > 0 else 0.0
        impact_n = min(max(impact / 5.0, 0.0), 1.0)
        risk_n = min(max(1.0 - (risk / 5.0), 0.0), 1.0)
        effort_n = min(max(1.0 - (effort / 5.0), 0.0), 1.0)
        if cost_est is None:
            cost_n = 0.45
        elif max_cost > 0:
            cost_n = min(max(1.0 - (cost_est / max_cost), 0.0), 1.0)
        else:
            cost_n = 0.5

        contrib_priority = cfg.weight_priority * priority_n
        contrib_impact = cfg.weight_impact * impact_n
        contrib_cost = cfg.weight_cost * cost_n
        contrib_risk = cfg.weight_risk * risk_n
        contrib_effort = cfg.weight_effort * effort_n
        base = contrib_priority + contrib_impact + contrib_cost + contrib_risk + contrib_effort
        horizon = str(row.get("plazo", "Sin clasificar"))
        horizon_mult = cfg.horizon_factor.get(horizon, cfg.horizon_factor.get("Sin clasificar", 0.75))
        score = base * horizon_mult
        if not has_known_cost:
            score -= cfg.penalty_unknown_cost

        row["cost_estimated_clp"] = cost_est
        row["_base_score"] = max(score, 0.0)
        row["_score_components"] = {
            "prioridad_kpi": round(contrib_priority, 4),
            "impacto": round(contrib_impact, 4),
            "costo": round(contrib_cost, 4),
            "riesgo": round(contrib_risk, 4),
            "esfuerzo": round(contrib_effort, 4),
            "factor_horizonte": round(horizon_mult, 4),
        }
        scored.append(row)
    return scored


def _can_fit_budget(
    candidate: dict[str, object],
    cfg: EngineConfig,
    *,
    used_total: float,
    used_by_horizon: dict[str, float],
) -> bool:
    cost = _to_float(candidate.get("cost_estimated_clp"), default=None)
    if cost is None:
        # Permitimos costo no determinado para no bloquear iniciativas sin precio público.
        return True
    horizon = str(candidate.get("plazo", "Sin clasificar"))
    if cfg.budget_total_clp is not None and (used_total + cost) > cfg.budget_total_clp:
        return False
    h_budget = cfg.budget_for(horizon)
    if h_budget is not None and (used_by_horizon.get(horizon, 0.0) + cost) > h_budget:
        return False
    return True


def _build_explanation(
    candidate: dict[str, object],
    *,
    rank: int,
    dynamic_score: float,
    provider_repeats: int,
    domain_repeats: int,
) -> dict[str, object]:
    comps = candidate.get("_score_components", {})
    ordered = sorted(
        [(k, float(v)) for k, v in comps.items() if k != "factor_horizonte"],
        key=lambda x: x[1],
        reverse=True,
    )
    top_bits = [f"{k}={v:.2f}" for k, v in ordered[:2]]
    assumptions: list[str] = []
    if candidate.get("cost_estimated_clp") is None:
        assumptions.append("Costo estimado por defecto (sin precio público confirmado).")
    if _norm(candidate.get("price_type", "")) == "subscription":
        assumptions.append("Costo referido a esquema de suscripción.")
    if provider_repeats > 0:
        assumptions.append("Penalización por proveedor repetido para mejorar diversidad.")
    if domain_repeats > 0:
        assumptions.append("Penalización por dominio repetido para ampliar cobertura.")

    return {
        "rank": rank,
        "selection_score": round(dynamic_score, 4),
        "summary": "Seleccionada por alto desempeño multicriterio.",
        "main_drivers": top_bits,
        "component_scores": comps,
        "assumptions": assumptions,
        "dependencies": candidate.get("dependencies", []),
    }


def optimize_recommendations(
    candidate_entries: list[dict[str, object]],
    cfg: EngineConfig,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    scored = _score_candidates(candidate_entries, cfg)
    if not scored:
        return [], {
            "engine_version": "eng_v1.0",
            "selected_count": 0,
            "candidate_count": 0,
            "used_budget_total_clp": 0.0,
            "used_budget_by_horizon": {},
            "reason": "Sin candidatos para optimizar.",
        }

    remaining = list(scored)
    selected: list[dict[str, object]] = []
    used_total = 0.0
    used_by_horizon: dict[str, float] = {}
    provider_count: dict[str, int] = {}
    domain_count: dict[str, int] = {}
    kpi_count: dict[str, int] = {}
    used_solution_names: set[str] = set()

    def can_select(c: dict[str, object]) -> bool:
        if len(selected) >= cfg.max_recommendations:
            return False
        provider = _norm(c.get("provider", ""))
        kpi = _norm(c.get("kpi", ""))
        name = _norm(c.get("solution_name", ""))
        if provider and provider_count.get(provider, 0) >= cfg.max_per_provider:
            return False
        if kpi and kpi_count.get(kpi, 0) >= cfg.max_per_kpi:
            return False
        if cfg.enforce_unique_solution and name and name in used_solution_names:
            return False
        if not _can_fit_budget(c, cfg, used_total=used_total, used_by_horizon=used_by_horizon):
            return False
        return True

    # Pase 1: cobertura mínima por dominio.
    if cfg.diversify_domains:
        best_by_domain: dict[str, dict[str, object]] = {}
        for c in sorted(remaining, key=lambda x: float(x.get("_base_score", 0)), reverse=True):
            d = _norm(c.get("domain", ""))
            if not d or d in best_by_domain:
                continue
            best_by_domain[d] = c
        for _, c in list(best_by_domain.items())[: max(0, cfg.min_domain_coverage)]:
            if not can_select(c):
                continue
            provider = _norm(c.get("provider", ""))
            domain = _norm(c.get("domain", ""))
            kpi = _norm(c.get("kpi", ""))
            name = _norm(c.get("solution_name", ""))
            cost = _to_float(c.get("cost_estimated_clp"), default=None)
            if cost is not None:
                used_total += cost
                h = str(c.get("plazo", "Sin clasificar"))
                used_by_horizon[h] = used_by_horizon.get(h, 0.0) + cost
            provider_count[provider] = provider_count.get(provider, 0) + 1
            domain_count[domain] = domain_count.get(domain, 0) + 1
            kpi_count[kpi] = kpi_count.get(kpi, 0) + 1
            if name:
                used_solution_names.add(name)
            c["_selected_dynamic_score"] = float(c.get("_base_score", 0))
            selected.append(c)

    # Pase 2: optimización greedy con penalizaciones de repetición.
    while len(selected) < cfg.max_recommendations:
        best_idx = -1
        best_score = -1.0
        for idx, c in enumerate(remaining):
            if c in selected:
                continue
            if not can_select(c):
                continue
            provider = _norm(c.get("provider", ""))
            domain = _norm(c.get("domain", ""))
            dyn = float(c.get("_base_score", 0))
            dyn -= cfg.penalty_repeat_provider * provider_count.get(provider, 0)
            dyn -= cfg.penalty_repeat_domain * max(domain_count.get(domain, 0) - 0, 0)
            if dyn > best_score:
                best_score = dyn
                best_idx = idx
        if best_idx < 0:
            break
        c = remaining[best_idx]
        provider = _norm(c.get("provider", ""))
        domain = _norm(c.get("domain", ""))
        kpi = _norm(c.get("kpi", ""))
        name = _norm(c.get("solution_name", ""))
        cost = _to_float(c.get("cost_estimated_clp"), default=None)
        if cost is not None:
            used_total += cost
            h = str(c.get("plazo", "Sin clasificar"))
            used_by_horizon[h] = used_by_horizon.get(h, 0.0) + cost
        provider_count[provider] = provider_count.get(provider, 0) + 1
        domain_count[domain] = domain_count.get(domain, 0) + 1
        kpi_count[kpi] = kpi_count.get(kpi, 0) + 1
        if name:
            used_solution_names.add(name)
        c["_selected_dynamic_score"] = best_score
        selected.append(c)

    selected.sort(key=lambda x: (_horizon_order(str(x.get("plazo", ""))), -float(x.get("_selected_dynamic_score", 0))))

    explained: list[dict[str, object]] = []
    for i, c in enumerate(selected, start=1):
        provider = _norm(c.get("provider", ""))
        domain = _norm(c.get("domain", ""))
        row = dict(c)
        row["engine_explanation"] = _build_explanation(
            row,
            rank=i,
            dynamic_score=float(row.get("_selected_dynamic_score", row.get("_base_score", 0))),
            provider_repeats=max(provider_count.get(provider, 1) - 1, 0),
            domain_repeats=max(domain_count.get(domain, 1) - 1, 0),
        )
        row.pop("_base_score", None)
        row.pop("_selected_dynamic_score", None)
        row.pop("_score_components", None)
        explained.append(row)

    report = {
        "engine_version": "eng_v1.0",
        "candidate_count": len(scored),
        "selected_count": len(explained),
        "used_budget_total_clp": round(used_total, 2),
        "used_budget_by_horizon": {k: round(v, 2) for k, v in used_by_horizon.items()},
        "config": {
            "max_recommendations": cfg.max_recommendations,
            "max_candidates_per_kpi": cfg.max_candidates_per_kpi,
            "max_per_provider": cfg.max_per_provider,
            "max_per_kpi": cfg.max_per_kpi,
            "diversify_domains": cfg.diversify_domains,
            "min_domain_coverage": cfg.min_domain_coverage,
            "weights": {
                "priority": cfg.weight_priority,
                "impact": cfg.weight_impact,
                "cost": cfg.weight_cost,
                "risk": cfg.weight_risk,
                "effort": cfg.weight_effort,
            },
            "budget_total_clp": cfg.budget_total_clp,
            "budget_short_clp": cfg.budget_short_clp,
            "budget_medium_clp": cfg.budget_medium_clp,
            "budget_long_clp": cfg.budget_long_clp,
        },
    }
    return explained, report

