"""
Ghostline Shared HTTP Client & Error Classification Subsystem.
Centralizes outbound HTTP transport with an explicit, non-impersonating User-Agent,
and normalizes provider error responses into friendly, actionable UI guidance.
Guarantees that HTTP >= 400 is NEVER displayed as an answer or raw JSON/HTML.
"""

import re
import json
import logging
import platform
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ghostline.build_info import VERSION

logger = logging.getLogger("ghostline.http_client")

# Official User-Agent identifying the Ghostline Windows desktop application
GHOSTLINE_USER_AGENT = f"Ghostline/{VERSION} (Windows)"

# Regex patterns for strict redaction of sensitive credentials and tokens
SECRET_PATTERNS = [
    re.compile(r'\bgsk_[a-zA-Z0-9_-]{15,}\b'),       # Groq API keys
    re.compile(r'\bxai-[a-zA-Z0-9_-]{15,}\b'),       # xAI API keys
    re.compile(r'\bsk-[a-zA-Z0-9_-]{15,}\b'),        # OpenAI / OpenRouter keys
    re.compile(r'\bAIza[0-9A-Za-z-_]{20,}\b'),       # Google AI Studio / Gemini keys
    re.compile(r'\bBearer\s+[a-zA-Z0-9_.-]{10,}\b', re.IGNORECASE),  # Authorization Bearer tokens
    re.compile(r'\bapi[_-]?key["\']?\s*[:=]\s*["\']?[a-zA-Z0-9_-]{12,}["\']?', re.IGNORECASE),
]


def redact_secrets(text: str) -> str:
    """
    Sanitizes string by replacing API keys, bearer tokens, and secrets with [REDACTED].
    Safe for log outputs, UI error cards, and user clipboard diagnostics.
    """
    if not text:
        return ""
    sanitized = str(text)
    for pat in SECRET_PATTERNS:
        sanitized = pat.sub("[REDACTED]", sanitized)
    return sanitized


@dataclass
class ProviderErrorInfo:
    status_code: Optional[int]
    error_category: str
    friendly_message: str
    action_type: str        # 'edit_key', 'open_console', 'copy_diagnostics', 'fetch_models', 'choose_model', 'retry', 'check_connection'
    action_label: str
    action_target: str      # URL, route, or button intent
    raw_error: str          # Sanitized and truncated to 500 chars
    request_id: Optional[str] = None
    retry_after_sec: Optional[int] = None
    provider_id: str = ""
    model_name: str = ""
    host: str = ""


