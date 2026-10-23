"""A bridge run as the app runs it: the launcher, its config file, a throwaway base."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest
from unit.paths import CORE

LAUNCHER = CORE / "bridges" / "launcher.py"
#: Runs the real launcher with one module made unimportable, as a broken install would leave it.
WITHOUT_MODULE = CORE / "tests" / "unit" / "bridge_without_module.py"


@pytest.fixture
def run_bridge_process(tmp_path: Path):
    """`run(bridge, config, blocked=None)` -> (process, its `error` lines).

    `blocked` names a module that does not import in that process. `TAKTIK_DB_PATH` points into
    `tmp_path`: a test can check that no base was created.
    """

    def run(bridge: str, config, blocked: Optional[str] = None):
        config_path = tmp_path / f"{bridge}.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE", "APPDATA",
                                                "PYTHONUSERBASE") if key in os.environ}
        env.update({"PYTHONIOENCODING": "utf-8", "TAKTIK_DB_PATH": str(tmp_path / "taktik-data.db")})
        command = ([sys.executable, str(WITHOUT_MODULE), blocked] if blocked
                   else [sys.executable, str(LAUNCHER)]) + [bridge, str(config_path)]
        proc = subprocess.run(command, cwd=str(CORE), env=env, capture_output=True, timeout=180)
        lines = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.startswith("{")]
        return proc, [line for line in lines if line.get("type") == "error"]

    return run
