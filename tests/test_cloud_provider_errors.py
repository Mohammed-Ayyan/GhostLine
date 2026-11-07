"""
Tests for Cloud Provider Error Handling, Cloudflare User-Agent blocks,
xAI / Groq error mapping, model validation, and diagnostics redaction.
"""

import time
import pytest
import requests

from tools.e2e.fake_cloud import FakeCloudRunner
from ghostline.core.http_client import (
    GHOSTLINE_USER_AGENT,
    classify_provider_error,
    build_sanitized_diagnostics,
    redact_secrets,
    ProviderErrorInfo
)
from ghostline.core.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
    GroqProvider,
    XAIProvider
)
from ghostline.core.providers.base import ProviderMetadata

FAKE_CLOUD_PORT = 11438


@pytest.fixture(scope="module")
def fake_cloud():
    runner = FakeCloudRunner(host="127.0.0.1", port=FAKE_CLOUD_PORT)
    assert runner.start(), f"Failed to start FakeCloud server on port {FAKE_CLOUD_PORT}"
    time.sleep(0.1)
    yield runner
    runner.stop()


def test_regression_cloudflare_user_agent_block(fake_cloud):
    """
    REGRESSION TEST:
    Default Python agent (python-requests) triggers Cloudflare 403 error code 1010.
    Ghostline User-Agent bypasses Cloudflare block and gets 200 OK.
    """
    url = f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1/chat/completions?cloudflare-block-test=1"

    # 1. Default Python agent -> 403 Cloudflare block
    resp_default = requests.post(
        url,
        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "hi"}]},
        headers={"User-Agent": "python-requests/2.31.0", "Authorization": "Bearer test-key"}
    )
    assert resp_default.status_code == 403
    assert "error code: 1010" in resp_default.text
    info_blocked = classify_provider_error("groq", resp_default.status_code, resp_default.text)
    assert info_blocked.error_category == "blocked_cloudflare"
    assert info_blocked.friendly_message == "The request was blocked before reaching the provider."
    assert info_blocked.action_type == "copy_diagnostics"

    # 2. Ghostline User-Agent via GroqProvider -> 200 OK
    prov = GroqProvider(
        api_key="valid-test-key",
        base_url=f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1"
    )
    # Ensure provider sends Ghostline User-Agent
    assert "User-Agent" in prov._get_headers()
    assert prov._get_headers()["User-Agent"] == GHOSTLINE_USER_AGENT

    # Call generate through REAL provider
    ans = prov.generate(prompt="hi", model="llama-3.3-70b-versatile")
    assert "Hello from Cloud Provider!" in ans


def test_groq_403_ineligible_mapping(fake_cloud):
    """
    Verifies that Groq-style 403 (organization restricted / not eligible)
    maps to a friendly console guidance message with action [Open provider console].
    """
    prov = GroqProvider(
        api_key="groq-ineligible-key",
        base_url=f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1"
    )
    with pytest.raises(Exception) as excinfo:
        prov.generate(prompt="test question")

    err = excinfo.value
    info = getattr(err, "info", None) or prov.last_error_info
    assert info is not None
    assert info.status_code == 403
    assert info.action_type == "open_console"
    assert "console.groq.com" in info.action_target
    assert "Your account or region may not be allowed to use this provider or model" in info.friendly_message


def test_xai_403_insufficient_credits_mapping(fake_cloud):
    """
    Verifies that xAI 403 indicating team missing credits maps to
    'No credits/licence on this xAI team: add credits at console.x.ai'.
    """
    prov = XAIProvider(
        api_key="xai-nocredits-key",
        base_url=f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1"
    )
    with pytest.raises(Exception) as excinfo:
        prov.generate(prompt="solve this")

    err = excinfo.value
    info = getattr(err, "info", None) or prov.last_error_info
    assert info is not None
    assert info.status_code == 403
    assert info.error_category == "xai_credits_exhausted"
    assert "No credits/licence on this xAI team: add credits at console.x.ai" in info.friendly_message
    assert info.action_target == "https://console.x.ai"


