from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from roadmap_core import apply_roadmap_edits, autosave_session, save_preview


class RoadmapUxTests(unittest.TestCase):
    def _sample_payload(self) -> dict[str, object]:
        return {
            "company": {"name": "Empresa Demo", "rut": "11.111.111-1", "email": "demo@example.com"},
            "result": {
                "timestamp": "2026-04-20T18:30:00",
                "roadmap_entries": [
                    {
                        "plazo": "Mediano plazo",
                        "kpi": "KPI A",
                        "solution_name": "Solucion 1",
                        "priority": 3.0,
                        "engine_explanation": {"selection_score": 0.7},
                    },
                    {
                        "plazo": "Corto plazo",
                        "kpi": "KPI B",
                        "solution_name": "Solucion 2",
                        "priority": 4.0,
                        "engine_explanation": {"selection_score": 0.8},
                    },
                ],
                "engine_summary": {"selected_count": 2},
                "catalog_summary": {"rows_processed": 10},
            },
        }

    def test_save_preview_contiene_bloques_esperados(self) -> None:
        payload = self._sample_payload()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "preview.json"
            save_preview(payload, out)
            preview = json.loads(out.read_text(encoding="utf-8"))
            self.assertIn("engine_summary", preview)
            self.assertIn("catalog_summary", preview)
            self.assertIn("roadmap_entries", preview)
            self.assertEqual(2, len(preview["roadmap_entries"]))

    def test_apply_roadmap_edits_orden_por_plazo_y_score(self) -> None:
        payload = self._sample_payload()
        edits = {
            "roadmap_entries": [
                {
                    "plazo": "Largo plazo",
                    "kpi": "KPI C",
                    "solution_name": "Solucion 3",
                    "engine_explanation": {"selection_score": 0.6},
                },
                {
                    "plazo": "Corto plazo",
                    "kpi": "KPI D",
                    "solution_name": "Solucion 4",
                    "engine_explanation": {"selection_score": 0.9},
                },
            ]
        }
        with tempfile.TemporaryDirectory() as tmp:
            edits_path = Path(tmp) / "edits.json"
            edits_path.write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding="utf-8")
            updated = apply_roadmap_edits(payload, edits_path)

        entries = updated["result"]["roadmap_entries"]
        self.assertEqual("Corto plazo", entries[0]["plazo"])
        self.assertEqual("Largo plazo", entries[1]["plazo"])

    def test_autosave_session_genera_archivo(self) -> None:
        payload = self._sample_payload()
        with tempfile.TemporaryDirectory() as tmp:
            path = autosave_session(payload, Path(tmp))
            self.assertTrue(path.exists())
            restored = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("Empresa Demo", restored["company"]["name"])


if __name__ == "__main__":
    unittest.main()
