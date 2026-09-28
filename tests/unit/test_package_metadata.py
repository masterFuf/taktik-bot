"""The package metadata says what the engine is, and its version once (decision D4 of 2026-09-27).

`setup.py` announced version 1.1.6 while `taktik.__version__` (what the banner and the installer
scripts print, what the update check compares with the GitHub release) said 1.2.1, and described a
French "Instagram & TikTok platform" when the engine drives five apps. The version is now read from
`taktik/__init__.py`, the one place it is written.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import taktik

_CORE_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _setup(option: str) -> str:
    result = subprocess.run(
        [sys.executable, "setup.py", option],
        cwd=_CORE_ROOT, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return result.stdout.strip().splitlines()[-1]


def test_setup_announces_the_engine_version():
    assert _setup("--version") == taktik.__version__


def test_the_engine_version_is_the_release_one():
    assert taktik.__version__ == "1.9.9"


def test_setup_describes_every_app_the_engine_drives():
    description = _setup("--description")

    for app in ("Instagram", "TikTok", "YouTube", "Threads", "Gmail"):
        assert app in description
