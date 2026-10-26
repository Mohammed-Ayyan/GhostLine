"""
Ghostline: Privacy-First, On-Device AI Screen & Live Audio Assistant
"""

import os
import sys

__version__ = "1.0.1"
BUILD_ID = "2026.10.26-build.203"
__author__ = "Antigravity Autonomous Systems"


def get_running_mode() -> str:
    """Returns whether the application is running from source or packaged binary."""
    if os.environ.get("GHOSTLINE_MODE") == "DEVELOPMENT":
        return "DEVELOPMENT (Source Tree)"
    if getattr(sys, "frozen", False):
        return "INSTALLED / PACKAGED BUILD"
    return "DEVELOPMENT (Source Tree)"

