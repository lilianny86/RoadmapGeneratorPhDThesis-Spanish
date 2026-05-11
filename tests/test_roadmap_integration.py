from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from recommendation_engine import build_engine_config
from roadmap_core import build_roadmap, load_answers


class RoadmapIntegrationTests(unittest.TestCase):
    def test_build_roadmap_incluye_resumenes_data_y_engine(self) -> None:
        root = Path(__file__).resolve().parents[1]
        answers = load_answers(root / "examples" / "answers_small.json")
        engine_cfg = build_engine_config(None, {"max_recommendations": 15})

        payload = build_roadmap(
            root=root,
            company_type="small",
            answers=answers,
            target_level=3,
            company_name="QA Integration",
            company_rut="11.111.111-1",
            company_email="qa@example.com",
            engine_cfg=engine_cfg,
        )

        result = payload["result"]
        self.assertIn("catalog_summary", result)
        self.assertIn("engine_summary", result)
        self.assertGreater(result["engine_summary"]["selected_count"], 0)
        self.assertIn("catalog_validation_report", payload)
        self.assertIn("roadmap_entries", result)
        self.assertIn("traceability_entries", result)
        self.assertTrue(all("engine_explanation" in x for x in result["roadmap_entries"]))
        self.assertEqual(len(result["traceability_entries"]), len(result["roadmap_entries"]))
        if result["traceability_entries"]:
            row = result["traceability_entries"][0]
            self.assertIn("kpi", row)
            self.assertIn("recommendation", row)
            self.assertIn("rule_constraints", row)


if __name__ == "__main__":
    unittest.main()
