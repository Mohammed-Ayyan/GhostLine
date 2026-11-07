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

logger = logging.getLogger("ghostline.providers.anthropic")


class AnthropicProvider(BaseAIProvider):
    """
    Adapter for Anthropic Claude Messages API.
    Supports Claude 3.5 Haiku, Claude 3.5 Sonnet, and Claude 3 Haiku.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 60.0
    ):
        meta = ProviderMetadata(
            id="anthropic",
            name="Anthropic Claude",
            description="Anthropic's Claude 3.5 models with industry-leading code reasoning and nuanced explanation.",
            is_local=False,
            requires_api_key=True,
            default_model=default_model or "claude-3-5-haiku-20241022",
            recommended_models=[
                "claude-3-5-haiku-20241022",
                "claude-3-5-sonnet-20241022",
                "claude-3-haiku-20240307"
            ],
            default_base_url="https://api.anthropic.com",
            pricing_note="Pay-as-you-go per token via Anthropic Console credits.",
            privacy_note="Cloud provider: Subject to Anthropic Commercial Terms of Service.",
            docs_url="https://console.anthropic.com/settings/keys"
        )
        super().__init__(
            metadata=meta,
            api_key=api_key,
            base_url=base_url or meta.default_base_url,
            default_model=meta.default_model,
            timeout=timeout
        )

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self.api_key.strip(),
            "anthropic-version": "2023-06-01",
            "User-Agent": GHOSTLINE_USER_AGENT
        }

    def _format_error(self, resp: requests.Response) -> str:
        try:
            data = resp.json()
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    return f"{err.get('type', '')}: {err.get('message', '')}"
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
                f"No API key configured for {self.name}. Please enter your Anthropic API key in Settings.",
                provider_id=self.id,
                is_auth_error=True
            )

        selected_model = model or self.default_model
        endpoint = f"{self.base_url}/v1/messages"

        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
        if system:
            payload["system"] = system

        try:
            resp = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=self.timeout)
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

            data = resp.json()
            content = data.get("content", [])
            return "".join(c.get("text", "") for c in content if c.get("type") == "text")
        except requests.exceptions.Timeout as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=selected_model, endpoint_url=endpoint)
            self.last_error_info = info
            raise ProviderError(info.friendly_message, info=info, provider_id=self.id)
        except requests.exceptions.ConnectionError as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=selected_model, endpoint_url=endpoint)
            self.last_error_info = info
            raise ProviderError(info.friendly_message, info=info, provider_id=self.id)

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
            raise ProviderError(f"No API key configured for {self.name}.", provider_id=self.id, is_auth_error=True)

        selected_model = model or self.default_model
        endpoint = f"{self.base_url}/v1/messages"

        payload: Dict[str, Any] = {
            "model": selected_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }
        if system:
            payload["system"] = system

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
                err_text = self._format_error(resp)
                raise ProviderError(f"Anthropic error ({resp.status_code}): {err_text}", provider_id=self.id, status_code=resp.status_code)

            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="replace") if isinstance(line, (bytes, bytearray)) else str(line)
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    try:
                        chunk = json.loads(data_str)
                        ev_type = chunk.get("type", "")
                        if ev_type == "content_block_delta":
                            delta = chunk.get("delta", {})
                            token = delta.get("text", "")
                            if token:
                                full_text += token
                                if stream_callback:
                                    stream_callback(token)
                    except Exception:
                        pass
            return full_text
        except requests.exceptions.Timeout:
            raise ProviderError("Anthropic streaming timed out.", provider_id=self.id)
        except requests.exceptions.ConnectionError:
            raise ProviderError("Network error connecting to Anthropic.", provider_id=self.id)

    def test_connection(self) -> Tuple[bool, str]:
        if not self.api_key:
            return False, "No API key set for Anthropic Claude. Please enter your API key."

        t0 = time.perf_counter()
        try:
            endpoint = f"{self.base_url}/v1/messages"
            payload = {
                "model": self.default_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5,
                "temperature": 0.0
            }
            resp = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=12.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            if resp.status_code == 200:
                self.last_error_info = None
                return True, f"Connected to Anthropic Claude ({elapsed_ms:.0f}ms). Model '{self.default_model}' is ready."

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
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=self.default_model, endpoint_url=f"{self.base_url}/v1/messages")
            self.last_error_info = info
            return False, info.friendly_message
        except requests.exceptions.ConnectionError as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=self.default_model, endpoint_url=f"{self.base_url}/v1/messages")
            self.last_error_info = info
            return False, info.friendly_message
        except Exception as e:
            return False, f"Error: {e}"

    def list_models(self) -> List[str]:
        # Anthropic provides a /v1/models endpoint in recent API versions
        if not self.api_key:
            return self.metadata.recommended_models
        try:
            endpoint = f"{self.base_url}/v1/models"
            resp = requests.get(endpoint, headers=self._get_headers(), timeout=6.0)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                if models:
                    rec = [m for m in self.metadata.recommended_models if m in models]
                    others = [m for m in models if m not in self.metadata.recommended_models]
                    return rec + others
        except Exception:
            pass
        return self.metadata.recommended_models

