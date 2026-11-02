import unittest
from ghostline.core.providers.base import validate_provider_endpoint, is_loopback_host

class TestEndpointSecurity(unittest.TestCase):
    def test_loopback_detection(self):
        self.assertTrue(is_loopback_host("http://127.0.0.1:11434"))
        self.assertTrue(is_loopback_host("http://localhost:8080"))
        self.assertTrue(is_loopback_host("http://[::1]:5000"))
        self.assertFalse(is_loopback_host("https://api.openai.com"))
        self.assertFalse(is_loopback_host("http://192.168.1.50:11434"))
        self.assertFalse(is_loopback_host("http://evil.com"))

    def test_cloud_provider_https_enforcement(self):
        # Cloud provider with valid HTTPS
        valid, _ = validate_provider_endpoint(
            "https://api.openai.com/v1",
            is_local=False,
            default_base_url="https://api.openai.com/v1"
        )
        self.assertTrue(valid)

        # Cloud provider with plain HTTP to remote host must be rejected
        valid_http, err = validate_provider_endpoint(
            "http://api.openai.com/v1",
            is_local=False,
            default_base_url="https://api.openai.com/v1"
        )
        self.assertFalse(valid_http)
        self.assertIn("must use HTTPS", err)

        # Cloud provider with HTTP to local loopback (dev proxy) is allowed
        valid_loop, _ = validate_provider_endpoint(
            "http://127.0.0.1:8000/v1",
            is_local=False,
            default_base_url="https://api.openai.com/v1"
        )
        self.assertTrue(valid_loop)

    def test_insecure_schemes_rejected(self):
        for bad in ["file:///etc/passwd", "ftp://example.com", "gopher://evil.com"]:
            valid, err = validate_provider_endpoint(bad, is_local=False)
            self.assertFalse(valid)
            self.assertIn("Only HTTP and HTTPS are permitted", err)

    def test_unconfirmed_host_warning(self):
        # Non-default host without confirmation
        valid, warn = validate_provider_endpoint(
            "https://custom-proxy.internal.net/v1",
            is_local=False,
            default_base_url="https://api.openai.com/v1",
            confirmed_hosts=[]
        )
        self.assertTrue(valid)
        self.assertTrue(warn.startswith("UNCONFIRMED_HOST:custom-proxy.internal.net"))

        # Once confirmed, no warning
        valid_conf, warn_conf = validate_provider_endpoint(
            "https://custom-proxy.internal.net/v1",
            is_local=False,
            default_base_url="https://api.openai.com/v1",
            confirmed_hosts=["custom-proxy.internal.net"]
        )
        self.assertTrue(valid_conf)
        self.assertEqual(warn_conf, "")

if __name__ == "__main__":
    unittest.main()
