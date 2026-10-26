"""
Ghostline — Build Information & Version Verification
Synchronized at build and release time with Git commit, build timestamp, and runtime mode.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any

VERSION = "1.0.1"
__version__ = VERSION

# Built-in fallback metadata (updated during release packaging)
DEFAULT_COMMIT = "74dea3388b0c747f8851e6eb77ad51968ce2ed04"
DEFAULT_SHORT_COMMIT = "74dea33"
DEFAULT_BUILD_TIME = "2026-10-26 22:16:34"


def _load_build_json() -> Dict[str, Any]:
    """Attempts to load build_info.json from app directory or MEIPASS."""
    cand_dirs = [
        Path(__file__).resolve().parent,
        Path(getattr(sys, "_MEIPASS", "")),
        Path(sys.executable).resolve().parent,
        Path(sys.executable).resolve().parent / "_internal",
    ]
    for d in cand_dirs:
        try:
            if d and d.exists():
                json_path = d / "build_info.json"
                if json_path.exists():
                    with open(json_path, "r", encoding="utf-8") as f:
                        return json.load(f)
        except Exception:
            pass
    return {}


_json_info = _load_build_json()


def _resolve_git_commit() -> str:
    """Dynamically resolves Git commit hash if in source tree, else uses build json or fallback."""
    if _json_info.get("git_commit"):
        return _json_info["git_commit"]
    try:
        root = Path(__file__).resolve().parent.parent
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=2
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return DEFAULT_COMMIT


GIT_COMMIT = _resolve_git_commit()
GIT_COMMIT_SHORT = _json_info.get("git_commit_short") or (GIT_COMMIT[:7] if GIT_COMMIT else DEFAULT_SHORT_COMMIT)
BUILD_TIMESTAMP = _json_info.get("build_timestamp") or DEFAULT_BUILD_TIME
BUILD_ID = f"{VERSION}-{GIT_COMMIT_SHORT}"
BUILD_IDENTIFIER = f"Ghostline v{VERSION} ({GIT_COMMIT_SHORT}) [{BUILD_TIMESTAMP}]"


def get_running_mode() -> str:
    """Returns whether the application is running from source or packaged binary."""
    if os.environ.get("GHOSTLINE_MODE") == "DEVELOPMENT":
        return "DEVELOPMENT (Source Tree)"
    if getattr(sys, "frozen", False):
        return "INSTALLED / PACKAGED BUILD"
    return "DEVELOPMENT (Source Tree)"


def get_build_summary() -> Dict[str, Any]:
    """Returns comprehensive build metadata for UI, logs, and diagnostics."""
    return {
        "version": VERSION,
        "build_id": BUILD_ID,
        "git_commit": GIT_COMMIT,
        "git_commit_short": GIT_COMMIT_SHORT,
        "build_timestamp": BUILD_TIMESTAMP,
        "running_mode": get_running_mode(),
        "frozen": getattr(sys, "frozen", False),
        "executable": sys.executable,
        "build_identifier": BUILD_IDENTIFIER
    }
