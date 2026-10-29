"""Shared helpers. Fixtures are generated in tmp folders; every brand in them is invented."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "make-colors-pptx"
sys.path.insert(0, str(SKILL / "scripts"))


def make_clean_dir():
    """The Make_Clean_PPTX skill, when available (CI checks it out; locally a sibling clone works)."""
    from preview_deck import find_make_clean
    return find_make_clean(os.environ.get("MAKE_CLEAN_PPTX_DIR") or ROOT.parent / "Make_Clean_PPTX")


@pytest.fixture
def harbour_roles():
    return {"name": "Demo Harbour", "primary": "#1D4E89", "secondary": "#E07A1F",
            "fonts": {"major": "Georgia", "minor": "Arial"}}
