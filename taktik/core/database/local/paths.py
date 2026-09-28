"""Filesystem paths for the local TAKTIK SQLite database.

The one computation of where the base is: the CLI's service (`LocalDatabaseService`), the bridges
and the database facades all read `get_default_database_path` (decision D2 of 2026-09-27).
"""

from __future__ import annotations

import os

from taktik.core.shared.app_paths import platform_data_dir

DATABASE_FILE_NAME = "taktik-data.db"


def get_default_database_path() -> str:
    """The SQLite file of this installation.

    `TAKTIK_DB_PATH` when it is set: the desktop app always sets it for the processes it starts, to
    the file it opens itself. Otherwise the file of the desktop app's data folder on this platform
    (`%APPDATA%/taktik-desktop` on Windows, the folder Electron uses on Linux and macOS).
    """
    explicit = os.environ.get("TAKTIK_DB_PATH")
    if explicit:
        return explicit
    return os.path.join(platform_data_dir(), DATABASE_FILE_NAME)


__all__ = ["DATABASE_FILE_NAME", "get_default_database_path"]
