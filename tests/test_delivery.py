import smtplib
import unittest
from email.message import EmailMessage
from unittest.mock import patch

from security_config import SecurityConfig
from streamlit_app import _deliver_smtp_message, _safe_smtp_console_diagnostic, _safe_smtp_error_message


class MailDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.config = SecurityConfig(False, 'smtp.example.invalid', 587, 'qa@example.invalid',
                                     'synthetic-test-value', 'qa@example.invalid', '')

    @patch('streamlit_app.smtplib.SMTP')
    def test_delivery_uses_tls_then_auth_and_sends_once(self, factory):
        smtp = factory.return_value.__enter__.return_value
        message = EmailMessage()
        message.add_attachment(b'%PDF-test', maintype='application', subtype='pdf', filename='roadmap.pdf')
        _deliver_smtp_message(self.config, message)
        self.assertEqual([method[0] for method in smtp.method_calls], ['starttls', 'login', 'send_message'])
        smtp.send_message.assert_called_once_with(message)

    @patch('streamlit_app.smtplib.SMTP')
    def test_auth_disconnect_is_reported_without_a_delivery_attempt(self, factory):
        smtp = factory.return_value.__enter__.return_value
        smtp.login.side_effect = smtplib.SMTPServerDisconnected('connection closed for qa@example.invalid')
        with self.assertRaises(smtplib.SMTPServerDisconnected) as reported:
            _deliver_smtp_message(self.config, EmailMessage())
        smtp.send_message.assert_not_called()
        self.assertIn('interrumpi', _safe_smtp_error_message(reported.exception, 'es'))
        log = _safe_smtp_console_diagnostic(reported.exception)
        self.assertIn('authentication', log)
        self.assertNotIn('qa@example.invalid', log)
        self.assertNotIn(self.config.smtp_password, log)

    @patch('streamlit_app.smtplib.SMTP')
    def test_gmail_preserves_authentication_rejection(self, factory):
        self.config.smtp_host = 'smtp.gmail.com'
        smtp = factory.return_value.__enter__.return_value
        smtp.esmtp_features = {'auth': 'PLAIN LOGIN'}
        smtp.auth.side_effect = smtplib.SMTPAuthenticationError(535, b'Invalid credentials')
        with self.assertRaises(smtplib.SMTPAuthenticationError) as reported:
            _deliver_smtp_message(self.config, EmailMessage())
        smtp.auth.assert_called_once_with('LOGIN', smtp.auth_login, initial_response_ok=False)
        smtp.login.assert_not_called()
        smtp.send_message.assert_not_called()
        self.assertIn('App Password', _safe_smtp_error_message(reported.exception, 'es'))
