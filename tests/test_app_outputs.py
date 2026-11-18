import csv
import io
import json
import smtplib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import streamlit_app as ui
from roadmap_core import cli
from security_config import SecurityConfig


class CaseOutputTests(unittest.TestCase):
    def setUp(self):
        self.config = SecurityConfig(False, "smtp.example.invalid", 587, "research@example.invalid",
                                     "synthetic-app-value", "research@example.invalid", "")

    def _verify_case(self, profile, language, smtp_fails):
        question_count = 21 if profile == "small" else 22
        company_name, rut, email = "QA Sample", "123456785", "qa@example.invalid"
        saved_csv_counts = []
        with TemporaryDirectory() as directory:
            output = Path(directory)

            def send_after_saving(_config, _message):
                saved_csv_counts.append(len(list(output.rglob("*.csv"))))
                if smtp_fails:
                    raise smtplib.SMTPServerDisconnected("Simulated SMTP failure")

            with patch.multiple(
                ui,
                OUTPUT_UI_DIR=output,
                _participant_pseudonym_secret=lambda: "synthetic-participant-value",
                _stats_recipient_from_config=lambda _cfg: "research@example.invalid",
                load_security_config=lambda _root: (self.config, None),
                _merge_smtp_config_from_streamlit_secrets=lambda cfg: cfg,
            ), patch.object(ui, "_deliver_smtp_message", side_effect=send_after_saving) as smtp, patch.object(
                ui.st, "download_button", wraps=ui.st.download_button
            ) as downloads:
                app = AppTest.from_string("from streamlit_app import main; main()", default_timeout=15)
                app.query_params["ui_lang"] = language
                app.run()
                app.checkbox(key="consent_accepted_checkbox").check().run()
                app.sidebar.selectbox[0].set_value(profile).run()
                for widget, value in zip(app.sidebar.text_input, (company_name, rut, email)):
                    widget.set_value(value)
                app.sidebar.slider(key=f"target_level_{profile}").set_value(3)
                app.sidebar.radio(key=f"budget_capacity_{profile}").set_value(f"{profile}_low")
                app.run()
                for radio in app.radio:
                    if (radio.key or "").startswith(f"q_{profile}_"):
                        radio.set_value(0)
                app.run()
                app.button[-1].click().run()
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                self.assertEqual(len(app.get("download_button")), 3)

                run_dirs = list(output.iterdir())
                self.assertEqual(len(run_dirs), 1)
                files = {path.name: path.read_bytes() for path in run_dirs[0].iterdir()}
                self.assertEqual(len(files), 6)
                state = app.session_state["ui_last_result"]["files"]
                self.assertEqual(set(state), {"roadmap_es", "roadmap_en", "consent"})
                for key, role in (("download_roadmap_es", "roadmap_es"), ("download_roadmap_en", "roadmap_en"),
                                  ("download_consent", "consent")):
                    kwargs, = (call.kwargs for call in downloads.call_args_list if call.kwargs["key"] == key)
                    expected = Path(state[role]).name
                    self.assertEqual(kwargs["file_name"], expected)
                    self.assertEqual(kwargs["on_click"], "ignore")
                    self.assertEqual(kwargs["data"], files[expected])
                    self.assertTrue(files[expected].startswith(b"%PDF"))

                self.assertEqual(saved_csv_counts, [3, 3])
                self.assertEqual(smtp.call_count, 2)
                participant, researcher = (call.args[1] for call in smtp.call_args_list)
                participant_docs = {item.get_filename(): item.get_payload(decode=True) for item in participant.iter_attachments()}
                recipient_pdf_names = {Path(state["consent"]).name, Path(state[f"roadmap_{language}"]).name}
                self.assertEqual(participant_docs, {name: files[name] for name in recipient_pdf_names})
                csv_docs = {name: data for name, data in files.items() if name.endswith(".csv")}
                self.assertEqual(csv_docs, {item.get_filename(): item.get_payload(decode=True) for item in researcher.iter_attachments()})
                self.assertEqual(set(files), {Path(path).name for path in state.values()} | set(csv_docs))

                detail, = (data for name, data in csv_docs.items() if name.startswith("rogen_estadisticas_detalle_kpi_"))
                self.assertEqual(len(list(csv.DictReader(io.StringIO(detail.decode("utf-8-sig"))))), question_count)
                for data in csv_docs.values():
                    for identifier in (company_name, "12.345.678-5", rut, email):
                        self.assertNotIn(identifier.encode(), data)

                app.run()
                self.assertEqual(len(app.get("download_button")), 3)
                self.assertEqual(smtp.call_count, 2)

    def test_spanish_small_case_generates_only_the_expected_documents(self):
        self._verify_case("small", "es", smtp_fails=False)

    def test_english_medium_case_keeps_downloads_and_csvs_when_smtp_fails(self):
        self._verify_case("medium", "en", smtp_fails=True)

    def test_cli_exports_only_the_requested_files(self):
        with TemporaryDirectory() as directory, patch("roadmap_core.load_security_config", return_value=(self.config, None)):
            folder = Path(directory)
            answers = folder / "answers.json"
            answers.write_text(json.dumps([1] * 21), encoding="utf-8")
            arguments = ["--company-type", "small", "--target-level", "3", "--answers-file", str(answers),
                         "--budget-capacity", "small_low"]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli([*arguments, "--language", "en", "--output-pdf", str(folder / "roadmap.pdf")]), 0)
            self.assertEqual({path.name for path in folder.iterdir()}, {"answers.json", "roadmap.pdf"})
            self.assertIn(b"TECHNOLOGY IMPROVEMENT ROADMAP", (folder / "roadmap.pdf").read_bytes())
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli([*arguments, "--language", "en", "--skip-pdf", "--output-json", str(folder / "analysis.json")]), 0)
            self.assertEqual({path.name for path in folder.iterdir()}, {"answers.json", "roadmap.pdf", "analysis.json"})
            payload = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
            result = payload["result"]
            self.assertTrue(result["traceability_entries"])
            for row, trace in zip(result["roadmap_entries"], result["traceability_entries"], strict=True):
                explanation = row["engine_explanation"]
                self.assertEqual(trace["recommendation"], row["solution_name"])
                self.assertEqual(trace["engine_score"], explanation["selection_score"])
                for field in ("base_score", "selection_stage", "selection_order", "applied_penalties"):
                    self.assertEqual(trace[f"engine_{field}"], explanation[field])
                self.assertEqual(trace["engine_selection_summary"], explanation["summary"])
                self.assertTrue(explanation["summary"].startswith("Selected "))
