from __future__ import annotations

import unittest

from app_streamlit import BUDGET_OPTIONS_BY_COMPANY, BUDGET_TO_CLP, _build_overrides
from pdf_export import _entry_price_amount as spanish_price_amount
from pdf_export import _entry_price_label as spanish_price_label
from pdf_export_en import _entry_price_amount as english_price_amount
from pdf_export_en import _entry_price_label as english_price_label
from recommendation_engine import EngineConfig, optimize_recommendations
from stats_export import _budget_cap_clp, _price_value_clp


def _candidate(*, name: str, cost: float, score: float) -> dict[str, object]:
    return {
        "required_transition_key": "1:N1->N2",
        "solution_name": name,
        "price_type": "fixed",
        "price_max_clp": cost,
        "plazo": "Corto plazo",
        "months_max": 3,
        "priority": score,
        "impact_score": 3.0,
        "risk_score": 3.0,
        "effort_score": 3.0,
        "provider": "Provider",
        "domain": "Domain",
        "kpi": "KPI",
    }


class BudgetPolicyTests(unittest.TestCase):
    def test_operational_budget_options_are_closed_by_company_size(self) -> None:
        self.assertEqual(BUDGET_OPTIONS_BY_COMPANY["small"], ["up_to_1m", "between_1m_5m"])
        self.assertEqual(BUDGET_OPTIONS_BY_COMPANY["medium"], ["up_to_1m", "between_1m_5m", "between_5m_10m"])
        self.assertEqual(BUDGET_TO_CLP["between_1m_5m"], 5_000_000.0)
        self.assertEqual(BUDGET_TO_CLP["between_5m_10m"], 10_000_000.0)
        self.assertEqual(_budget_cap_clp("between_1m_5m"), 5_000_000.0)
        self.assertEqual(_budget_cap_clp("between_5m_10m"), 10_000_000.0)

    def test_ui_budget_range_reaches_the_engine_as_a_hard_cap(self) -> None:
        overrides = _build_overrides({"budget_total_clp": BUDGET_TO_CLP["up_to_1m"]})
        config = EngineConfig(**overrides)

        self.assertEqual(config.budget_total_clp, 1_000_000.0)

    def test_required_transition_does_not_bypass_the_budget_cap(self) -> None:
        candidate = _candidate(name="Over budget", cost=5_000_001.0, score=1.0)
        selected, report = optimize_recommendations(
            [candidate],
            EngineConfig(budget_total_clp=5_000_000.0, diversify_domains=False),
        )

        self.assertEqual(selected, [])
        self.assertEqual(report["uncovered_required_transitions"], ["1:N1->N2"])
        self.assertEqual(report["required_transition_budget_exception_count"], 0)

    def test_affordable_candidate_is_selected_when_a_required_alternative_exceeds_budget(self) -> None:
        candidates = [
            _candidate(name="Over budget", cost=5_000_001.0, score=2.0),
            _candidate(name="Within budget", cost=4_999_999.0, score=1.0),
        ]
        selected, report = optimize_recommendations(
            candidates,
            EngineConfig(budget_total_clp=5_000_000.0, diversify_domains=False),
        )

        self.assertEqual([row["solution_name"] for row in selected], ["Within budget"])
        self.assertEqual(report["used_budget_total_clp"], 4_999_999.0)

    def test_unverified_prices_have_explicit_bilingual_roadmap_labels(self) -> None:
        entry = {
            "price_type": "variable",
            "price": "Sin precio público único; requiere cotización",
        }

        self.assertEqual(spanish_price_label(entry), "No confirmado (requiere cotización)")
        self.assertEqual(english_price_label(entry), "Not confirmed (quotation required)")
        self.assertIsNone(spanish_price_amount(entry))
        self.assertIsNone(english_price_amount(entry))
        self.assertIsNone(_price_value_clp(entry))


if __name__ == "__main__":
    unittest.main()
