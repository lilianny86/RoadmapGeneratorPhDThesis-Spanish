from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from catalog_quality import build_catalog_v3


class CatalogQualityTests(unittest.TestCase):
    def test_build_catalog_v3_normaliza_y_enriquece(self) -> None:
        raw_rows = [
            {
                "row_number": 2,
                "code": "SOL-001",
                "model": "Modelo Demo",
                "domain": "Produccion",
                "kda": "Riego",
                "kpi": "Consumo de agua",
                "transition": "N1->N3",
                "origin": "N1",
                "target": "N3",
                "option": 1,
                "name": "Sensor IoT de riego",
                "description": "Automatiza monitoreo con alertas en tiempo real",
                "plazo_raw": "corto",
                "provider": "Proveedor A",
                "provider_url": "https://example.com/proveedor",
                "source": "Fuente A",
                "source_url": "https://example.com/fuente",
                "price_reference": "150000",
                "price_clp_raw": "150000 CLP",
                "currency": "CLP",
                "fx_date": "2026-03-11",
                "source_date": "",
            }
        ]
        rows, report = build_catalog_v3(raw_rows)
        self.assertEqual(1, len(rows))
        self.assertEqual(0, report["summary"]["error_count"])
        self.assertEqual("Corto plazo", rows[0]["horizon"])
        self.assertIn("impact_score", rows[0])
        self.assertIn("dependencies", rows[0])

    def test_detecta_errores_campos_obligatorios(self) -> None:
        raw_rows = [
            {
                "row_number": 3,
                "code": "SOL-002",
                "model": "",
                "domain": "",
                "kda": "Riego",
                "kpi": "Consumo de agua",
                "transition": "",
                "origin": "N1",
                "target": "N2",
                "option": 1,
                "name": "",
                "description": "",
                "plazo_raw": "",
                "provider": "Proveedor B",
                "provider_url": "no-url",
                "source": "",
                "source_url": "",
                "price_reference": "",
                "price_clp_raw": "",
                "currency": "CLP",
                "fx_date": "",
                "source_date": "",
            }
        ]
        _, report = build_catalog_v3(raw_rows)
        self.assertGreater(report["summary"]["error_count"], 0)


if __name__ == "__main__":
    unittest.main()
