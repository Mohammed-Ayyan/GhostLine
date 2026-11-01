import time
import json
import logging
from typing import Optional, Callable, Dict, Any, List, Tuple
import requests

from .base import BaseAIProvider, ProviderMetadata, ProviderError

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
            "Authorization": f"Bearer {self.api_key.strip()}"
        }
        headers.update(self.extra_headers)
        return headers

    def _format_error(self, resp: requests.Response) -> str:
        try:
            data = resp.json()
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    return err.get("message", str(err))
                return str(err)
        except Exception:
            pass
        return resp.text[:200]

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        if not self.api_key:
            raise ProviderError(
                f"No API key configured for {self.name}. Please enter your API key in Settings -> AI Provider.",
                provider_id=self.id,
                is_auth_error=True
            )

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

        try:
            resp = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 401 or resp.status_code == 403:
                err_text = self._format_error(resp)
                raise ProviderError(
                    f"Authentication failed for {self.name}: {err_text}",
                    provider_id=self.id,
                    status_code=resp.status_code,
                    is_auth_error=True
                )
            elif resp.status_code == 429:
                err_text = self._format_error(resp)
                retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
                if retry_after:
                    err_text += f" (Retry-After: {retry_after}s)"
                raise ProviderError(
                    f"Quota or rate limit exceeded for {self.name}: {err_text}",
                    provider_id=self.id,
                    status_code=429,
                    is_quota_error=True
                )
            elif resp.status_code != 200:
                err_text = self._format_error(resp)
                raise ProviderError(
                    f"{self.name} API error ({resp.status_code}): {err_text}",
                    provider_id=self.id,
                    status_code=resp.status_code
                )

            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return ""
            return choices[0].get("message", {}).get("content", "")
        except requests.exceptions.Timeout:
            raise ProviderError(f"{self.name} request timed out after {self.timeout}s.", provider_id=self.id)
        except requests.exceptions.ConnectionError:
            raise ProviderError(f"Network error connecting to {self.name} at {self.base_url}.", provider_id=self.id)

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
            raise ProviderError(
                f"No API key configured for {self.name}.",
                provider_id=self.id,
                is_auth_error=True
            )

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
            if resp.status_code == 401 or resp.status_code == 403:
                raise ProviderError(f"Authentication failed: {self._format_error(resp)}", provider_id=self.id, is_auth_error=True)
            elif resp.status_code == 429:
                err_text = self._format_error(resp)
                retry_after = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
                if retry_after:
                    err_text += f" (Retry-After: {retry_after}s)"
                raise ProviderError(f"Quota exceeded: {err_text}", provider_id=self.id, is_quota_error=True)
            elif resp.status_code != 200:
                raise ProviderError(f"{self.name} HTTP {resp.status_code}: {self._format_error(resp)}", provider_id=self.id)

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
        except requests.exceptions.Timeout:
            raise ProviderError(f"{self.name} streaming timed out.", provider_id=self.id)
        except requests.exceptions.ConnectionError:
            raise ProviderError(f"Network error connecting to {self.name}.", provider_id=self.id)

    def test_connection(self) -> Tuple[bool, str]:
        if not self.api_key:
            return False, f"No API key set for {self.name}. Please enter your key first."

        t0 = time.perf_counter()
        try:
            endpoint = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.default_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 4,
                "temperature": 0.0
            }
            resp = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=12.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            if resp.status_code == 200:
                return True, f"Connected to {self.name} ({elapsed_ms:.0f}ms). Model '{self.default_model}' is active and responsive."
            elif resp.status_code in (401, 403):
                return False, f"Authentication failed: {self._format_error(resp)}"
            elif resp.status_code == 429:
                return False, f"Quota/Rate Limit reached: {self._format_error(resp)}"
            elif resp.status_code == 404:
                return False, f"Model '{self.default_model}' not found on {self.name}. Try selecting a different model."
            else:
                return False, f"{self.name} responded with status {resp.status_code}: {self._format_error(resp)}"
        except requests.exceptions.Timeout:
            return False, f"Connection to {self.name} timed out after 12s."
        except requests.exceptions.ConnectionError:
            return False, f"Network error: Unable to reach {self.base_url}."
        except Exception as e:
            return False, f"Error: {e}"

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
                    # Filter and sort so recommended ones come first
                    rec = [m for m in self.metadata.recommended_models if m in models]
                    others = [m for m in models if m not in self.metadata.recommended_models]
                    return rec + others[:40]
        except Exception:
            pass
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