def test_401_invalid_key_mapping(fake_cloud):
    """Verifies that 401 returns 'That API key was rejected' [Edit key]."""
    prov = GroqProvider(
        api_key="test-401-invalid-key",
        base_url=f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1"
    )
    with pytest.raises(Exception) as excinfo:
        prov.generate(prompt="hi")

    err = excinfo.value
    info = getattr(err, "info", None) or prov.last_error_info
    assert info is not None
    assert info.status_code == 401
    assert info.friendly_message == "That API key was rejected."
    assert info.action_type == "edit_key"
    assert info.action_label == "Edit key"


def test_404_retired_model_mapping(fake_cloud):
    """Verifies that 404 returns 'That model isn't available for this key; it may have been retired.'"""
    prov = GroqProvider(
        api_key="valid-key",
        base_url=f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1"
    )
    with pytest.raises(Exception) as excinfo:
        prov.generate(prompt="test", model="retired-model-v1")

    err = excinfo.value
    info = getattr(err, "info", None) or prov.last_error_info
    assert info is not None
    assert info.status_code == 404
    assert info.friendly_message == "That model isn't available for this key; it may have been retired."
    assert info.action_type == "fetch_models"


def test_429_rate_limit_with_retry_after(fake_cloud):
    """Verifies that 429 returns 'Rate limited; retrying in N s'."""
    prov = GroqProvider(
        api_key="test-429-key",
        base_url=f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1"
    )
    with pytest.raises(Exception) as excinfo:
        prov.generate(prompt="spam requests")

    err = excinfo.value
    info = getattr(err, "info", None) or prov.last_error_info
    assert info is not None
    assert info.status_code == 429
    assert "Rate limited" in info.friendly_message
    assert info.retry_after_sec == 4


def test_model_validity_check(fake_cloud):
    """
    Verifies validate_model checks against live models endpoint
    and suggests active models when configured model is retired.
    """
    prov = GroqProvider(
        api_key="valid-key",
        base_url=f"http://127.0.0.1:{FAKE_CLOUD_PORT}/v1"
    )
    # 1. Valid model
    is_valid, msg, suggested = prov.validate_model("llama-3.3-70b-versatile")
    assert is_valid is True
    assert suggested is None

    # 2. Retired / Unknown model
    is_valid, msg, suggested = prov.validate_model("ancient-retired-model-1999")
    assert is_valid is False
    assert "it may have been retired" in msg
    assert suggested in ("llama-3.3-70b-versatile", "llama-3.1-8b-instant")


def test_diagnostics_sanitization_and_redaction():
    """
    Verifies that 'Copy diagnostics' redacts all API keys, bearer tokens,
    and never leaks prompts or user profiles.
    """
    info = ProviderErrorInfo(
        status_code=403,
        error_category="permission",
        friendly_message="Account restricted.",
        action_type="open_console",
        action_label="Open console",
        action_target="https://console.groq.com",
        raw_error="Failed with gsk_abcdef1234567890qwerty and xai-998877665544332211 and sk-proj-1234567890abcdef and AIzaSyABCDEF12345678901234567890 and Bearer secret_bearer_token",
        request_id="req_test_123",
        provider_id="groq",
        model_name="llama-3.3-70b-versatile",
        host="api.groq.com"
    )
    diag = build_sanitized_diagnostics(
        info=info,
        provider_id="groq",
        model="llama-3.3-70b-versatile",
        endpoint_url="https://api.groq.com/openai/v1",
        images_included=False,
        profile_context_included=True
    )

    # Asserts that all secret keys are redacted
    assert "gsk_" not in diag
    assert "xai-" not in diag
    assert "sk-proj" not in diag
    assert "AIza" not in diag
    assert "secret_bearer_token" not in diag
    assert "[REDACTED]" in diag

    # Asserts endpoint HOST only
    assert "api.groq.com" in diag
    assert "/openai/v1" not in diag  # Path must not be in Endpoint Host line

    # Asserts metadata present
    assert "Ghostline" in diag
    assert "User-Agent Sent: Ghostline/" in diag
    assert "Images Included: No" in diag
    assert "Profile Context Included: Yes" in diag
    assert "req_test_123" in diag
