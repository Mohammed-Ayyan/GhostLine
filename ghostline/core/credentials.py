import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger("ghostline.credentials")

# Environment variable map for cloud AI providers
ENV_KEY_MAP = {
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    "groq": ["GROQ_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"],
    "xai": ["XAI_API_KEY", "GROK_API_KEY"],
}


def _get_credentials_path() -> Path:
    """Returns path to the encrypted credentials file in %APPDATA%/Ghostline."""
    from ghostline.config import get_app_dir
    return get_app_dir() / "credentials.bin"


def _encrypt_bytes_dpapi(data: bytes) -> bytes:
    """Encrypts bytes using Windows DPAPI (CryptProtectData)."""
    if sys.platform != "win32":
        # Fallback for non-Windows test environments
        import base64
        return b"NON_WIN:" + base64.b64encode(data)

    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

    blob_in = DATA_BLOB(
        len(data),
        ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte))
    )
    blob_out = DATA_BLOB()

    # CryptProtectData with UI forbidden flag (CRYPTPROTECT_UI_FORBIDDEN = 0x1)
    res = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in),
        "GhostlineCredentials",
        None,
        None,
        None,
        0x1,
        ctypes.byref(blob_out)
    )
    if not res:
        err = ctypes.GetLastError()
        raise OSError(f"CryptProtectData failed with error code {err}")

    try:
        encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return encrypted
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _decrypt_bytes_dpapi(encrypted_data: bytes) -> bytes:
    """Decrypts bytes using Windows DPAPI (CryptUnprotectData)."""
    if sys.platform != "win32" or encrypted_data.startswith(b"NON_WIN:"):
        import base64
        raw = encrypted_data[len(b"NON_WIN:"):] if encrypted_data.startswith(b"NON_WIN:") else encrypted_data
        return base64.b64decode(raw)

    import ctypes
    import ctypes.wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", ctypes.wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

    blob_in = DATA_BLOB(
        len(encrypted_data),
        ctypes.cast(ctypes.create_string_buffer(encrypted_data), ctypes.POINTER(ctypes.c_byte))
    )
    blob_out = DATA_BLOB()

    res = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(blob_out)
    )
    if not res:
        err = ctypes.GetLastError()
        raise OSError(f"CryptUnprotectData failed with error code {err}")

    try:
        decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return decrypted
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def _load_credentials_dict() -> Dict[str, str]:
    """Loads and decrypts all stored credentials from the persistent storage."""
    cred_path = _get_credentials_path()
    if not cred_path.exists():
        return {}
    try:
        with open(cred_path, "rb") as f:
            encrypted_payload = f.read()
        if not encrypted_payload:
            return {}
        decrypted_bytes = _decrypt_bytes_dpapi(encrypted_payload)
        return json.loads(decrypted_bytes.decode("utf-8"))
    except Exception as e:
        logger.warning("Could not decrypt credentials file: %s", type(e).__name__)
        return {}


def _save_credentials_dict(creds: Dict[str, str]) -> None:
    """Encrypts and writes the credentials dictionary to persistent storage."""
    cred_path = _get_credentials_path()
    cred_path.parent.mkdir(parents=True, exist_ok=True)
    raw_bytes = json.dumps(creds).encode("utf-8")
    encrypted_bytes = _encrypt_bytes_dpapi(raw_bytes)
    with open(cred_path, "wb") as f:
        f.write(encrypted_bytes)


def save_api_key(provider_id: str, api_key: str) -> None:
    """
    Securely saves an API key for the given provider.
    The key is encrypted using Windows DPAPI and never stored in plaintext.
    """
    provider = provider_id.lower().strip()
    key = api_key.strip()
    creds = _load_credentials_dict()
    if key:
        creds[provider] = key
    else:
        creds.pop(provider, None)
    _save_credentials_dict(creds)
    logger.info("Securely saved API key for provider: %s", provider)


def get_api_key(provider_id: str) -> Optional[str]:
    """
    Retrieves the decrypted API key for the given provider.
    Checks:
    1. Secure encrypted DPAPI store.
    2. Environment variables (e.g. GEMINI_API_KEY, GROQ_API_KEY, etc.) as fallback.
    Returns None if no key is configured.
    """
    provider = provider_id.lower().strip()
    creds = _load_credentials_dict()
    if provider in creds and creds[provider].strip():
        return creds[provider].strip()

    # Environment variable fallback
    env_vars = ENV_KEY_MAP.get(provider, [])
    for env_var in env_vars:
        val = os.environ.get(env_var, "").strip()
        if val:
            return val

    return None


def delete_api_key(provider_id: str) -> None:
    """Removes the stored API key for the given provider."""
    provider = provider_id.lower().strip()
    creds = _load_credentials_dict()
    if provider in creds:
        del creds[provider]
        _save_credentials_dict(creds)
        logger.info("Removed API key for provider: %s", provider)


def has_api_key(provider_id: str) -> bool:
    """Returns True if a valid API key exists for the provider (stored or env)."""
    key = get_api_key(provider_id)
    return bool(key and len(key) > 0)


def mask_api_key(api_key: Optional[str]) -> str:
    """
    Returns a masked version of the API key for safe UI presentation.
    Never exposes full key text.
    Example: 'sk-proj-1234567890abcdef' -> 'sk-••••••••cdef'
    """
    if not api_key:
        return ""
    key = api_key.strip()
    if len(key) <= 8:
        return "••••••••"
    prefix = key[:3] if len(key) > 12 else ""
    suffix = key[-4:]
    return f"{prefix}••••••••{suffix}"

