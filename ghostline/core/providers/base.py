import abc
import logging
import time
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List, Tuple

from ghostline.core.llm_client import (
    AnswerResult,
    OllamaClient,
    classify_question_type,
    log_safe_code_diagnostic
)
from ghostline.core.http_client import (
    GHOSTLINE_USER_AGENT,
    ProviderErrorInfo,
    ProviderError,
    classify_provider_error,
    build_sanitized_diagnostics,
    get_shared_session,
    redact_secrets
)

logger = logging.getLogger("ghostline.providers")

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def is_loopback_host(url: str) -> bool:
    """Checks if a URL points to local machine loopback."""
    if not url:
        return False
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = (parsed.hostname or "").lower()
        return host in LOOPBACK_HOSTS or host.endswith(".localhost")
    except Exception:
        return False


def validate_provider_endpoint(
    base_url: str,
    is_local: bool,
    default_base_url: str = "",
    confirmed_hosts: Optional[List[str]] = None
) -> Tuple[bool, str]:
    """
    Validates provider endpoint URL against security rules:
    - Must use HTTP or HTTPS.
    - Cloud providers (is_local=False) MUST use HTTPS unless connecting to local loopback.
    - Non-default custom hosts sending API keys must be explicitly user-confirmed.
    Returns: (is_valid: bool, error_or_warning: str)
    """
    clean_url = (base_url or "").strip()
    if not clean_url:
        return False, "Endpoint URL cannot be empty."

    try:
        parsed = urlparse(clean_url if "://" in clean_url else f"http://{clean_url}")
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()
    except Exception as e:
        return False, f"Invalid endpoint URL structure: {e}"

    if scheme not in ("http", "https"):
        return False, f"Insecure URL scheme '{scheme}'. Only HTTP and HTTPS are permitted."

    # Cloud providers must use HTTPS unless loopback
    if not is_local:
        if scheme != "https" and not is_loopback_host(clean_url):
            return False, (
                f"Insecure transport: Cloud provider endpoints must use HTTPS. "
                f"Plain HTTP is only permitted for local loopback development."
            )

    # Check non-default host confirmation
    if default_base_url:
        try:
            default_parsed = urlparse(default_base_url)
            default_host = (default_parsed.hostname or "").lower()
        except Exception:
            default_host = ""

        if default_host and host and host != default_host and not is_loopback_host(clean_url):
            confirmed = [h.lower() for h in (confirmed_hosts or [])]
            if host not in confirmed:
                return True, f"UNCONFIRMED_HOST:{host}"

    return True, ""


@dataclass
class ProviderMetadata:
    id: str
    name: str
    description: str
    is_local: bool
    requires_api_key: bool
    default_model: str
    recommended_models: List[str] = field(default_factory=list)
    default_base_url: str = ""
    pricing_note: str = ""
    privacy_note: str = ""
    docs_url: str = ""


class ProviderError(Exception):
    """Base exception for AI provider errors."""
    def __init__(self, message: str, provider_id: str, status_code: Optional[int] = None, is_auth_error: bool = False, is_quota_error: bool = False):
        super().__init__(message)
        self.provider_id = provider_id
        self.status_code = status_code
        self.is_auth_error = is_auth_error
        self.is_quota_error = is_quota_error


