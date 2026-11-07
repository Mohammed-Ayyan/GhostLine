import os
import sys
import json
import unittest
from unittest.mock import patch, MagicMock

from ghostline.config import AppConfig
from ghostline.core.credentials import (
    save_api_key,
    get_api_key,
    has_api_key,
    delete_api_key,
    mask_api_key,
    ENV_KEY_MAP
)
from ghostline.core.providers.base import BaseAIProvider, ProviderMetadata, ProviderError
from ghostline.core.providers.ollama_provider import OllamaProvider
from ghostline.core.providers.openai_compatible_provider import (
    OpenAICompatibleProvider,
    GroqProvider,
    OpenRouterProvider,
    OpenAIProvider,
    XAIProvider
)
from ghostline.core.providers.gemini_provider import GeminiProvider
from ghostline.core.providers.anthropic_provider import AnthropicProvider
from ghostline.core.providers.router import AIRouter
from ghostline.core.llm_client import AnswerResult
from ghostline.core.pipeline import GhostlinePipeline
from ghostline.audio.assistant import LiveAudioAssistant


class TestCredentialsStorage(unittest.TestCase):
    """Test DPAPI encrypted local storage for Bring Your Own API Key."""

    def test_save_get_delete_roundtrip(self):
        test_prov = "test_custom_provider"
        test_key = "sk-test-1234567890abcdef"

        save_api_key(test_prov, test_key)
        self.assertTrue(has_api_key(test_prov))
        self.assertEqual(get_api_key(test_prov), test_key)

        delete_api_key(test_prov)
        self.assertFalse(has_api_key(test_prov))
        self.assertIsNone(get_api_key(test_prov))

    def test_masked_api_key_security(self):
        # Empty
        self.assertEqual(mask_api_key(""), "")
        self.assertEqual(mask_api_key(None), "")

        # Short key
        self.assertEqual(mask_api_key("12345"), "••••••••")

        # Standard key
        masked = mask_api_key("sk-proj-1234567890abcdef")
        self.assertTrue(masked.startswith("sk-"))
        self.assertTrue(masked.endswith("cdef"))
        self.assertIn("••••••••", masked)
        self.assertNotIn("1234567890", masked)

    def test_key_never_saved_in_plaintext_config(self):
        from ghostline.config import get_config_path, load_config, save_config
        fake_secret = "AIzaSyFakeSecretKeyNeverPlaintext999"
        save_api_key("gemini", fake_secret)

        cfg = load_config()
        save_config(cfg)
        cfg_path = get_config_path()
        if cfg_path.exists():
            with open(cfg_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn(fake_secret, content)

    def test_env_var_fallback(self):
        # Temporarily set environment variable
        os.environ["GROQ_API_KEY"] = "gsk_test_env_key_9999"
        try:
            # When no key is saved in storage, it should pick up the env var
            key = get_api_key("groq")
            self.assertEqual(key, "gsk_test_env_key_9999")
            self.assertTrue(has_api_key("groq"))
        finally:
            os.environ.pop("GROQ_API_KEY", None)


class TestProviderAdapters(unittest.TestCase):
    """Test each AI Provider adapter with mock HTTP responses."""

    @patch("requests.post")
    def test_ollama_provider_generate(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "Local Ollama generation result"}
        mock_post.return_value = mock_resp

        provider = OllamaProvider()
        ans = provider.generate("What is 2+2?")
        self.assertEqual(ans, "Local Ollama generation result")

    @patch("requests.post")
    def test_gemini_provider_generate_and_solve(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "B\n\nExplanation: Binary heap allows efficient priority queue operations."}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        provider = GeminiProvider(api_key="AIzaSyFakeKeyForTesting1234")
        res = provider.solve_question(
            question_text="Which data structure implements a priority queue?",
            options={"A": "Stack", "B": "Binary Heap", "C": "Queue"}
        )

        self.assertIsInstance(res, AnswerResult)
        self.assertEqual(res.source_option_label, "B")
        self.assertTrue(res.is_validated)
        self.assertIn("binary heap", res.option_text.lower())

        # Verify API key is passed in x-goog-api-key header and NOT in URL query string
        url_called = mock_post.call_args[0][0]
        headers_called = mock_post.call_args[1].get("headers", {})
        self.assertNotIn("?key=", url_called)
        self.assertEqual(headers_called.get("x-goog-api-key"), "AIzaSyFakeKeyForTesting1234")

    @patch("requests.post")
    def test_groq_provider_chat_completions(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "A\n\nExplanation: Python uses indentation to delimit blocks."
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        provider = GroqProvider(api_key="gsk_fake_key_1234")
        res = provider.solve_question(
            question_text="How are blocks delimited in Python?",
            options={"A": "Indentation", "B": "Curly brackets", "C": "Begin/End"}
        )

        self.assertIsInstance(res, AnswerResult)
        self.assertEqual(res.source_option_label, "A")
        self.assertTrue(res.is_validated)

    @patch("requests.post")
    def test_openrouter_provider_with_headers(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "OpenRouter test answer"}}]
        }
        mock_post.return_value = mock_resp

        provider = OpenRouterProvider(api_key="sk-or-fake-key")
        ans = provider.generate("Hello OpenRouter")
        self.assertEqual(ans, "OpenRouter test answer")

        headers = mock_post.call_args[1].get("headers", {})
        self.assertEqual(headers.get("HTTP-Referer"), "https://ghostline.ai")
        self.assertEqual(headers.get("X-Title"), "Ghostline Desktop")

    @patch("requests.post")
    def test_openai_provider_quota_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.json.return_value = {
            "error": {"message": "You exceeded your current quota, please check your plan and billing details."}
        }
        mock_post.return_value = mock_resp

        provider = OpenAIProvider(api_key="sk-fake-openai-key")
        with self.assertRaises(ProviderError) as ctx:
            provider.generate("Test prompt")
        self.assertTrue(ctx.exception.is_quota_error)
        self.assertIn("quota", str(ctx.exception).lower())

    @patch("requests.post")
    def test_anthropic_provider_solve(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": [
                {
                    "type": "text",
                    "text": "C\n\nExplanation: Quicksort has an average time complexity of O(n log n)."
                }
            ]
        }
        mock_post.return_value = mock_resp

        provider = AnthropicProvider(api_key="sk-ant-fake-key")
        res = provider.solve_question(
            question_text="What is the average time complexity of quicksort?",
            options={"A": "O(n^2)", "B": "O(n)", "C": "O(n log n)"}
        )

        self.assertIsInstance(res, AnswerResult)
        self.assertEqual(res.source_option_label, "C")
        self.assertTrue(res.is_validated)

    @patch("requests.post")
    def test_xai_provider_connection_test(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        provider = XAIProvider(api_key="xai-fake-key")
        ok, msg = provider.test_connection()
        self.assertTrue(ok)
        self.assertIn("xAI", msg)


class TestAIRouter(unittest.TestCase):
    """Test central AIRouter provider management, switching, and fallback."""

    def test_router_initialization_and_metadata(self):
        cfg = AppConfig(ai_provider="ollama")
        router = AIRouter(config=cfg)

        metadata_list = router.get_all_metadata()
        provider_ids = [m.id for m in metadata_list]
        self.assertIn("ollama", provider_ids)
        self.assertIn("gemini", provider_ids)
        self.assertIn("groq", provider_ids)
        self.assertIn("openrouter", provider_ids)
        self.assertIn("openai", provider_ids)
        self.assertIn("anthropic", provider_ids)
        self.assertIn("xai", provider_ids)

        self.assertEqual(router.get_active_provider_id(), "ollama")

    def test_router_switching(self):
        cfg = AppConfig(ai_provider="ollama")
        router = AIRouter(config=cfg)

        router.switch_provider("groq", model="llama-3.3-70b-versatile")
        self.assertEqual(router.get_active_provider_id(), "groq")
        self.assertEqual(router.model_name, "llama-3.3-70b-versatile")

    @patch.object(OllamaProvider, "solve_question")
    @patch.object(GroqProvider, "solve_question")
    def test_router_fallback_to_ollama(self, mock_groq_solve, mock_ollama_solve):
        # Configure Groq to fail with a quota error
        mock_groq_solve.return_value = AnswerResult(
            source_option_label="Uncertain",
            is_validated=False,
            validation_status="error",
            error="Quota exceeded (429)"
        )

        # Configure Ollama fallback to succeed
        mock_ollama_solve.return_value = AnswerResult(
            source_option_label="A",
            option_text="Stack",
            explanation="Ollama fallback solution",
            is_validated=True,
            validation_status="validated"
        )

        cfg = AppConfig(ai_provider="groq", fallback_to_ollama=True)
        router = AIRouter(config=cfg)

        # Mock ollama availability
        router.providers["ollama"].is_available = MagicMock(return_value=True)

        res = router.solve_question(
            question_text="Which data structure follows LIFO?",
            options={"A": "Stack", "B": "Queue"}
        )

        # Verify fallback occurred
        self.assertTrue(res.is_validated)
        self.assertEqual(res.source_option_label, "A")
        self.assertIn("[Fallback: Ollama]", res.explanation)


class TestPipelineBYOKIntegration(unittest.TestCase):
    """Test GhostlinePipeline and LiveAudioAssistant integration with AIRouter."""

    @patch.object(AIRouter, "solve_question")
    def test_ghostline_pipeline_uses_ai_router(self, mock_router_solve):
        mock_router_solve.return_value = AnswerResult(
            source_option_label="D",
            option_text="Linked List",
            explanation="Linear collection of data elements whose order is not given by physical memory placement.",
            is_validated=True,
            validation_status="validated"
        )

        router = AIRouter(config=AppConfig(ai_provider="groq"))
        pipeline = GhostlinePipeline(
            ollama_client=router,
            model_name="llama-3.3-70b-versatile"
        )

        self.assertEqual(pipeline.llm, router)

    @patch.object(AIRouter, "generate")
    def test_live_audio_assistant_uses_ai_router(self, mock_router_generate):
        mock_router_generate.return_value = "The time complexity is O(log n)."

        router = AIRouter(config=AppConfig(ai_provider="gemini"))
        assistant = LiveAudioAssistant(
            ollama_client=router,
            model_name="gemini-1.5-flash"
        )

        self.assertEqual(assistant.llm, router)


class TestMainWindowBYOKUI(unittest.TestCase):
    """Test PyQt6 Settings UI elements for AI Provider configuration."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def test_main_window_byok_ui_components(self):
        from ghostline.ui.qt_main_window import QtGhostlineMainWindow
        cfg = AppConfig(ai_provider="ollama")
        win = QtGhostlineMainWindow(config=cfg)

        self.assertTrue(hasattr(win, "combo_provider"))
        self.assertTrue(hasattr(win, "card_api_key"))
        self.assertTrue(hasattr(win, "combo_model"))
        self.assertTrue(hasattr(win, "txt_endpoint"))
        self.assertTrue(hasattr(win, "btn_test_conn"))
        self.assertTrue(hasattr(win, "switch_fallback"))

        # In Ollama mode, API key card should be hidden
        self.assertTrue(win.card_api_key.isHidden())

        # Switch to Groq
        idx = win.combo_provider.findData("groq")
        self.assertGreaterEqual(idx, 0)
        win.combo_provider.setCurrentIndex(idx)

        # In cloud provider mode, API key card should be visible (not hidden)
        self.assertFalse(win.card_api_key.isHidden())
        self.assertIn("llama", win.combo_model.currentText().lower())

        # Switch to Gemini
        idx_gemini = win.combo_provider.findData("gemini")
        win.combo_provider.setCurrentIndex(idx_gemini)
        self.assertFalse(win.card_api_key.isHidden())
        self.assertIn("gemini", win.combo_model.currentText().lower())

        # Save settings test
        saved_configs = []
        win.on_settings_saved = lambda c: saved_configs.append(c)
        win._save_settings()

        self.assertEqual(len(saved_configs), 1)
        self.assertEqual(saved_configs[0].ai_provider, "gemini")


if __name__ == "__main__":
    unittest.main()
