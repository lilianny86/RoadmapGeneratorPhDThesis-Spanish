from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilot_batch import _aggregate_results, _horizon_distribution, _normalize_answers


class PilotBatchTests(unittest.TestCase):
    def test_normalize_answers_list_and_dict(self) -> None:
        self.assertEqual([1, 2, 3], _normalize_answers([1, "2", 3]))
        self.assertEqual({1: 2, 3: 4}, _normalize_answers({"1": "2", 3: 4}))

    def test_horizon_distribution(self) -> None:
        entries = [
            {"plazo": "Corto plazo"},
            {"plazo": "Mediano plazo"},
            {"plazo": "largo"},
            {"plazo": "indefinido"},
        ]
        dist = _horizon_distribution(entries)
        self.assertEqual(1, dist["Corto plazo"])
        self.assertEqual(1, dist["Mediano plazo"])
        self.assertEqual(1, dist["Largo plazo"])
        self.assertEqual(1, dist["Sin clasificar"])

    def test_aggregate_results(self) -> None:
        rows = [
            {"case_id": "a", "status": "ok", "actions": 10, "current_score": 1.2, "target_score": 3.0, "budget_used_clp": 1000},
            {"case_id": "b", "status": "ok", "actions": 20, "current_score": 1.8, "target_score": 3.5, "budget_used_clp": 2000},
            {"case_id": "c", "status": "error", "error": "fail"},
        ]
        report = _aggregate_results(rows)
        self.assertEqual(3, report["total_cases"])
        self.assertEqual(2, report["success_cases"])
        self.assertEqual(1, report["failed_cases"])
        self.assertEqual(15.0, report["avg_actions"])
        self.assertEqual(3000.0, report["sum_budget_used_clp"])


if __name__ == "__main__":
    unittest.main()
