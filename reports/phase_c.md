# Phase C — BYOK Audit and Fixes Report

**Date & Time**: 2026-11-01 18:48:45  
**Audit Scope**: All 7 AI Providers (Google Gemini, Groq, OpenRouter, OpenAI, Anthropic Claude, xAI Grok, Ollama)  

---

## 1. Provider Audit Matrix

| Provider | Endpoint & Protocol | Auth Headers | Doc Reference & Date | Verification Status | Audit Findings & Remediations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | `generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | `x-goog-api-key: <key>` | [ai.google.dev Quickstart](https://ai.google.dev/gemini-api/docs/quickstart) (Nov 2026) | VERIFIED-AUTOMATED | **FIXED**: Code originally passed `?key=` query param in the URL. Fixed to use the standard `x-goog-api-key` header to eliminate key exposure in logs and tracebacks. Added `finishReason` safety filter check. |
| **Groq** | `api.groq.com/openai/v1/chat/completions` | `Authorization: Bearer <key>` | [Groq API Reference](https://console.groq.com/docs/api-reference) (Nov 2026) | VERIFIED-AUTOMATED | Standard OpenAI format. Added `Retry-After` header extraction and bounded reporting for 429 rate limits. |
| **OpenRouter** | `openrouter.ai/api/v1/chat/completions` | `Authorization: Bearer <key>` | [OpenRouter Docs](https://openrouter.ai/docs) (Nov 2026) | VERIFIED-AUTOMATED | Includes attribution headers `HTTP-Referer: https://ghostline.ai` and `X-Title: Ghostline Desktop`. Prefix models supported. |
| **OpenAI** | `api.openai.com/v1/chat/completions` | `Authorization: Bearer <key>` | [OpenAI Chat API](https://platform.openai.com/docs/api-reference/chat) (Nov 2026) | VERIFIED-AUTOMATED | **FIXED**: Added reasoning model detection (`o1`, `o3`). Routes with `max_completion_tokens` instead of `max_tokens` and omits `temperature` to prevent 400 Bad Request rejections on reasoning models. |
| **Anthropic Claude** | `api.anthropic.com/v1/messages` | `x-api-key: <key>`, `anthropic-version: 2023-06-01` | [Anthropic Messages API](https://docs.anthropic.com/en/api/messages) (Nov 2026) | VERIFIED-AUTOMATED | Strict schema enforced: `max_tokens` required, `system` prompt top-level, content block array parsed. Added `Retry-After` header parsing. |
| **xAI Grok** | `api.x.ai/v1/chat/completions` | `Authorization: Bearer <key>` | [xAI Docs](https://docs.x.ai/api) (Nov 2026) | VERIFIED-AUTOMATED | Standard OpenAI-compatible Chat Completions format with Bearer auth. |
| **Ollama (Local)** | `http://127.0.0.1:11434/api/generate` | None (Local daemon) | [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) (Nov 2026) | VERIFIED-LIVE | Confirmed running locally on machine. Model tags response verified in 91ms (`phi3:mini`, `qwen2.5:0.5b`). |

---

## 2. Redaction & Key Security Verification
- **Test**: `test_key_never_saved_in_plaintext_config` in `tests/test_byok_providers.py`.
- **Result**: VERIFIED-AUTOMATED. Verified that saving API keys via DPAPI stores binary ciphertext in `%APPDATA%\Ghostline\credentials.bin` and never writes raw plaintext keys to `config.json` or logs.
- **Redaction in UI**: Verified that `mask_api_key()` renders `sk-••••••••abcd` or `••••••••`.
- **URL Sanitization**: Verified that Gemini REST URLs no longer contain `?key=...`.

---

## 3. Fallback & Switching Verification
- **Dynamic Switching**: `AIRouter.switch_provider()` updates the active provider instantly in memory without app restart.
- **Safe Fallback**: Confirmed that when cloud quota is exhausted (429), `AIRouter` falls back to local Ollama ONLY if `config.fallback_to_ollama` is enabled, and prepends `[Fallback: Ollama]` to the answer explanation so the user is always informed. Never falls back to a paid cloud provider.

---

## 4. Live Verification Script
- **Tool**: `scripts/live_provider_check.py`
- **Output**: Tested against local environment. Providers without explicit environment variables report `NOT-TESTED` without failing, while local Ollama reports `VERIFIED-LIVE`.

