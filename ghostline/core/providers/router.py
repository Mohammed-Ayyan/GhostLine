import logging
from typing import Optional, Callable, Dict, Any, List, Tuple

from ghostline.config import AppConfig, save_config
from ghostline.core.credentials import get_api_key, save_api_key, delete_api_key, has_api_key
from ghostline.core.llm_client import AnswerResult
from .base import BaseAIProvider, ProviderMetadata, ProviderError
from .ollama_provider import OllamaProvider
from .gemini_provider import GeminiProvider
from .openai_compatible_provider import (
    GroqProvider,
    OpenRouterProvider,
    OpenAIProvider,
    XAIProvider
)
from .anthropic_provider import AnthropicProvider

logger = logging.getLogger("ghostline.ai_router")


class AIRouter:
    """
    Central AI Router for Ghostline.
    Coordinates all screen MCQ solving, live audio conversation AI, and HUD custom questions.
    Decouples pipelines from specific LLM implementations, routing to the user's selected
    local or cloud provider (Ollama, Gemini, Groq, OpenRouter, OpenAI, Anthropic, xAI).
    """
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.providers: Dict[str, BaseAIProvider] = {}
        self.last_prompt: str = ""
        self._init_providers()

    def _init_providers(self) -> None:
        """Instantiates all supported provider adapters with current config and secure keys."""
        cfg = self.config
        models = getattr(cfg, "provider_models", {})
        urls = getattr(cfg, "provider_base_urls", {})

        # 1. Ollama (Local)
        self.providers["ollama"] = OllamaProvider(
            base_url=urls.get("ollama", getattr(cfg, "ollama_url", "http://127.0.0.1:11434")),
            default_model=models.get("ollama", getattr(cfg, "model_name", "phi3:mini"))
        )

        # 2. Google Gemini
        self.providers["gemini"] = GeminiProvider(
            api_key=get_api_key("gemini"),
            base_url=urls.get("gemini", "https://generativelanguage.googleapis.com"),
            default_model=models.get("gemini", "gemini-1.5-flash")
        )

        # 3. Groq
        self.providers["groq"] = GroqProvider(
            api_key=get_api_key("groq"),
            base_url=urls.get("groq", "https://api.groq.com/openai/v1"),
            default_model=models.get("groq", "llama-3.3-70b-versatile")
        )

        # 4. OpenRouter
        self.providers["openrouter"] = OpenRouterProvider(
            api_key=get_api_key("openrouter"),
            base_url=urls.get("openrouter", "https://openrouter.ai/api/v1"),
            default_model=models.get("openrouter", "meta-llama/llama-3.3-70b-instruct")
        )

        # 5. OpenAI
        self.providers["openai"] = OpenAIProvider(
            api_key=get_api_key("openai"),
            base_url=urls.get("openai", "https://api.openai.com/v1"),
            default_model=models.get("openai", "gpt-4o-mini")
        )

        # 6. Anthropic Claude
        self.providers["anthropic"] = AnthropicProvider(
            api_key=get_api_key("anthropic"),
            base_url=urls.get("anthropic", "https://api.anthropic.com"),
            default_model=models.get("anthropic", "claude-3-5-haiku-20241022")
        )

        # 7. xAI (Grok)
        self.providers["xai"] = XAIProvider(
            api_key=get_api_key("xai"),
            base_url=urls.get("xai", "https://api.x.ai/v1"),
            default_model=models.get("xai", "grok-2-1212")
        )

    @property
    def model_name(self) -> str:
        return self.get_active_provider().default_model

    @property
    def default_model(self) -> str:
        return self.get_active_provider().default_model

    @default_model.setter
    def default_model(self, val: str) -> None:
        self.get_active_provider().default_model = val

    @property
    def base_url(self) -> str:
        return self.get_active_provider().base_url

    @base_url.setter
    def base_url(self, val: str) -> None:
        self.get_active_provider().base_url = val

    def pull_model(self, model_name: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> Tuple[bool, str]:
        """Delegates pull_model to local Ollama provider."""
        ollama = self.providers.get("ollama")
        if ollama and hasattr(ollama._llm_helper, "pull_model"):
            return ollama._llm_helper.pull_model(model_name, progress_callback)
        return False, "Model download is only supported for local Ollama."

    def get_active_provider_id(self) -> str:
        prov = getattr(self.config, "ai_provider", "ollama").lower().strip()
        return prov if prov in self.providers else "ollama"

    def get_active_provider(self) -> BaseAIProvider:
        return self.providers[self.get_active_provider_id()]

    def get_provider(self, provider_id: str) -> Optional[BaseAIProvider]:
        return self.providers.get(provider_id.lower().strip())

    def get_all_metadata(self) -> List[ProviderMetadata]:
        return [p.metadata for p in self.providers.values()]

    def switch_provider(self, provider_id: str, model: Optional[str] = None) -> None:
        """Switches the active provider and updates configuration in real-time."""
        pid = provider_id.lower().strip()
        if pid not in self.providers:
            raise ValueError(f"Unknown AI provider: '{provider_id}'")

        self.config.ai_provider = pid
        if model:
            self.update_provider_model(pid, model)
        else:
            save_config(self.config)
        logger.info("Active AI provider switched to: %s (model: %s)", pid, self.providers[pid].default_model)

    def set_provider_key(self, provider_id: str, key: str) -> None:
        """Securely encrypts and saves an API key and updates the active runtime provider."""
        pid = provider_id.lower().strip()
        save_api_key(pid, key)
        if pid in self.providers:
            self.providers[pid].api_key = key.strip()

    def remove_provider_key(self, provider_id: str) -> None:
        """Removes the stored API key for a provider."""
        pid = provider_id.lower().strip()
        delete_api_key(pid)
        if pid in self.providers:
            self.providers[pid].api_key = ""

    def update_provider_model(self, provider_id: str, model: str) -> None:
        """Updates the default model for a specific provider."""
        pid = provider_id.lower().strip()
        clean_model = model.strip()
        if not hasattr(self.config, "provider_models"):
            self.config.provider_models = {}
        self.config.provider_models[pid] = clean_model

        if pid == "ollama":
            self.config.model_name = clean_model

        if pid in self.providers:
            self.providers[pid].default_model = clean_model

        save_config(self.config)

    def confirm_custom_host(self, host: str) -> None:
        """Explicitly records user confirmation for transmitting API keys to a non-default host."""
        if not hasattr(self.config, "confirmed_custom_hosts") or not isinstance(self.config.confirmed_custom_hosts, list):
            self.config.confirmed_custom_hosts = []
        clean = host.strip().lower()
        if clean and clean not in self.config.confirmed_custom_hosts:
            self.config.confirmed_custom_hosts.append(clean)
            save_config(self.config)

    def update_provider_base_url(self, provider_id: str, base_url: str) -> None:
        """Updates custom endpoint URL for a specific provider."""
        pid = provider_id.lower().strip()
        clean_url = base_url.strip()
        if not hasattr(self.config, "provider_base_urls"):
            self.config.provider_base_urls = {}
        self.config.provider_base_urls[pid] = clean_url

        if pid == "ollama":
            self.config.ollama_url = clean_url

        if pid in self.providers:
            self.providers[pid].base_url = clean_url.rstrip("/")

        save_config(self.config)

    def test_provider(self, provider_id: str) -> Tuple[bool, str]:
        """Tests live connectivity for a specific provider."""
        prov = self.get_provider(provider_id)
        if not prov:
            return False, f"Unknown provider: {provider_id}"
        return prov.test_connection()

    def list_models(self, provider_id: str) -> List[str]:
        """Lists available models for a specific provider."""
        prov = self.get_provider(provider_id)
        if not prov:
            return []
        return prov.list_models()

    def is_available(self) -> bool:
        """Checks if current active provider is available."""
        return self.get_active_provider().is_available()

    def check_health(self) -> Tuple[bool, List[str]]:
        """Health check compatibility helper."""
        prov = self.get_active_provider()
        ok, _ = prov.test_connection()
        return ok, prov.list_models()

    def select_model_for_type(self, question_type: str, preferred_model: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """Delegates model selection to active provider."""
        return self.get_active_provider().select_model_for_type(question_type, preferred_model)

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1024
    ) -> str:
        """Generates plain text response via the active provider."""
        active = self.get_active_provider()
        try:
            return active.generate(
                prompt=prompt,
                model=model,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens
            )
        except Exception as e:
            logger.warning("[%s] Generation failed: %s", active.name, e)
            # Check fallback to Ollama if active is a cloud provider
            if getattr(self.config, "fallback_to_ollama", True) and active.id != "ollama":
                logger.info("Falling back to local Ollama...")
                try:
                    return self.providers["ollama"].generate(
                        prompt=prompt,
                        system=system,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                except Exception as fb_err:
                    logger.error("Ollama fallback also failed: %s", fb_err)
            raise

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
        Solves question using the active provider, with automatic validation
        and graceful fallback handling.
        """
        active = self.get_active_provider()
        result = active.solve_question(
            question_text=question_text,
            options=options,
            model=model,
            stream_callback=stream_callback,
            is_unlabelled_mcq=is_unlabelled_mcq,
            supporting_passage=supporting_passage,
            constraints=constraints,
            examples=examples,
            input_format=input_format,
            output_format=output_format,
            starter_code=starter_code,
            requested_language=requested_language,
            question_type=question_type
        )
        self.last_prompt = getattr(active, "last_prompt", "")

        # If cloud provider returned an error and fallback is enabled, try local Ollama
        if result.validation_status == "error" and getattr(self.config, "fallback_to_ollama", True) and active.id != "ollama":
            logger.warning("[%s] Failed with error: %s. Attempting fallback to local Ollama...", active.name, result.error)
            ollama = self.providers.get("ollama")
            if ollama and ollama.is_available():
                fallback_result = ollama.solve_question(
                    question_text=question_text,
                    options=options,
                    stream_callback=stream_callback,
                    is_unlabelled_mcq=is_unlabelled_mcq,
                    supporting_passage=supporting_passage,
                    constraints=constraints,
                    examples=examples,
                    input_format=input_format,
                    output_format=output_format,
                    starter_code=starter_code,
                    requested_language=requested_language,
                    question_type=question_type
                )
                self.last_prompt = getattr(ollama, "last_prompt", "")
                if fallback_result.is_validated or fallback_result.validation_status != "error":
                    fallback_result.explanation = f"[Fallback: Ollama] {fallback_result.explanation}"
                    return fallback_result

        return result
