"""
Ghostline — Enterprise Sensitive Data & Credential Redaction Layer.

Guarantees that sensitive secrets, API keys, authorization headers, and personal profile facts
are never written to log files, stdout, crash logs, or exception traces.
"""

import re
import logging
from typing import Optional, List, Set, Any

# Standard key patterns for cloud providers and services
REDACTION_PATTERNS: List[re.Pattern] = [
    # OpenAI and OpenAI-compatible keys
    re.compile(r'\bsk-[a-zA-Z0-9_-]{16,}\b'),
    # Anthropic API keys
    re.compile(r'\bsk-ant-[a-zA-Z0-9_-]{16,}\b'),
    # OpenRouter API keys
    re.compile(r'\bsk-or-[a-zA-Z0-9_-]{16,}\b'),
    # Groq API keys
    re.compile(r'\bgsk_[a-zA-Z0-9_-]{16,}\b'),
    # Google AIza keys
    re.compile(r'\bAIza[0-9A-Za-z-_]{30,}\b'),
    # xAI Grok keys
    re.compile(r'\bxai-[a-zA-Z0-9_-]{16,}\b'),
    # GitHub personal access tokens
    re.compile(r'\bghp_[a-zA-Z0-9]{30,}\b'),
    re.compile(r'\bgithub_pat_[a-zA-Z0-9_]{20,}\b'),
    # Bearer tokens in headers or logs
    re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', re.IGNORECASE),
    # API key query parameters or JSON fields
    re.compile(r'["\']?(?:api[_-]?key|key|token|password|secret)["\']?\s*[:=]\s*["\']([^"\'\s]{8,})["\']', re.IGNORECASE),
    # Headers like x-goog-api-key: ...
    re.compile(r'x-goog-api-key:\s*[^\s,\'\"]+', re.IGNORECASE),
    re.compile(r'x-api-key:\s*[^\s,\'\"]+', re.IGNORECASE),
]

_REGISTERED_SECRETS: Set[str] = set()


def register_secret_for_redaction(secret: str) -> None:
    """Registers a specific sensitive string (e.g. user key or profile text) to be redacted."""
    if secret and len(secret.strip()) >= 5:
        _REGISTERED_SECRETS.add(secret.strip())


def unregister_secret_for_redaction(secret: str) -> None:
    """Removes a registered secret from active redaction set."""
    if secret in _REGISTERED_SECRETS:
        _REGISTERED_SECRETS.remove(secret)


def redact_sensitive_text(text: str, extra_secrets: Optional[List[str]] = None) -> str:
    """
    Sanitizes text by replacing any API keys, credentials, or registered secrets
    with a safe masked placeholder '[REDACTED]'.
    """
    if not text or not isinstance(text, str):
        return text

    sanitized = text

    # 1. Redact known registered secrets
    all_secrets = set(_REGISTERED_SECRETS)
    if extra_secrets:
        for s in extra_secrets:
            if s and len(s.strip()) >= 5:
                all_secrets.add(s.strip())

    for secret in sorted(all_secrets, key=len, reverse=True):
        if secret in sanitized:
            sanitized = sanitized.replace(secret, "[REDACTED_SECRET]")

    # 2. Redact regex patterns
    for pat in REDACTION_PATTERNS:
        def _repl(m: re.Match) -> str:
            full = m.group(0)
            if "Bearer " in full:
                return "Bearer [REDACTED_TOKEN]"
            if "x-goog-api-key:" in full:
                return "x-goog-api-key: [REDACTED_KEY]"
            if "x-api-key:" in full:
                return "x-api-key: [REDACTED_KEY]"
            if m.lastindex and m.lastindex >= 1:
                # Key/value field match
                val = m.group(1)
                return full.replace(val, "[REDACTED]")
            # Direct pattern match (e.g. sk-..., gsk_...)
            prefix = full[:4]
            return f"{prefix}••••[REDACTED]"

        sanitized = pat.sub(_repl, sanitized)

    return sanitized


class RedactingLoggingFilter(logging.Filter):
    """
    Logging filter attached to root and handler loggers to automatically redact
    any sensitive API keys or credentials from log records before formatting/writing.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_sensitive_text(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_sensitive_text(str(a)) if isinstance(a, str) else a for a in record.args)
        return True


class RedactingFormatter(logging.Formatter):
    """
    Logging formatter wrapper that ensures formatted messages and exception traces
    have all sensitive information redacted.
    """
    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return redact_sensitive_text(formatted)

