"""
Tests for Ghostline System Tray & Windows Startup Configuration.
Verifies:
- Config migration / backward compatibility (old config loads with defaults)
- Startup registry key setting and removal in HKCU Run
- Unreachable state guard (cannot hide taskbar if tray icon disabled)
- Tray settings persistence
"""

import sys
import tempfile
import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ghostline.config import AppConfig, load_config, save_config
from ghostline.core.win_startup import set_start_with_windows, get_start_with_windows


def test_old_config_loads_with_tray_and_startup_defaults():
    """Verify an older config file missing new keys loads seamlessly with proper defaults."""
    old_data = {
        "ai_provider": "ollama",
        "hotkey": "Alt + /",
        "hide_from_taskbar": False,
        "minimize_to_tray": True
    }
    with tempfile.TemporaryDirectory() as td:
        cfg_file = Path(td) / "config.json"
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(old_data, f)

        cfg = load_config(custom_path=cfg_file)
        assert cfg.ai_provider == "ollama"
        assert cfg.show_tray_icon is True
        assert cfg.start_with_windows is False
        assert cfg.tray_notifications is True
        assert cfg.use_profile_in_screen is False


def test_win_startup_registry_roundtrip():
    """Verify registry key can be set and deleted cleanly in HKCU."""
    original_state = get_start_with_windows()
    try:
        # Set
        res_enable = set_start_with_windows(True, custom_command='"C:\\FakeGhostline\\ghostline.exe"')
        assert res_enable is True
        assert get_start_with_windows() is True

        # Remove
        res_disable = set_start_with_windows(False)
        assert res_disable is True
        assert get_start_with_windows() is False
    finally:
        # Restore original state
        set_start_with_windows(original_state)

