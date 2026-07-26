from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app_streamlit import _apply_no_translate_guard, _send_pdfs_via_gmail
from consent_export import (
    CONSENT_VERSION,
    RESEARCHER_NAME,
    build_consent_record,
    consent_acceptance_statement,
    consent_sections,
)
from security_config import SecurityConfig


class _PdfAttachment:
    def __init__(self, name: str) -> None:
        self.name = name

    def exists(self) -> bool:
        return True

    def read_bytes(self) -> bytes:
        return b"%PDF-1.4\nplaceholder\n"


class ConsentTests(unittest.TestCase):
    @patch("app_streamlit.components.html", side_effect=RuntimeError("component unavailable"))
    def test_cosmetic_browser_guard_cannot_stop_the_app(self, _: MagicMock) -> None:
        _apply_no_translate_guard("es")

    def test_spanish_and_english_text_identify_the_thesis_and_researcher(self) -> None:
        spanish = " ".join(text for _, text in consent_sections("es", "contact@example.org"))
        english = " ".join(text for _, text in consent_sections("en", "contact@example.org"))

        self.assertIn("tesis doctoral", spanish)
        self.assertIn(RESEARCHER_NAME, spanish)
        self.assertIn("doctoral thesis", english)
        self.assertIn(RESEARCHER_NAME, english)

    def test_consent_record_uses_checkbox_acceptance_and_pending_interviewer_signature(self) -> None:
        record = build_consent_record(
            consent_id="CONSENT-1",
            language="es",
            accepted_at="2026-07-26T10:00:00-04:00",
            participant_email="participant@example.org",
            company_name="Empresa de prueba",
            company_rut="12.345.678-5",
            contact_email="contact@example.org",
        )

        self.assertEqual(record["consent_version"], CONSENT_VERSION)
        self.assertEqual(record["acceptance_method"], "checkbox")
        self.assertEqual(record["interviewer_signature_status"], "pending")
        self.assertIn("acepto voluntariamente", record["acceptance_statement"])
        self.assertIn("voluntarily agree", consent_acceptance_statement("en"))

    @patch("app_streamlit._merge_smtp_config_from_streamlit_secrets")
    @patch("app_streamlit.load_security_config")
    @patch("app_streamlit.smtplib.SMTP")
    def test_roadmap_email_includes_the_consent_receipt(self, smtp_mock: MagicMock, config_mock: MagicMock, merge_mock: MagicMock) -> None:
        config = SecurityConfig(
            require_smtp=True,
            smtp_host="smtp.example.org",
            smtp_port=587,
            smtp_user="sender@example.org",
            smtp_password="test-password",
            smtp_from="sender@example.org",
            smtp_to="",
        )
        config_mock.return_value = (config, None)
        merge_mock.return_value = config
        smtp_client = smtp_mock.return_value.__enter__.return_value

        recipients = _send_pdfs_via_gmail(
            root=None,
            company_name="Empresa de prueba",
            company_email="participant@example.org",
            pdf_paths=[_PdfAttachment("roadmap_es.pdf"), _PdfAttachment("consent_empresa_es.pdf")],
            language="es",
            include_consent=True,
        )

        self.assertEqual(recipients, ["participant@example.org"])
        message = smtp_client.send_message.call_args.args[0]
        self.assertEqual(message["To"], "participant@example.org")
        self.assertIn("consentimiento informado", message.get_body(preferencelist=("plain",)).get_content())
        self.assertEqual([part.get_filename() for part in message.iter_attachments()], ["roadmap_es.pdf", "consent_empresa_es.pdf"])


if __name__ == "__main__":
    unittest.main()
