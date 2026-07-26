from __future__ import annotations

import unittest

from costing import estimate_cost_clp, horizon_months
from recommendation_engine import EngineConfig, _score_candidates, optimize_recommendations


class CostingTests(unittest.TestCase):
    def test_monthly_subscription_uses_the_horizon_upper_bound(self) -> None:
        entry = {
            "price_type": "subscription",
            "price_max_clp": 7200,
            "plazo": "Corto plazo",
            "months_max": 3,
        }
        self.assertEqual(horizon_months(entry), 3)
        self.assertEqual(estimate_cost_clp(entry), 21600)

    def test_monthly_subscription_uses_horizon_when_months_are_not_provided(self) -> None:
        entry = {
            "price_type": "subscription",
            "price_max_clp": 14400,
            "plazo": "Medium term",
        }
        self.assertEqual(horizon_months(entry), 6)
        self.assertEqual(estimate_cost_clp(entry), 86400)

    def test_non_recurring_cost_is_not_multiplied(self) -> None:
        entry = {
            "price_type": "fixed",
            "price_max_clp": 99990,
            "plazo": "Largo plazo",
            "months_max": 12,
        }
        self.assertEqual(estimate_cost_clp(entry), 99990)

    def test_existing_engine_estimate_is_preserved_for_reporting(self) -> None:
        entry = {
            "price_type": "fixed",
            "price_max_clp": 99990,
            "cost_estimated_clp": 99990,
        }
        self.assertEqual(estimate_cost_clp(entry, use_existing_estimate=True), 99990)

    def test_existing_legacy_subscription_estimate_is_recalculated(self) -> None:
        entry = {
            "price_type": "subscription",
            "price_max_clp": 7200,
            "plazo": "Corto plazo",
            "months_max": 3,
            "cost_estimated_clp": 7200,
        }
        self.assertEqual(estimate_cost_clp(entry, use_existing_estimate=True), 21600)

    def test_recommendation_engine_scores_the_projected_subscription_cost(self) -> None:
        candidate = {
            "price_type": "subscription",
            "price_max_clp": 14400,
            "plazo": "Mediano plazo",
            "months_max": 6,
            "priority": 1.0,
            "impact_score": 3.0,
            "risk_score": 3.0,
            "effort_score": 3.0,
        }
        scored = _score_candidates([candidate], EngineConfig())
        self.assertEqual(scored[0]["cost_estimated_clp"], 86400)

    def test_budget_filter_uses_projected_subscription_cost(self) -> None:
        candidate = {
            "price_type": "subscription",
            "price_max_clp": 14400,
            "plazo": "Mediano plazo",
            "months_max": 6,
            "priority": 1.0,
            "impact_score": 3.0,
            "risk_score": 3.0,
            "effort_score": 3.0,
            "provider": "Test provider",
            "domain": "Test domain",
            "kpi": "Test KPI",
            "solution_name": "Monthly test solution",
        }
        cfg = EngineConfig(
            budget_total_clp=80_000,
            diversify_domains=False,
            max_recommendations=1,
        )
        selected, report = optimize_recommendations([candidate], cfg)
        self.assertEqual(selected, [])
        self.assertEqual(report["used_budget_total_clp"], 0.0)


if __name__ == "__main__":
    unittest.main()
