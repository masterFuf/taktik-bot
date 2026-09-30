"""One computation of where the SQLite base is (decision D2 of 2026-09-27).

The service every CLI command opens (`LocalDatabaseService`) and the default the bridges and the
database facades read (`get_default_database_path`) each computed the path. They agreed on Windows
with `APPDATA`; without it, the service took the home folder and the bridges a path relative to the
current directory, and on Linux and macOS the service took `~/taktik-desktop` while the bridges took
the folder Electron uses. The service now reads the bridges' computation, which reads the data
folder of `shared/app_paths.py`.

What the app, the CLI and the bridges open on Windows does not change: `TAKTIK_DB_PATH` when it is
set (the app always sets it), else `%APPDATA%/taktik-desktop/taktik-data.db`, the file the app's
`app.getPath('userData')` holds. No path is opened here.
"""

from __future__ import annotations

import os
import sys

import pytest

from taktik.core.database.local import service as service_module
from taktik.core.database.local.paths import get_default_database_path
from taktik.core.shared.app_paths import get_app_data_dir


@pytest.fixture
def environment(monkeypatch, tmp_path):
    """An empty environment on a chosen platform, with a throwaway home and APPDATA."""
    home = tmp_path / "home"
    appdata = tmp_path / "appdata"
    for name in ("TAKTIK_DB_PATH", "TAKTIK_DATA_DIR", "APPDATA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(service_module.LocalDatabaseService, "_ensure_database", lambda self: None)

    def use(platform: str, *, with_appdata: bool = True, db_path: str | None = None):
        monkeypatch.setattr(sys, "platform", platform)
        if with_appdata:
            monkeypatch.setenv("APPDATA", str(appdata))
        if db_path is not None:
            monkeypatch.setenv("TAKTIK_DB_PATH", db_path)
        return home, appdata

    return use


def _service_path() -> str:
    return service_module.LocalDatabaseService().db_path


def test_windows_with_appdata_is_the_app_base_everywhere(environment):
    _, appdata = environment("win32")
    expected = os.path.join(str(appdata), "taktik-desktop", "taktik-data.db")

    assert get_default_database_path() == expected
    assert _service_path() == expected


def test_the_path_the_app_injects_wins_everywhere(environment, tmp_path):
    injected = str(tmp_path / "userData" / "taktik-data.db")
    environment("win32", db_path=injected)

    assert get_default_database_path() == injected
    assert _service_path() == injected


def test_windows_without_appdata_is_the_home_folder_everywhere(environment):
    home, _ = environment("win32", with_appdata=False)
    expected = os.path.join(str(home), "taktik-desktop", "taktik-data.db")

    assert get_default_database_path() == expected
    assert _service_path() == expected


@pytest.mark.parametrize("platform, folder", [
    ("linux", os.path.join(".config", "taktik-desktop")),
    ("darwin", os.path.join("Library", "Application Support", "taktik-desktop")),
])
def test_linux_and_macos_follow_electron_everywhere(environment, platform, folder):
    home, _ = environment(platform, with_appdata=False)
    expected = os.path.normpath(os.path.join(str(home), folder, "taktik-data.db"))

    assert os.path.normpath(get_default_database_path()) == expected
    assert os.path.normpath(_service_path()) == expected


@pytest.mark.parametrize("platform", ["win32", "linux", "darwin"])
def test_the_base_lives_in_the_data_folder(environment, platform):
    environment(platform)

    assert os.path.dirname(get_default_database_path()) == get_app_data_dir()
