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

logger = logging.getLogger("ghostline.providers.gemini")


class GeminiProvider(BaseAIProvider):
    """
    Adapter for Google Gemini REST API.
    Supports Gemini 1.5 Flash, 2.0 Flash, and 1.5 Pro.
    Uses official x-goog-api-key header authentication (no keys in URL).
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
        timeout: float = 60.0
    ):
        meta = ProviderMetadata(
            id="gemini",
            name="Google Gemini",
            description="Google's state-of-the-art multimodal AI with massive context and rapid inference.",
            is_local=False,
            requires_api_key=True,
            default_model=default_model or "gemini-1.5-flash",
            recommended_models=[
                "gemini-1.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-pro"
            ],
            default_base_url="https://generativelanguage.googleapis.com",
            pricing_note="Free tier available (15 RPM / 1M TPM) via Google AI Studio.",
            privacy_note="Cloud provider: Processed on Google Cloud servers according to Google AI Studio Terms.",
            docs_url="https://aistudio.google.com/app/apikey"
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
            "x-goog-api-key": self.api_key.strip(),
            "User-Agent": GHOSTLINE_USER_AGENT
        }

    def _format_error(self, resp: requests.Response) -> str:
        try:
            data = resp.json()
            if "error" in data:
                err = data["error"]
                if isinstance(err, dict):
                    msg = err.get("message", "")
                    status = err.get("status", "")
                    return f"{status}: {msg}" if status else msg
                return str(err)
        except Exception:
            pass
        return resp.text[:200]

    def _clean_model_name(self, model: str) -> str:
        m = model.strip()
        if m.startswith("models/"):
            return m[7:]
        return m

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
                f"No API key configured for {self.name}. Please enter your Gemini API key in Settings.",
                provider_id=self.id,
                is_auth_error=True
            )

        model_name = self._clean_model_name(model or self.default_model)
        endpoint = f"{self.base_url}/v1beta/models/{model_name}:generateContent"

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system:
            payload["systemInstruction"] = {
                "parts": [{"text": system}]
            }

        try:
            resp = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code != 200:
                info = classify_provider_error(
                    self.id,
                    resp.status_code,
                    resp.text,
                    dict(resp.headers),
                    model_name=model_name,
                    endpoint_url=endpoint
                )
                self.last_error_info = info
                raise ProviderError(info.friendly_message, info=info, provider_id=self.id, status_code=resp.status_code)

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            cand0 = candidates[0]
            finish_reason = cand0.get("finishReason", "")
            if finish_reason in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"):
                raise ProviderError(f"Gemini generation blocked by safety filter: {finish_reason}", provider_id=self.id)
            content = cand0.get("content", {})
            parts = content.get("parts", [])
            return "".join(p.get("text", "") for p in parts)
        except requests.exceptions.Timeout as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=model_name, endpoint_url=endpoint)
            self.last_error_info = info
            raise ProviderError(info.friendly_message, info=info, provider_id=self.id)
        except requests.exceptions.ConnectionError as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=model_name, endpoint_url=endpoint)
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

        model_name = self._clean_model_name(model or self.default_model)
        endpoint = f"{self.base_url}/v1beta/models/{model_name}:streamGenerateContent?alt=sse"

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }
        if system:
            payload["systemInstruction"] = {
                "parts": [{"text": system}]
            }

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
                raise ProviderError(f"Gemini error ({resp.status_code}): {err_text}", provider_id=self.id, status_code=resp.status_code)

            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="replace") if isinstance(line, (bytes, bytearray)) else str(line)
                if line_str.startswith("data: "):
                    data_str = line_str[6:].strip()
                    try:
                        chunk = json.loads(data_str)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                token = p.get("text", "")
                                if token:
                                    full_text += token
                                    if stream_callback:
                                        stream_callback(token)
                    except Exception:
                        pass
            return full_text
        except requests.exceptions.Timeout:
            raise ProviderError("Gemini streaming timed out.", provider_id=self.id)
        except requests.exceptions.ConnectionError:
            raise ProviderError("Network error connecting to Gemini.", provider_id=self.id)

    def test_connection(self) -> Tuple[bool, str]:
        if not self.api_key:
            return False, "No API key configured for Google Gemini. Please enter your API key."

        t0 = time.perf_counter()
        try:
            model_name = self._clean_model_name(self.default_model)
            endpoint = f"{self.base_url}/v1beta/models/{model_name}:generateContent"
            payload = {
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 4, "temperature": 0.0}
            }
            resp = requests.post(endpoint, json=payload, headers=self._get_headers(), timeout=12.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            if resp.status_code == 200:
                self.last_error_info = None
                return True, f"Connected to Google Gemini ({elapsed_ms:.0f}ms). Model '{model_name}' is active."

            info = classify_provider_error(
                self.id,
                resp.status_code,
                resp.text,
                dict(resp.headers),
                model_name=model_name,
                endpoint_url=endpoint
            )
            self.last_error_info = info
            return False, info.friendly_message
        except requests.exceptions.Timeout as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=self.default_model, endpoint_url=f"{self.base_url}/v1beta/models")
            self.last_error_info = info
            return False, info.friendly_message
        except requests.exceptions.ConnectionError as ex:
            info = classify_provider_error(self.id, None, "", exception=ex, model_name=self.default_model, endpoint_url=f"{self.base_url}/v1beta/models")
            self.last_error_info = info
            return False, info.friendly_message
        except Exception as e:
            return False, f"Connection test failed: {e}"

    def list_models(self) -> List[str]:
        if not self.api_key:
            return self.metadata.recommended_models
        try:
            endpoint = f"{self.base_url}/v1beta/models"
            resp = requests.get(endpoint, headers=self._get_headers(), timeout=8.0)
            if resp.status_code == 200:
                data = resp.json()
                models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    if name.startswith("models/"):
                        name = name[7:]
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods and "gemini" in name:
                        models.append(name)
                if models:
                    rec = [m for m in self.metadata.recommended_models if m in models]
                    others = [m for m in models if m not in self.metadata.recommended_models]
                    return rec + others[:15]
        except Exception:
            pass
        return self.metadata.recommended_models
