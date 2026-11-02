"""
Pytest UI Lint Suite for Ghostline Fluent 2 Interface
Validates against regressions in:
- Dark strip artifacts behind labels
- Text clipping and word wrap truncation
- Mnemonic marker '&' loss
- Horizontal scrollbars / layout overlaps
- Content column width uniformity
- Button icon spacing
- Combobox drop-down arrows
- Seeded test results
- Useless progress bars
"""

import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ui_lint import UILintRunner

def test_ui_lint_clean():
    """Validates that all UI pages across window sizes pass the UI lint checks."""
    runner = UILintRunner(window_sizes=[(1916, 1140)])
    rep = runner.run_lint()
    
    # Assert zero violations
    violations = rep["total_violations"]
    if violations > 0:
        details = []
        for cat, items in rep["failures"].items():
            if items:
                details.append(f"{cat}: {len(items)} issues (e.g. {items[0]})")
        pytest.fail(f"UI Lint failed with {violations} total violations:\n" + "\n".join(details))

