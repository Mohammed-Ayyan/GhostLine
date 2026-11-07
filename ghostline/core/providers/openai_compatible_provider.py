import time
import json
import logging
from typing import Optional, Callable, Dict, Any, List, Tuple
import requests

from .base import BaseAIProvider, ProviderMetadata
from ghostline.core.http_client import (
    GHOSTLINE_USER_AGENT,
    ProviderError,
    ProviderErrorInfo,
    classify_provider_error,
    redact_secrets
)

logger = logging.getLogger("ghostline.providers.openai_compat")


class OpenAICompatibleProvider(BaseAIProvider):
    """
    Adapter for any OpenAI-compatible Chat Completions API.
    Supports Groq, OpenRouter, OpenAI, and xAI Grok.
    """
    def __init__(
        self,
        metadata: ProviderMetadata,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        timeout: float = 60.0
    ):
        super().__init__(
            metadata=metadata,
            api_key=api_key,
            base_url=base_url,
            default_model=default_model,
            timeout=timeout
        )
        self.extra_headers = extra_headers or {}

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.strip()}",
            "User-Agent": GHOSTLINE_USER_AGENT
        }
        if self.default_model:
            headers["X-Model-Name"] = self.default_model
        headers.update(self.extra_headers)
        return headers

    def _headers(self) -> Dict[str, str]:
        return self._get_headers()

    def _format_error(self, resp: requests.Response) -> str:
        try:
            data = resp.json()
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    return redact_secrets(err.get("message", str(err)))
                return redact_secrets(str(err))
        except Exception:
            pass
        return redact_secrets(resp.text[:200])

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        if not self.api_key:
            info = ProviderErrorInfo(
                status_code=None,
                error_category="missing_api_key",
                friendly_message=f"No API key configured for {self.name}. Please enter your key in Settings -> AI Provider.",
                action_type="edit_key",
                action_label="Edit key",
                action_target="settings_ai_provider",
                raw_error="",
                provider_id=self.id,
                model_name=model or self.default_model,
                host=self.base_url
            )
            self.last_error_info = info
            raise ProviderError(info.friendly_message, info=info, provider_id=self.id)

        selected_model = model or self.default_model
        endpoint = f"{self.base_url}/chat/completions"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        is_reasoning_model = selected_model.lower().startswith(("o1", "o3"))
        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "stream": False
        }
        if is_reasoning_model:
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = temperature

        # Bounded retry loop for 429 rate limit
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                resp = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if not choices:
                        return ""
                    return choices[0].get("message", {}).get("content", "")

                info = classify_provider_error(
                    self.id,
                    resp.status_code,
                    resp.text,
                    dict(resp.headers),
                    model_name=selected_model,
                    endpoint_url=endpoint
                )
                self.last_error_info = info

                # Handle 429 retry-after if bounded and first attempt
                if resp.status_code == 429 and attempt < max_attempts - 1 and info.retry_after_sec and 0 < info.retry_after_sec <= 6:
                    logger.info("Rate limited by %s. Retrying in %ds...", self.name, info.retry_after_sec)
                    time.sleep(info.retry_after_sec)
                    continue

                raise ProviderError(info.friendly_message, info=info, provider_id=self.id, status_code=resp.status_code)

            except requests.exceptions.Timeout as ex:
                info = classify_provider_error(self.id, None, "", exception=ex, model_name=selected_model, endpoint_url=endpoint)
                self.last_error_info = info
                raise ProviderError(info.friendly_message, info=info, provider_id=self.id)
            except requests.exceptions.ConnectionError as ex:
                info = classify_provider_error(self.id, None, "", exception=ex, model_name=selected_model, endpoint_url=endpoint)
                self.last_error_info = info
                raise ProviderError(info.friendly_message, info=info, provider_id=self.id)

        return ""

    def generate_stream(
        self,
        prompt: str,
        stream_callback: Callable[[str], None],
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        if not self.api_key:
            info = ProviderErrorInfo(
                status_code=None,
                error_category="missing_api_key",
                friendly_message=f"No API key configured for {self.name}.",
                action_type="edit_key",
                action_label="Edit key",
                action_target="settings_ai_provider",
                raw_error="",
                provider_id=self.id,
                model_name=model or self.default_model,
                host=self.base_url
            )
            self.last_error_info = info
            raise ProviderError(info.friendly_message, info=info, provider_id=self.id)

        selected_model = model or self.default_model
        endpoint = f"{self.base_url}/chat/completions"

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        is_reasoning_model = selected_model.lower().startswith(("o1", "o3"))
        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "stream": True
        }
        if is_reasoning_model:
            payload["max_completion_tokens"] = max_tokens
        else:
            payload["max_tokens"] = max_tokens
            payload["temperature"] = temperature

        full_text = ""
        try:
            resp = requests.post(
                endpoint,
                json=payload,
                headers=self._get_headers(),
                stream=True,
                timeout=self.timeout
            )
            if resp.status_code != 200:
                info = classify_provider_error(
                    self.id,
                    resp.status_code,
                    resp.text,
                    dict(resp.headers),
                    model_name=selected_model,
                    endpoint_url=endpoint
                )
                self.last_error_info = info
                raise ProviderError(info.friendly_message, info=info, provider_id=self.id, status_code=resp.status_code)

            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="replace") if isinstance(line, (bytes, bytearray)) else str(line)
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                full_text += token
                                if stream_callback:
                                    stream_callback(token)
                    except Exception:
                        pass
            return full_text
        except requests.exceptions.Timeout as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=selected_model, endpoint_url=endpoint)
            self.last_error_info = info
            raise ProviderError(info.friendly_message, info=info, provider_id=self.id)
        except requests.exceptions.ConnectionError as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=selected_model, endpoint_url=endpoint)
            self.last_error_info = info
            raise ProviderError(info.friendly_message, info=info, provider_id=self.id)

    def test_connection(self) -> Tuple[bool, str]:
        """
        Tests connectivity and authentication by performing the cheapest valid API call.
        Checks /models first, then lightweight 1-token query.
        Returns: (success: bool, friendly_message: str)
        """
        if not self.api_key:
            return False, f"No API key set for {self.name}. Please enter your key first."

        t0 = time.perf_counter()
        # 1. Cheapest call: models list (0 inference tokens)
        try:
            endpoint = f"{self.base_url}/models"
            resp = requests.get(endpoint, headers=self._get_headers(), timeout=10.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            if resp.status_code == 200:
                self.last_error_info = None
                return True, f"Connected to {self.name} ({elapsed_ms:.0f}ms). API key is valid and responsive."

            info = classify_provider_error(
                self.id,
                resp.status_code,
                resp.text,
                dict(resp.headers),
                model_name=self.default_model,
                endpoint_url=endpoint
            )
            self.last_error_info = info
            return False, info.friendly_message

        except requests.exceptions.Timeout as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=self.default_model, endpoint_url=f"{self.base_url}/models")
            self.last_error_info = info
            return False, info.friendly_message
        except requests.exceptions.ConnectionError as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=self.default_model, endpoint_url=f"{self.base_url}/models")
            self.last_error_info = info
            return False, info.friendly_message
        except Exception as e:
            return False, f"Connection test failed: {e}"

    def list_models(self) -> List[str]:
        if not self.api_key:
            return self.metadata.recommended_models
        try:
            endpoint = f"{self.base_url}/models"
            resp = requests.get(endpoint, headers=self._get_headers(), timeout=8.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                if models:
                    rec = [m for m in self.metadata.recommended_models if m in models]
                    others = [m for m in models if m not in self.metadata.recommended_models]
                    return rec + others[:40]
            else:
                info = classify_provider_error(
                    self.id,
                    resp.status_code,
                    resp.text,
                    dict(resp.headers),
                    model_name="",
                    endpoint_url=endpoint
                )
                self.last_error_info = info
        except Exception as e:
            logger.warning("Error fetching models for %s: %s", self.name, e)
        return self.metadata.recommended_models


class GroqProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, default_model: Optional[str] = None):
        meta = ProviderMetadata(
            id="groq",
            name="Groq",
            description="Ultra-fast LPU inference. Generates answers in under 300ms, ideal for real-time exam solving.",
            is_local=False,
            requires_api_key=True,
            default_model=default_model or "llama-3.3-70b-versatile",
            recommended_models=[
                "llama-3.3-70b-versatile",
                "llama-3.1-8b-instant",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
                "deepseek-r1-distill-llama-70b"
            ],
            default_base_url="https://api.groq.com/openai/v1",
            pricing_note="Generous free tier with high rate limits (~30 RPM).",
            privacy_note="Cloud provider: Data processed on Groq LPUs according to Groq terms.",
            docs_url="https://console.groq.com/keys"
        )
        super().__init__(
            metadata=meta,
            api_key=api_key,
            base_url=base_url or meta.default_base_url,
            default_model=meta.default_model
        )


class OpenRouterProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, default_model: Optional[str] = None):
        meta = ProviderMetadata(
            id="openrouter",
            name="OpenRouter",
            description="Universal AI gateway. Access hundreds of open & proprietary models with a single API key.",
            is_local=False,
            requires_api_key=True,
            default_model=default_model or "meta-llama/llama-3.3-70b-instruct",
            recommended_models=[
                "meta-llama/llama-3.3-70b-instruct",
                "google/gemini-2.0-flash-exp:free",
                "meta-llama/llama-3.1-8b-instruct:free",
                "anthropic/claude-3.5-sonnet",
                "deepseek/deepseek-r1"
            ],
            default_base_url="https://openrouter.ai/api/v1",
            pricing_note="Pay-as-you-go per token, with many completely free models available.",
            privacy_note="Cloud provider: OpenRouter routes requests to your chosen upstream provider.",
            docs_url="https://openrouter.ai/keys"
        )
        super().__init__(
            metadata=meta,
            api_key=api_key,
            base_url=base_url or meta.default_base_url,
            default_model=meta.default_model,
            extra_headers={
                "HTTP-Referer": "https://ghostline.ai",
                "X-Title": "Ghostline Desktop"
            }
        )


class OpenAIProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, default_model: Optional[str] = None):
        meta = ProviderMetadata(
            id="openai",
            name="OpenAI",
            description="Official OpenAI models including GPT-4o and GPT-4o mini.",
            is_local=False,
            requires_api_key=True,
            default_model=default_model or "gpt-4o-mini",
            recommended_models=[
                "gpt-4o-mini",
                "gpt-4o",
                "o3-mini",
                "gpt-3.5-turbo"
            ],
            default_base_url="https://api.openai.com/v1",
            pricing_note="Pay-as-you-go billing with prepaid API credits.",
            privacy_note="Cloud provider: Subject to OpenAI API data privacy policies (API data not used for training).",
            docs_url="https://platform.openai.com/api-keys"
        )
        super().__init__(
            metadata=meta,
            api_key=api_key,
            base_url=base_url or meta.default_base_url,
            default_model=meta.default_model
        )


class XAIProvider(OpenAICompatibleProvider):
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, default_model: Optional[str] = None):
        meta = ProviderMetadata(
            id="xai",
            name="xAI (Grok)",
            description="xAI's Grok models with high reasoning and coding proficiency.",
            is_local=False,
            requires_api_key=True,
            default_model=default_model or "grok-2-1212",
            recommended_models=[
                "grok-2-1212",
                "grok-2-vision-1212",
                "grok-beta"
            ],
            default_base_url="https://api.x.ai/v1",
            pricing_note="Pay-as-you-go via xAI Console credits.",
            privacy_note="Cloud provider: Subject to xAI Developer terms.",
            docs_url="https://console.x.ai/"
        )
        super().__init__(
            metadata=meta,
            api_key=api_key,
            base_url=base_url or meta.default_base_url,
            default_model=meta.default_model
        )
