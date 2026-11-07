#!/usr/bin/env python3
"""
Ghostline — Live BYOK Provider Verification Script
Safely tests configured cloud AI providers using environment variables.
Never prints or logs API keys.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ghostline.config import AppConfig
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
    print("=" * 70)
    print("Ghostline AI Provider Verification Suite (Live & Local)")
    print("=" * 70)
    print("Checking environment variables and local services (keys are never echoed)...\n")

    results = []

    # 1. Ollama (Local)
    ollama = OllamaProvider()
    t0 = time.perf_counter()
    ok, msg = ollama.test_connection()
    lat = (time.perf_counter() - t0) * 1000.0
    if ok:
        results.append(("Ollama (Local)", "VERIFIED-LIVE", ollama.default_model, f"{lat:.0f}ms", msg))
    else:
        results.append(("Ollama (Local)", "BLOCKED", ollama.default_model, "-", "Ollama daemon not responding at 127.0.0.1:11434"))

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
            results.append((name, "NOT-TESTED", default_model, "-", f"Set {env_vars[0]}=... to enable live check"))
            continue

        try:
            prov = prov_cls(api_key=key, default_model=default_model)
            t0 = time.perf_counter()
            success, msg = prov.test_connection()
            lat = (time.perf_counter() - t0) * 1000.0
            if success:
                results.append((name, "VERIFIED-LIVE", default_model, f"{lat:.0f}ms", f"Verified via ${used_var}"))
            else:
                results.append((name, "FAILED", default_model, f"{lat:.0f}ms", msg))
        except Exception as e:
            results.append((name, "FAILED", default_model, "-", str(e)))

    # Output Markdown Table
    print(f"{'Provider':<18} | {'Status':<16} | {'Model':<30} | {'Latency':<9} | {'Details'}")
    print(f"{'-'*18}-|-{'-'*16}-|-{'-'*30}-|-{'-'*9}-|-{'-'*25}")
    for prov_name, status, model, lat_str, details in results:
        print(f"{prov_name:<18} | {status:<16} | {model:<30} | {lat_str:<9} | {details}")

    print("\nVerification completed.")


if __name__ == "__main__":
    main()