class ProviderError(Exception):
    """
    Structured Exception raised when an AI provider call fails.
    Preserves classified ProviderErrorInfo for immediate UI mapping.
    """
    def __init__(self, message: str, info: Optional[ProviderErrorInfo] = None, provider_id: str = "", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.info = info
        self.provider_id = provider_id or (info.provider_id if info else "")
        self.status_code = status_code or (info.status_code if info else None)

    @property
    def is_quota_error(self) -> bool:
        if self.info and self.info.error_category in ("quota_exceeded", "quota", "insufficient_quota"):
            return True
        msg = (self.message or "").lower()
        return "quota" in msg or "billing" in msg or "exceeded" in msg

    @property
    def is_auth_error(self) -> bool:
        if self.info and self.info.error_category in ("invalid_key", "forbidden", "unauthorized"):
            return True
        return self.status_code in (401, 403)


def get_provider_console_url(provider_id: str) -> str:
    """Returns official provider developer console URL."""
    p = (provider_id or "").lower().strip()
    urls = {
        "groq": "https://console.groq.com",
        "xai": "https://console.x.ai",
        "gemini": "https://aistudio.google.com/app/apikey",
        "openai": "https://platform.openai.com/api-keys",
        "openrouter": "https://openrouter.ai/keys",
        "anthropic": "https://console.anthropic.com/settings/keys",
        "ollama": "https://ollama.com"
    }
    return urls.get(p, "https://ghostline.dev")


def classify_provider_error(
    provider_id: str,
    status_code: Optional[int],
    response_text: str,
    headers: Optional[Dict[str, str]] = None,
    exception: Optional[Exception] = None,
    model_name: str = "",
    endpoint_url: str = ""
) -> ProviderErrorInfo:
    """
    Translates raw HTTP errors and exceptions into clear, friendly guidance
    with actionable next steps. Never shows HTTP >= 400 as raw JSON or HTML.
    """
    prov_clean = (provider_id or "provider").lower().strip()
    headers = headers or {}
    req_id = headers.get("x-request-id") or headers.get("cf-ray") or headers.get("request-id")
    
    # Extract host
    host = ""
    if endpoint_url:
        try:
            parsed = urlparse(endpoint_url if "://" in endpoint_url else f"https://{endpoint_url}")
            host = parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            host = endpoint_url

    # Check for retry-after header
    retry_after_sec: Optional[int] = None
    ra_val = headers.get("retry-after") or headers.get("Retry-After")
    if ra_val:
        try:
            retry_after_sec = int(ra_val)
        except Exception:
            pass

    # Extract parsed JSON error message if present
    parsed_msg = ""
    parsed_type = ""
    parsed_code = ""
    if response_text:
        try:
            data = json.loads(response_text)
            if isinstance(data, dict):
                err = data.get("error", {})
                if isinstance(err, dict):
                    parsed_msg = err.get("message", "")
                    parsed_type = err.get("type", "")
                    parsed_code = err.get("code", "")
                elif isinstance(err, str):
                    parsed_msg = err
                if not parsed_msg and "code" in data and isinstance(data.get("error"), str):
                    parsed_msg = data["error"]
        except Exception:
            pass

    raw_clean = redact_secrets(response_text or str(exception or "")).strip()
    if len(raw_clean) > 500:
        raw_clean = raw_clean[:500] + "..."

    console_url = get_provider_console_url(prov_clean)

    # 1. Network / Connection Errors
    if status_code is None:
        ex_str = str(exception or "").lower()
        if "timeout" in ex_str:
            return ProviderErrorInfo(
                status_code=None,
                error_category="timeout",
                friendly_message="The provider took too long to respond. Please check your connection and retry.",
                action_type="retry",
                action_label="Retry",
                action_target="retry",
                raw_error=raw_clean,
                provider_id=prov_clean,
                model_name=model_name,
                host=host
            )
        return ProviderErrorInfo(
            status_code=None,
            error_category="network_error",
            friendly_message="Unable to connect. Please check your internet connection.",
            action_type="check_connection",
            action_label="Check connection",
            action_target="check_connection",
            raw_error=raw_clean,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 2. HTTP 401 — Authentication Failure
    if status_code == 401:
        return ProviderErrorInfo(
            status_code=401,
            error_category="auth_rejected",
            friendly_message="That API key was rejected.",
            action_type="edit_key",
            action_label="Edit key",
            action_target="settings_ai_provider",
            raw_error=raw_clean,
            request_id=req_id,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 3. HTTP 403 — Cloudflare Block (Error 1010 or HTML page)
    is_cf_block = (
        status_code == 403 and (
            "error code: 1010" in raw_clean.lower() or
            "error code 1010" in raw_clean.lower() or
            "<html" in raw_clean.lower() or
            "cloudflare" in raw_clean.lower() and "access denied" in raw_clean.lower()
        )
    )
    if is_cf_block:
        return ProviderErrorInfo(
            status_code=403,
            error_category="blocked_cloudflare",
            friendly_message="The request was blocked before reaching the provider.",
            action_type="copy_diagnostics",
            action_label="Copy diagnostics",
            action_target="copy_diagnostics",
            raw_error=raw_clean,
            request_id=req_id,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 4. HTTP 403 — xAI Team Credits / Eligibility
    combined_err_text = f"{parsed_msg} {parsed_type} {parsed_code} {raw_clean}".lower()
    if prov_clean == "xai" and status_code == 403:
        if "credit" in combined_err_text or "eligible" in combined_err_text or "team" in combined_err_text or "tier" in combined_err_text:
            return ProviderErrorInfo(
                status_code=403,
                error_category="xai_credits_exhausted",
                friendly_message="No credits/licence on this xAI team: add credits at console.x.ai",
                action_type="open_console",
                action_label="Open console.x.ai",
                action_target="https://console.x.ai",
                raw_error=raw_clean,
                request_id=req_id,
                provider_id=prov_clean,
                model_name=model_name,
                host=host
            )

    # 5. HTTP 403 — Generic Permission / Region / Organization Not Eligible
    if status_code == 403:
        return ProviderErrorInfo(
            status_code=403,
            error_category="permission_or_region",
            friendly_message=(
                "Your account or region may not be allowed to use this provider or model; "
                "some providers require accepting terms, adding billing or credits in their console."
            ),
            action_type="open_console",
            action_label="Open provider console",
            action_target=console_url,
            raw_error=raw_clean,
            request_id=req_id,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 6. HTTP 404 — Model Unavailable or Retired
    if status_code == 404:
        return ProviderErrorInfo(
            status_code=404,
            error_category="model_not_found",
            friendly_message="That model isn't available for this key; it may have been retired.",
            action_type="fetch_models",
            action_label="Fetch models",
            action_target="fetch_models",
            raw_error=raw_clean,
            request_id=req_id,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 7. HTTP 400 — Vision / Unsupported Params
    if status_code == 400:
        if "vision" in combined_err_text or "image" in combined_err_text or "multimodal" in combined_err_text:
            msg = "This model can't read images. Please choose a multimodal model."
        else:
            msg = "Invalid request parameter for this model. Try choosing a standard model."
        return ProviderErrorInfo(
            status_code=400,
            error_category="bad_request",
            friendly_message=msg,
            action_type="choose_model",
            action_label="Choose model",
            action_target="choose_model",
            raw_error=raw_clean,
            request_id=req_id,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 8. HTTP 413 — Payload Too Large
    if status_code == 413:
        return ProviderErrorInfo(
            status_code=413,
            error_category="payload_too_large",
            friendly_message="Request too large for this model.",
            action_type="copy_diagnostics",
            action_label="Copy diagnostics",
            action_target="copy_diagnostics",
            raw_error=raw_clean,
            request_id=req_id,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 9. HTTP 429 — Rate Limited / Quota
    if status_code == 429:
        if "quota" in combined_err_text or "billing" in combined_err_text or parsed_code == "insufficient_quota":
            return ProviderErrorInfo(
                status_code=429,
                error_category="quota_exceeded",
                friendly_message="API quota exceeded. Check your plan and billing details.",
                action_type="check_quota",
                action_label="Check billing",
                action_target="billing",
                raw_error=raw_clean,
                request_id=req_id,
                retry_after_sec=None,
                provider_id=prov_clean,
                model_name=model_name,
                host=host
            )
        if retry_after_sec and retry_after_sec > 0:
            msg = f"Rate limited; retrying in {retry_after_sec} s."
        else:
            msg = "Rate limited by provider. Please wait a moment before sending another request."
        return ProviderErrorInfo(
            status_code=429,
            error_category="rate_limited",
            friendly_message=msg,
            action_type="retry",
            action_label="Retry",
            action_target="retry",
            raw_error=raw_clean,
            request_id=req_id,
            retry_after_sec=retry_after_sec,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # 10. HTTP 5xx — Server / Upstream trouble
    if status_code >= 500:
        return ProviderErrorInfo(
            status_code=status_code,
            error_category="server_error",
            friendly_message="Provider is having trouble. Please try again in a few moments.",
            action_type="retry",
            action_label="Retry",
            action_target="retry",
            raw_error=raw_clean,
            request_id=req_id,
            provider_id=prov_clean,
            model_name=model_name,
            host=host
        )

    # Fallback for unexpected codes
    return ProviderErrorInfo(
        status_code=status_code,
        error_category="unexpected_error",
        friendly_message=f"Provider returned status {status_code}.",
        action_type="copy_diagnostics",
        action_label="Copy diagnostics",
        action_target="copy_diagnostics",
        raw_error=raw_clean,
        request_id=req_id,
        provider_id=prov_clean,
        model_name=model_name,
        host=host
    )


def build_sanitized_diagnostics(
    info: Optional[Any] = None,
    provider_id: str = "",
    model: str = "",
    endpoint_url: str = "",
    images_included: bool = False,
    profile_context_included: bool = False,
    **kwargs
) -> str:
    """
    Builds a structured diagnostics block strictly sanitized of secrets, keys,
    prompts, and user profile contents. Safe for clipboard sharing.
    Supports flexible keyword arguments: provider, model_name, endpoint, error_info,
    has_images, has_profile_context, request_id.
    """
    prov_id = provider_id or kwargs.get("provider", "") or (info.provider_id if isinstance(info, ProviderErrorInfo) else "")
    mod_name = model or kwargs.get("model_name", "") or kwargs.get("model", "") or (info.model_name if isinstance(info, ProviderErrorInfo) else "")
    endpoint = endpoint_url or kwargs.get("endpoint", "") or kwargs.get("endpoint_url", "")
    has_img = images_included or kwargs.get("has_images", False)
    has_prof = profile_context_included or kwargs.get("has_profile_context", False)
    err_info = info or kwargs.get("error_info")
    req_id = kwargs.get("request_id", "")

    # Extract endpoint host only (no paths, no query params, no auth)
    host = ""
    try:
        parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
        host = parsed.netloc or parsed.path.split("/")[0]
    except Exception:
        host = endpoint.split("/")[0] if endpoint else "unknown"

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    win_ver = f"{platform.system()} {platform.release()} (Build {platform.version()})"

    if isinstance(err_info, ProviderErrorInfo):
        status_code = err_info.status_code
        err_cat = err_info.error_category
        friendly_msg = err_info.friendly_message
        clean_err = redact_secrets(err_info.raw_error or "None")
        req_id = req_id or err_info.request_id or "None"
        host = host or err_info.host or "unknown"
    elif isinstance(err_info, dict):
        status_code = err_info.get("status_code", "Unknown")
        err_cat = err_info.get("type", "api_error")
        friendly_msg = err_info.get("message", "Error")
        clean_err = redact_secrets(str(err_info.get("message", "None")))
    else:
        status_code = "None"
        err_cat = "diagnostic_capture"
        friendly_msg = "Routine diagnostics check"
        clean_err = redact_secrets(str(err_info or "None"))

    if len(clean_err) > 500:
        clean_err = clean_err[:500] + "..."

    try:
        from ghostline.audio.timing import get_stt_diagnostics_line
        stt_diag = get_stt_diagnostics_line()
    except Exception:
        stt_diag = "STT: faster-whisper [tiny] | int8 | idle"

    lines = [
        "=== Ghostline Provider Diagnostics ===",
        f"App Version: Ghostline {VERSION}",
        f"Provider: {prov_id or 'unknown'}",
        f"Model: {mod_name or 'default'}",
        f"Endpoint Host: {host or 'unknown'}",
        f"HTTP Status: {status_code if status_code is not None else 'Network/Timeout'}",
        f"Error Category: {err_cat}",
        f"Friendly Message: {friendly_msg}",
        f"Provider Error: {clean_err}",
        f"Request ID: {req_id or 'None'}",
        f"Speech Engine: {stt_diag}",
        f"User-Agent Sent: {GHOSTLINE_USER_AGENT}",
        f"Images Included: {'Yes' if has_img else 'No'}",
        f"Profile Context Included: {'Yes' if has_prof else 'No'}",
        f"Timestamp: {now_utc}",
        f"OS Version: {win_ver}",
        "======================================"
    ]
    diag = "\n".join(lines)
    return redact_secrets(diag)


class GhostlineHttpClient:
    """
    Shared requests.Session wrapper enforcing explicit User-Agent and connection pooling.
    """
    _session: Optional[requests.Session] = None

    @classmethod
    def get_session(cls) -> requests.Session:
        if cls._session is None:
            s = requests.Session()
            s.headers.update({
                "User-Agent": GHOSTLINE_USER_AGENT,
                "Accept": "application/json"
            })
            retries = Retry(
                total=2,
                backoff_factor=0.3,
                status_forcelist=[502, 503, 504],
                raise_on_status=False
            )
            adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=20)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            cls._session = s
        return cls._session


def get_shared_session() -> requests.Session:
    """Convenience accessor for shared HTTP session."""
    return GhostlineHttpClient.get_session()
