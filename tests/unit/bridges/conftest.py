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
#: Runs the real launcher with one call that raises, and optionally a stand-in phone.
WITH_FAULT = CORE / "tests" / "unit" / "bridge_with_fault.py"


@pytest.fixture
def run_bridge_process(tmp_path: Path):
    """`run(bridge, config, blocked=None, fault=None, phone=False, passes=(), db_path=None)` ->
    (process, its `error` lines).

    `blocked` names a module that does not import in that process; `fault` a `<module>:<name>` that
    raises when called, `phone` a connection that succeeds on a stand-in device, `passes` the steps
    that return True instead of asking it (`tests/unit/bridge_with_fault.py`). `TAKTIK_DB_PATH`
    points into `tmp_path` (or at `db_path`): a test can check that no base was created.
    """

    def run(bridge: str, config, blocked: Optional[str] = None, fault: Optional[str] = None,
            phone: bool = False, passes: tuple = (), db_path: Optional[Path] = None):
        config_path = tmp_path / f"{bridge}.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "TEMP", "TMP", "USERPROFILE", "APPDATA",
                                                "PYTHONUSERBASE") if key in os.environ}
        env.update({"PYTHONIOENCODING": "utf-8", "TAKTIK_DB_PATH": str(db_path or tmp_path / "taktik-data.db")})
        if blocked:
            command = [sys.executable, str(WITHOUT_MODULE), blocked]
        elif fault:
            command = [sys.executable, str(WITH_FAULT)] + (["--phone"] if phone else [])
            for step in passes:
                command += ["--passes", step]
            command.append(fault)
        else:
            command = [sys.executable, str(LAUNCHER)]
        command += [bridge, str(config_path)]
        proc = subprocess.run(command, cwd=str(CORE), env=env, capture_output=True, timeout=180)
        lines = [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.startswith("{")]
        return proc, [line for line in lines if line.get("type") == "error"]

    return run
