"""Where the bot writes when the app is the one that started it.

The desktop app spawns Python with an allowlisted environment — forwarding all of `process.env`
would leak the host's API keys — and `APPDATA` is not on that list. Every writer that resolved
its folder with `os.environ.get('APPDATA', expanduser('~'))` silently landed in
`~/taktik-desktop/`, beside the real folder. The writes succeed; nobody ever looks there.

What the app DOES inject is `TAKTIK_DB_PATH`. Deriving from it is what makes these paths land
where the operator is looking, which is the whole point of a diagnostic.
"""

import os
import subprocess
import sys

import pytest

from taktik.core.shared.app_paths import get_app_data_dir, get_app_subdir
from unit.paths import CORE


def test_the_data_folder_follows_the_database_the_app_handed_us(monkeypatch):
    monkeypatch.delenv("TAKTIK_DATA_DIR", raising=False)
    monkeypatch.setenv("TAKTIK_DB_PATH", os.path.join("C:\\", "somewhere", "taktik-desktop",
                                                      "taktik-data.db"))

    assert get_app_data_dir() == os.path.join("C:\\", "somewhere", "taktik-desktop")


def test_an_explicit_data_dir_wins(monkeypatch):
    monkeypatch.setenv("TAKTIK_DATA_DIR", os.path.join("D:\\", "elsewhere"))
    monkeypatch.setenv("TAKTIK_DB_PATH", os.path.join("C:\\", "somewhere", "taktik-data.db"))

    assert get_app_data_dir() == os.path.join("D:\\", "elsewhere")


def test_a_subfolder_is_not_prefixed_twice(monkeypatch, tmp_path):
    """The callers used to append 'taktik-desktop' themselves, on top of a root that already
    carried it. Doubling it would recreate the phantom folder one level deeper."""
    monkeypatch.setenv("TAKTIK_DATA_DIR", str(tmp_path / "taktik-desktop"))
    monkeypatch.delenv("TAKTIK_DB_PATH", raising=False)

    screens = get_app_subdir("logs", "screens", create=False)

    assert screens == str(tmp_path / "taktik-desktop" / "logs" / "screens")
    assert screens.count("taktik-desktop") == 1


def test_the_writers_land_in_that_folder(monkeypatch, tmp_path):
    """The two writers whose output went missing, checked against the same root."""
    monkeypatch.setenv("TAKTIK_DATA_DIR", str(tmp_path))
    from taktik.core.social_media.instagram.actions.business.workflows.common.followers_tracker import (
        FollowersTracker,
    )
    from taktik.core.shared.diagnostics.screen_snapshot import _snapshot_dir

    assert str(FollowersTracker("acct", "target").log_dir).startswith(str(tmp_path))
    assert _snapshot_dir().startswith(str(tmp_path))


_BARE_ENV_RUN = "import logging, taktik; logging.getLogger('bare').warning('a line for the journal')"


@pytest.mark.skipif(sys.platform != "win32", reason="elsewhere the home comes from the password database")
def test_a_process_without_any_home_stops_instead_of_writing_in_its_current_folder(tmp_path):
    """Started with a bare environment (no APPDATA, USERPROFILE nor HOME, no TAKTIK_* variable),
    the bot resolved `~` to itself and wrote `~/taktik-desktop/logs/taktik.log` in its current
    folder: one sat at the root of the core's checkout. It now stops at once and says what to set."""
    env = {name: os.environ[name] for name in ("PATH", "SystemRoot") if name in os.environ}
    env["PYTHONPATH"] = str(CORE)
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    run = subprocess.run([sys.executable, "-c", _BARE_ENV_RUN], env=env, cwd=tmp_path,
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)

    assert list(tmp_path.iterdir()) == []
    assert run.returncode != 0
    assert "DataFolderUnknown" in run.stderr and "TAKTIK_DATA_DIR" in run.stderr
