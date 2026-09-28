"""Where this installation keeps its data, whoever started the process.

The desktop app spawns Python with a deliberately ALLOWLISTED environment — forwarding all of
`process.env` would leak the host's API keys into a child process — and `APPDATA` is not on that
list. Every module that resolved its folder with `os.environ.get('APPDATA', expanduser('~'))`
therefore fell through to the home directory and wrote to `~/taktik-desktop/`, a phantom folder
beside the real one. Silently: the writes succeed, they simply land where nobody looks.

Measured 2026-08-28: the followers tracker and every diagnostic screen capture had been landing
there. The captures of a run blocked by Instagram were on disk the whole time, in a folder the
operator had no reason to open.

What the app DOES inject is `TAKTIK_DB_PATH`, so the bot writes the SQLite file Electron reads.
The folder holding that file IS the data folder, which is what makes it the reliable answer here
— no change to the spawn environment, and one place to fix rather than six.
"""

import logging
import os
import sys
from typing import Optional


APP_FOLDER_NAME = 'taktik-desktop'


def platform_data_dir() -> str:
    """The folder the desktop app uses on this platform (Electron's `userData`), when nobody names one.

    Windows without `APPDATA` (a process started with a bare environment) falls back to the home
    folder rather than to a path relative to wherever the process runs.
    """
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA')
        if appdata:
            return os.path.join(appdata, APP_FOLDER_NAME)
    elif sys.platform == 'darwin':
        return os.path.expanduser(f'~/Library/Application Support/{APP_FOLDER_NAME}')
    else:
        return os.path.expanduser(f'~/.config/{APP_FOLDER_NAME}')
    return os.path.join(os.path.expanduser('~'), APP_FOLDER_NAME)


def get_app_data_dir() -> str:
    """The folder this installation writes to. Never raises, always returns a path.

    Order: an explicit `TAKTIK_DATA_DIR`, then the folder of the database the app told us to
    use, then the platform default. The middle one is what makes this work under the app.
    """
    explicit = os.environ.get('TAKTIK_DATA_DIR')
    if explicit:
        return explicit

    db_path = os.environ.get('TAKTIK_DB_PATH')
    if db_path:
        parent = os.path.dirname(os.path.abspath(db_path))
        if parent:
            return parent

    return platform_data_dir()


def get_app_subdir(*parts: str, create: bool = True) -> Optional[str]:
    """A folder inside the data dir (`logs`, `logs/screens`…). None if it cannot be made."""
    path = os.path.join(get_app_data_dir(), *parts)
    if not create:
        return path
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    return path


class DataFolderLogFile(logging.FileHandler):
    """A journal in `logs/` of the data folder, looked up when its first line is written.

    Not when the handler is made: importing the bot makes the journal, and whatever imports the
    bot first would otherwise fix its folder for the whole process. The test suite moves the data
    folder to a throwaway one in `tests/unit/conftest.py`, and a pytest plugin is imported before
    any conftest; a plugin that imported the bot sent the tests' lines to the operator's journal.
    """

    def __init__(self, file_name: str):
        self._file_name = file_name
        super().__init__(self._path_now(), encoding='utf-8', delay=True)

    def _path_now(self) -> str:
        return os.path.join(get_app_data_dir(), 'logs', self._file_name)

    def _open(self):
        self.baseFilename = os.path.abspath(self._path_now())
        os.makedirs(os.path.dirname(self.baseFilename), exist_ok=True)
        return super()._open()