class BaseAIProvider(abc.ABC):
    """
    Abstract base class for all Ghostline AI Providers.
    Standardizes text generation, structured question solving, model querying,
    and connection health diagnostics.
    """
    def __init__(
        self,
        metadata: ProviderMetadata,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 60.0
    ):
        self.metadata = metadata
        self.api_key = api_key or ""
        self.base_url = (base_url or metadata.default_base_url).rstrip("/")
        self.default_model = default_model or metadata.default_model
        self.timeout = timeout
        self.last_prompt = ""
        self.http = get_shared_session()
        self.last_error_info: Optional[ProviderErrorInfo] = None
        # Internal parser helper for prompt formatting and structured response extraction
        self._llm_helper = OllamaClient(base_url="http://127.0.0.1:11434", default_model=self.default_model)

    def get_diagnostics(self, images_included: bool = False, profile_context_included: bool = False) -> str:
        """Returns sanitized diagnostic report block safe for clipboard copy."""
        info = self.last_error_info or ProviderErrorInfo(
            status_code=None,
            error_category="none",
            friendly_message="No recent provider error recorded.",
            action_type="check_connection",
            action_label="Check connection",
            action_target="",
            raw_error="",
            provider_id=self.id,
            model_name=self.default_model,
            host=self.base_url
        )
        return build_sanitized_diagnostics(
            info=info,
            provider_id=self.id,
            model=self.default_model,
            endpoint_url=self.base_url,
            images_included=images_included,
            profile_context_included=profile_context_included
        )

    def validate_model(self, model_name: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Validates whether model_name exists on provider's live models list.
        Returns: (is_valid: bool, human_message: str, suggested_model: Optional[str])
        """
        target = (model_name or self.default_model or "").strip()
        if not target:
            suggested = self.metadata.default_model
            return False, "No model specified.", suggested

        try:
            live_models = self.list_models()
            if not live_models:
                # If cannot fetch, default to valid with caveat
                return True, f"Model '{target}' configured (models list unverified).", None

            clean_target = target.lower().strip()
            for m in live_models:
                if m.lower().strip() == clean_target:
                    return True, f"Model '{target}' verified active on {self.name}.", None

            # Model not found in live list
            suggested = None
            for rec in self.metadata.recommended_models:
                if any(m.lower().strip() == rec.lower().strip() for m in live_models):
                    suggested = rec
                    break
            if not suggested and live_models:
                suggested = live_models[0]

            msg = f"Model '{target}' isn't available for this key on {self.name}; it may have been retired."
            return False, msg, suggested
        except Exception as e:
            return True, f"Configured model '{target}' (validation warning: {e}).", None

    def validate_endpoint_security(self, confirmed_hosts: Optional[List[str]] = None) -> Tuple[bool, str]:
        """Validates transport encryption and host authorization according to security policy."""
        return validate_provider_endpoint(
            self.base_url,
            is_local=self.metadata.is_local,
            default_base_url=self.metadata.default_base_url,
            confirmed_hosts=confirmed_hosts
        )

    def _ensure_endpoint_safe(self, confirmed_hosts: Optional[List[str]] = None) -> None:
        ok, reason = self.validate_endpoint_security(confirmed_hosts=confirmed_hosts)
        if not ok:
            raise ProviderError(f"Security Policy Rejection: {reason}", provider_id=self.id)
        if reason.startswith("UNCONFIRMED_HOST:"):
            host = reason.split(":", 1)[1]
            raise ProviderError(
                f"Security Warning: Transmission of API key to non-default host '{host}' requires explicit confirmation.",
                provider_id=self.id,
                is_auth_error=True
            )

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def name(self) -> str:
        return self.metadata.name

    def is_available(self) -> bool:
        """Returns True if the provider is configured and reachable."""
        if self.metadata.requires_api_key and not self.api_key:
            return False
        try:
            ok, _ = self.test_connection()
            return ok
        except Exception:
            return False

    @abc.abstractmethod
    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        """Generates plain text response for conversational or open-ended prompts."""
        pass

    @abc.abstractmethod
    def generate_stream(
        self,
        prompt: str,
        stream_callback: Callable[[str], None],
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        """Generates streaming text response, calling stream_callback for each token chunk."""
        pass

    @abc.abstractmethod
    def test_connection(self) -> Tuple[bool, str]:
        """
        Tests connectivity and authentication by performing a lightweight API call.
        Returns: (success: bool, human_readable_message: str)
        """
        pass

    @abc.abstractmethod
    def list_models(self) -> List[str]:
        """Queries the provider API for available models. Returns empty or recommended list on error."""
        pass

    def select_model_for_type(self, question_type: str, preferred_model: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """Selects optimal model for the given question type."""
        model = preferred_model or self.default_model
        return model, None

    def solve_question(
        self,
        question_text: str,
        options: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
        is_unlabelled_mcq: bool = False,
        supporting_passage: str = "",
        constraints: Optional[List[str]] = None,
        examples: Optional[List[Dict[str, str]]] = None,
        input_format: str = "",
        output_format: str = "",
        starter_code: str = "",
        requested_language: str = "",
        question_type: Optional[str] = None
    ) -> AnswerResult:
        """
        Submits question and options to the provider, parses structured output,
        and returns an AnswerResult matching Ghostline's pipeline contract.
        """
        selected_model = model or self.default_model
        q_type = question_type or classify_question_type(question_text, options)

        # 1. Build standardized prompt using Ghostline's structured prompt builder
        prompt = self._llm_helper._construct_prompt(
            question_text,
            options,
            is_unlabelled_mcq=is_unlabelled_mcq,
            supporting_passage=supporting_passage,
            question_type=q_type,
            constraints=constraints,
            examples=examples,
            input_format=input_format,
            output_format=output_format,
            starter_code=starter_code,
            requested_language=requested_language
        )
        self.last_prompt = prompt

        temperature = 0.0 if q_type in ("output_prediction", "coding", "programming") else 0.1
        max_tokens = 2048 if q_type in ("coding", "programming") else 600

        try:
            if stream_callback:
                raw_response = self.generate_stream(
                    prompt=prompt,
                    stream_callback=stream_callback,
                    model=selected_model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                raw_response = self.generate(
                    prompt=prompt,
                    model=selected_model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
        except Exception as e:
            logger.error("[%s] API inference failed: %s", self.name, e)
            err_msg = str(e)
            info = getattr(e, "info", None) or self.last_error_info
            diag_text = self.get_diagnostics()
            return AnswerResult(
                source_option_label="Uncertain",
                answer_option="Uncertain",
                explanation=info.friendly_message if info else f"{self.name} error: {err_msg}",
                is_validated=False,
                validation_status="error",
                error=info.friendly_message if info else err_msg,
                question_type=q_type,
                model_name=selected_model,
                raw_response="",
                error_info=info,
                diagnostics_text=diag_text
            )

        log_safe_code_diagnostic(f"1. Raw {self.name} Response", raw_response)

        # Parse and validate response using Ghostline's structured parser
        result = self._llm_helper._parse_and_validate_response(
            raw_response,
            options,
            is_unlabelled_mcq=is_unlabelled_mcq,
            question_text=question_text,
            question_type=q_type,
            requested_language=requested_language
        )
        result.model_name = selected_model
        return result

