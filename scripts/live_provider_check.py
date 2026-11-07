#!/usr/bin/env python3
"""
Ghostline — Live BYOK Provider Verification Script (Run 8)
Safely tests configured local and cloud AI providers using the shared HTTP layer.
Reads API keys strictly from environment variables.
Never echoes, prints, or logs API keys.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ghostline.build_info import VERSION
from ghostline.core.http_client import GHOSTLINE_USER_AGENT, redact_secrets
from ghostline.core.providers.ollama_provider import OllamaProvider
from ghostline.core.providers.gemini_provider import GeminiProvider
from ghostline.core.providers.openai_compatible_provider import (
    GroqProvider,
    OpenRouterProvider,
    OpenAIProvider,
    XAIProvider
)
from ghostline.core.providers.anthropic_provider import AnthropicProvider


def main():
    print("=" * 80)
    print(f"Ghostline v{VERSION} AI Provider Verification Suite")
    print(f"User-Agent: {GHOSTLINE_USER_AGENT}")
    print("=" * 80)
    print("Checking local services and environment variables (keys are strictly redacted)...\n")

    results = []

    # 1. Ollama (Local)
    ollama = OllamaProvider()
    t0 = time.perf_counter()
    ok, msg = ollama.test_connection()
    lat = (time.perf_counter() - t0) * 1000.0
    if ok:
        results.append(("Ollama (Local)", "VERIFIED-LIVE", ollama.default_model, f"{lat:.0f}ms", msg))
    else:
        results.append(("Ollama (Local)", "MOCK-ONLY/BLOCKED", ollama.default_model, "-", redact_secrets(msg)))

    # Provider env mapping
    providers = [
        ("Google Gemini", "gemini", ["GEMINI_API_KEY", "GOOGLE_API_KEY"], GeminiProvider, "gemini-1.5-flash"),
        ("Groq", "groq", ["GROQ_API_KEY"], GroqProvider, "llama-3.3-70b-versatile"),
        ("OpenRouter", "openrouter", ["OPENROUTER_API_KEY"], OpenRouterProvider, "meta-llama/llama-3.3-70b-instruct"),
        ("OpenAI", "openai", ["OPENAI_API_KEY"], OpenAIProvider, "gpt-4o-mini"),
        ("Anthropic Claude", "anthropic", ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"], AnthropicProvider, "claude-3-5-haiku-20241022"),
        ("xAI Grok", "xai", ["XAI_API_KEY", "GROK_API_KEY"], XAIProvider, "grok-2-1212"),
    ]

    for name, pid, env_vars, prov_cls, default_model in providers:
        key = None
        used_var = None
        for ev in env_vars:
            val = os.environ.get(ev, "").strip()
            if val:
                key = val
                used_var = ev
                break

        if not key:
            results.append((name, "MOCK-ONLY/BLOCKED", default_model, "-", f"No key in ${env_vars[0]}. Run: $env:{env_vars[0]}='...'"))
            continue

        try:
            prov = prov_cls(api_key=key, default_model=default_model)
            t0 = time.perf_counter()
            success, msg = prov.test_connection()
            lat = (time.perf_counter() - t0) * 1000.0
            clean_msg = redact_secrets(msg)
            if success:
                results.append((name, "VERIFIED-LIVE", default_model, f"{lat:.0f}ms", f"Verified via ${used_var}"))
            else:
                results.append((name, "FAILED", default_model, f"{lat:.0f}ms", clean_msg))
        except Exception as e:
            results.append((name, "FAILED", default_model, "-", redact_secrets(str(e))))

    # Output Markdown Table
    print(f"{'Provider':<18} | {'Status':<18} | {'Model':<30} | {'Latency':<9} | {'Details'}")
    print(f"{'-'*18}-|-{'-'*18}-|-{'-'*30}-|-{'-'*9}-|-{'-'*35}")
    for prov_name, status, model, lat_str, details in results:
        print(f"{prov_name:<18} | {status:<18} | {model:<30} | {lat_str:<9} | {details}")

    print("\nVerification completed. Keys were never displayed or stored in logs.")


if __name__ == "__main__":
    main()
