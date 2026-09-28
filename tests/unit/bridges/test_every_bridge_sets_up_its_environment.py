"""Every bridge sets up the bridge environment itself, before it imports anything else.

`setup_environment()` (UTF-8 stdio, the bridge log handler on stderr, the engine on `sys.path`) is
the first thing a bridge does. Most entries call it, or import `bridge_base` or `platform_bridge`,
which call it. Five got it by chance: a package `__init__.py` on their way led to one of those two
modules (`bridges/common/__init__.py`, `bridges/common/runtime/__init__.py`, the network re-export
of `bridges/common/device/__init__.py`). Once those re-exports went, the schema bridge logged
through loguru's default handler, coloured in a terminal, and the Lab entries kept the raw stdio.

Each entry is loaded alone, in a fresh interpreter, as the launcher loads it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CORE = Path(__file__).resolve().parents[3]
MANIFEST = CORE / "bridges" / "bridges.manifest.json"

# Run by the child interpreter: load the entry, then say whether the bridge environment is set up.
_PROBE = """
import importlib
import sys

sys.path.insert(0, sys.argv[1])
importlib.import_module(sys.argv[2])
from bridges.common import bootstrap

print("set up" if bootstrap._initialized else "not set up")
"""


def _entries() -> dict[str, str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    return {key: module for bridges in manifest.values() for key, module in bridges.items()}


def _environment_after_loading(module: str, db_path: Path) -> str:
    env = dict(os.environ, TAKTIK_DB_PATH=str(db_path), PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [sys.executable, "-c", _PROBE, str(CORE), module],
        cwd=str(CORE), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=180,
    )
    lines = result.stdout.strip().splitlines()
    if result.returncode != 0 or not lines:
        return f"not loaded: {result.stderr.strip()[-800:]}"
    return lines[-1]


def test_every_bridge_entry_sets_up_the_bridge_environment_when_loaded_alone(tmp_path):
    entries = _entries()
    with ThreadPoolExecutor(max_workers=6) as pool:
        verdicts = dict(zip(entries, pool.map(
            lambda module: _environment_after_loading(module, tmp_path / "probe.db"), entries.values())))

    assert entries
    assert {key: verdict for key, verdict in verdicts.items() if verdict != "set up"} == {}
