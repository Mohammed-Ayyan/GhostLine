import unittest
import logging
from io import StringIO
from ghostline.core.redaction import (
    redact_sensitive_text,
    register_secret_for_redaction,
    unregister_secret_for_redaction,
    RedactingLoggingFilter,
    RedactingFormatter
)

class TestSecurityRedaction(unittest.TestCase):
    def test_redact_cloud_api_keys(self):
        # OpenAI style
        text1 = "Error communicating with endpoint using sk-1234567890abcdef1234567890 and more text"
        sanitized1 = redact_sensitive_text(text1)
        self.assertNotIn("sk-1234567890abcdef1234567890", sanitized1)
        self.assertIn("[REDACTED]", sanitized1)

        # Anthropic style
        text2 = "API key sk-ant-api03-abcdefghijklmnop123456789 was rejected"
        sanitized2 = redact_sensitive_text(text2)
        self.assertNotIn("sk-ant-api03-abcdefghijklmnop123456789", sanitized2)
        self.assertIn("[REDACTED]", sanitized2)

        # Groq style
        text3 = "Failed request with gsk_9876543210abcdefghijklmnop"
        sanitized3 = redact_sensitive_text(text3)
        self.assertNotIn("gsk_9876543210abcdefghijklmnop", sanitized3)
        self.assertIn("[REDACTED]", sanitized3)

        # Google AIza style
        text4 = "Key AIzaSyAbcdef1234567890GHIJKLMN-opqrst is invalid"
        sanitized4 = redact_sensitive_text(text4)
        self.assertNotIn("AIzaSyAbcdef1234567890GHIJKLMN-opqrst", sanitized4)
        self.assertIn("[REDACTED]", sanitized4)

        # Bearer header
        text5 = "Authorization: Bearer ya29.a0AfH6SMBabcdef1234567890uvwxyz"
        sanitized5 = redact_sensitive_text(text5)
        self.assertNotIn("ya29.a0AfH6SMBabcdef1234567890uvwxyz", sanitized5)
        self.assertIn("[REDACTED_TOKEN]", sanitized5)

    def test_registered_profile_secrets(self):
        secret_fact = "Confidential Project Titan Secret"
        register_secret_for_redaction(secret_fact)
        try:
            sample_log = f"User profile contains: {secret_fact} at line 4"
            redacted = redact_sensitive_text(sample_log)
            self.assertNotIn(secret_fact, redacted)
            self.assertIn("[REDACTED_SECRET]", redacted)
        finally:
            unregister_secret_for_redaction(secret_fact)

    def test_logging_filter_and_formatter(self):
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(RedactingFormatter("%(levelname)s: %(message)s"))
        handler.addFilter(RedactingLoggingFilter())

        test_logger = logging.getLogger("test_redact_logger")
        test_logger.setLevel(logging.INFO)
        test_logger.addHandler(handler)
        test_logger.propagate = False

        test_logger.info("Connecting with key %s", "sk-live-secret-key-1234567890abcdef")
        output = stream.getvalue()

        self.assertNotIn("sk-live-secret-key-1234567890abcdef", output)
        self.assertIn("[REDACTED]", output)

if __name__ == "__main__":
    unittest.main()

