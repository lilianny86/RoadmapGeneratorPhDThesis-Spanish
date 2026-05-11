from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from recommendation_engine import build_engine_config, optimize_recommendations


class RecommendationEngineTests(unittest.TestCase):
    def test_optimizacion_respeta_presupuesto_y_limites(self) -> None:
        candidates = [
            {
                "domain": "D1",
                "kda": "K1",
                "kpi": "KPI-1",
                "transition": "N1->N3",
                "plazo": "Corto plazo",
                "solution_name": "Solucion A",
                "solution_description": "Impacto alto",
                "provider": "Prov-1",
                "provider_url": "",
                "source": "",
                "source_url": "",
                "price": "100000 CLP",
                "price_type": "fixed",
                "price_min_clp": 100000.0,
                "price_max_clp": 100000.0,
                "impact_score": 4.5,
                "effort_score": 2.0,
                "risk_score": 2.0,
                "dependencies": [],
                "priority": 4.0,
                "option": 1,
            },
            {
                "domain": "D1",
                "kda": "K1",
                "kpi": "KPI-2",
                "transition": "N1->N3",
                "plazo": "Corto plazo",
                "solution_name": "Solucion B",
                "solution_description": "Impacto medio",
                "provider": "Prov-1",
                "provider_url": "",
                "source": "",
                "source_url": "",
                "price": "90000 CLP",
                "price_type": "fixed",
                "price_min_clp": 90000.0,
                "price_max_clp": 90000.0,
                "impact_score": 3.8,
                "effort_score": 2.3,
                "risk_score": 2.1,
                "dependencies": [],
                "priority": 3.6,
                "option": 1,
            },
            {
                "domain": "D2",
                "kda": "K2",
                "kpi": "KPI-3",
                "transition": "N2->N4",
                "plazo": "Mediano plazo",
                "solution_name": "Solucion C",
                "solution_description": "Impacto alto",
                "provider": "Prov-2",
                "provider_url": "",
                "source": "",
                "source_url": "",
                "price": "250000 CLP",
                "price_type": "fixed",
                "price_min_clp": 250000.0,
                "price_max_clp": 250000.0,
                "impact_score": 4.7,
                "effort_score": 3.8,
                "risk_score": 3.7,
                "dependencies": [],
                "priority": 3.9,
                "option": 1,
            },
        ]
        cfg = build_engine_config(
            None,
            {
                "budget_total_clp": 180000,
                "max_recommendations": 3,
                "max_per_provider": 1,
                "max_per_kpi": 1,
            },
        )
        selected, report = optimize_recommendations(candidates, cfg)
        self.assertLessEqual(len(selected), 3)
        self.assertLessEqual(report["used_budget_total_clp"], 180000)
        providers = {str(x.get("provider", "")).lower() for x in selected}
        self.assertEqual(len(selected), len(providers))
        self.assertTrue(all("engine_explanation" in x for x in selected))


if __name__ == "__main__":
    unittest.main()
