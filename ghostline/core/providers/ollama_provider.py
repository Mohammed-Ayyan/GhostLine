import time
import json
import logging
from typing import Optional, Callable, Dict, Any, List, Tuple
import requests

from .base import BaseAIProvider, ProviderMetadata
from ghostline.core.http_client import GHOSTLINE_USER_AGENT, ProviderError, ProviderErrorInfo
from ghostline.core.llm_client import sanitize_control_characters

logger = logging.getLogger("ghostline.providers.ollama")


class OllamaProvider(BaseAIProvider):
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        default_model: str = "phi3:mini",
        timeout: float = 60.0
    ):
        metadata = ProviderMetadata(
            id="ollama",
            name="Ollama (Local)",
            description="Run models 100% locally on your machine. Zero network requests, absolute privacy.",
            is_local=True,
            requires_api_key=False,
            default_model=default_model,
            recommended_models=[
                "phi3:mini",
                "llama3.2:3b",
                "mistral:7b",
                "qwen2.5-coder:7b",
                "deepseek-coder:6.7b",
                "gemma2:2b"
            ],
            default_base_url="http://127.0.0.1:11434",
            pricing_note="Free (Runs locally on your CPU/GPU)",
            privacy_note="100% Local: No prompts, screenshots, or transcripts ever leave your device.",
            docs_url="https://ollama.com"
        )
        super().__init__(
            metadata=metadata,
            api_key="",
            base_url=base_url,
            default_model=default_model,
            timeout=timeout
        )

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        selected_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": max_tokens
            }
        }
        if system:
            payload["system"] = system

        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except requests.exceptions.ConnectionError:
            raise ProviderError(
                f"Cannot connect to Ollama daemon at {self.base_url}. Make sure Ollama is installed and running.",
                provider_id="ollama"
            )
        except requests.exceptions.Timeout:
            raise ProviderError(
                f"Ollama inference timed out after {self.timeout}s. Model '{selected_model}' may be too large for this CPU/GPU.",
                provider_id="ollama"
            )
        except Exception as e:
            raise ProviderError(f"Ollama generation failed: {e}", provider_id="ollama")

    def generate_stream(
        self,
        prompt: str,
        stream_callback: Callable[[str], None],
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        selected_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": selected_model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": max_tokens
            }
        }
        if system:
            payload["system"] = system

        full_text = ""
        try:
            resp = requests.post(f"{self.base_url}/api/generate", json=payload, stream=True, timeout=self.timeout)
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8", errors="replace") if isinstance(line, (bytes, bytearray)) else str(line)
                line_str = line_str.strip()
                if not line_str:
                    continue
                try:
                    chunk = json.loads(line_str, strict=False)
                except Exception:
                    sanitized_line = sanitize_control_characters(line_str)
                    try:
                        chunk = json.loads(sanitized_line, strict=False)
                    except Exception:
                        chunk = {}
                token = chunk.get("response", "")
                full_text += token
                if stream_callback:
                    stream_callback(token)
            return full_text
        except requests.exceptions.ConnectionError:
            raise ProviderError(
                f"Cannot connect to Ollama daemon at {self.base_url}.",
                provider_id="ollama"
            )
        except Exception as e:
            raise ProviderError(f"Ollama streaming failed: {e}", provider_id="ollama")

    def test_connection(self) -> Tuple[bool, str]:
        t0 = time.perf_counter()
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                model_count = len(models)
                return True, f"Connected to Ollama ({elapsed_ms:.0f}ms). Found {model_count} local model(s)."
            return False, f"Ollama HTTP {resp.status_code}: {resp.text[:100]}"
        except requests.exceptions.ConnectionError:
            return False, f"Could not connect to Ollama at {self.base_url}. Is Ollama running?"
        except requests.exceptions.Timeout:
            return False, f"Connection to Ollama timed out (endpoint {self.base_url})."
        except Exception as e:
            return False, f"Connection test failed: {e}"

    def list_models(self) -> List[str]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            pass
        return self.metadata.recommended_models

    def select_model_for_type(self, question_type: str, preferred_model: Optional[str] = None) -> Tuple[str, Optional[str]]:
        return self._llm_helper.select_model_for_type(question_type, preferred_model)

