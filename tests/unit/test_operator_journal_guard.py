"""The suite never writes the operator's journal.

The bot's journal is `logs/taktik.log` in its data folder: the folder of `TAKTIK_DB_PATH`, else
`%APPDATA%/taktik-desktop`, the operator's own. `tests/unit/conftest.py` moves that folder to a
throwaway directory before the tests import the bot. But importing `taktik` used to open the
journal right away, in the folder of that moment, and a pytest plugin (`-p`) is imported before
any conftest: on 2026-09-28 a run whose plugin imported the bot wrote its tests' log lines into
the operator's journal. The journal now opens in the data folder of the moment it writes its
first line, so the conftest's isolation holds whoever imported the bot first, and an open of the
operator's folder goes through the conftest's guard like any other.
"""

import os
import pathlib
import subprocess
import sys
import textwrap
from unit.paths import CORE

_CANARY = "journal canary"

# What a pytest plugin does before any conftest, then what tests/unit/conftest.py does.
_IMPORT_THEN_ISOLATE = textwrap.dedent(f"""
    import logging, os, sys
    import taktik
    os.environ["APPDATA"] = sys.argv[1]
    logging.getLogger("journal-canary").warning("{_CANARY}")
""")

_PLUGIN = textwrap.dedent(f"""
    import logging
    import taktik

    def pytest_runtest_call(item):
        logging.getLogger("journal-canary").warning("{_CANARY}")
""")


def _journal(appdata: pathlib.Path) -> pathlib.Path:
    return appdata / "taktik-desktop" / "logs" / "taktik.log"


def _bot_env(appdata: pathlib.Path, *python_path: pathlib.Path) -> dict:
    env = {name: value for name, value in os.environ.items()
           if name not in ("TAKTIK_DB_PATH", "TAKTIK_DATA_DIR")}
    env["APPDATA"] = str(appdata)
    env["PYTHONPATH"] = os.pathsep.join(str(path) for path in (*python_path, CORE))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def test_the_journal_opens_in_the_data_folder_of_its_first_line(tmp_path):
    operator, throwaway = tmp_path / "operator", tmp_path / "throwaway"

    subprocess.run(
        [sys.executable, "-c", _IMPORT_THEN_ISOLATE, str(throwaway)],
        env=_bot_env(operator), cwd=tmp_path, check=True, capture_output=True, timeout=120,
    )

    assert not _journal(operator).exists()
    assert _CANARY in _journal(throwaway).read_text(encoding="utf-8")


def test_a_plugin_importing_the_bot_before_the_conftest_leaves_the_operator_journal_alone(tmp_path):
    operator = tmp_path / "operator"
    (tmp_path / "journal_canary_plugin.py").write_text(_PLUGIN, encoding="utf-8")

    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         "-p", "journal_canary_plugin",
         "tests/unit/test_package_metadata.py::test_the_engine_version_is_the_release_one"],
        env=_bot_env(operator, tmp_path), cwd=CORE, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert not _journal(operator).exists()
