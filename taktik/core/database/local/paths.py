"""Filesystem paths for the local TAKTIK SQLite database."""

from __future__ import annotations

import os
import sys


def get_default_database_path() -> str:
    """Return the default SQLite path used by standalone bridges."""
    if os.environ.get("TAKTIK_DB_PATH"):
        return os.environ["TAKTIK_DB_PATH"]

    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, "taktik-desktop", "taktik-data.db")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/taktik-desktop/taktik-data.db")
    return os.path.expanduser("~/.config/taktik-desktop/taktik-data.db")


__all__ = ["get_default_database_path"]
