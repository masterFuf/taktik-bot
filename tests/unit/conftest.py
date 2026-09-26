"""
Shared pytest fixtures for the TAKTIK bot test suite.

No test touches the operator's database. DB tests get a temp-file base (`db`, `conn`,
`tmp_path`). The guard below enforces it: before `taktik` is imported it moves the default data
folder into a throwaway directory, then fails any test that opens a SQLite base there or
anything in the operator's own data folder, even when the code under test swallows the error.
"""
import logging
import os
import pathlib
import shutil
import site
import sys
import tempfile
import threading
import traceback
import urllib.parse

import pytest

_DATA_FOLDER = "taktik-desktop"
_CORE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _operator_data(env):
    """Folders and files where the bot finds the operator's data on its own."""
    home = os.path.expanduser("~")
    folders = [
        os.path.join(home, _DATA_FOLDER),
        os.path.join(home, ".config", _DATA_FOLDER),
        os.path.join(home, "Library", "Application Support", _DATA_FOLDER),
    ]
    if env.get("APPDATA"):
        folders.append(os.path.join(env["APPDATA"], _DATA_FOLDER))
    if env.get("TAKTIK_DATA_DIR"):
        folders.append(env["TAKTIK_DATA_DIR"])
    files = [env["TAKTIK_DB_PATH"]] if env.get("TAKTIK_DB_PATH") else []
    return folders, files


class RealDatabaseAccess(PermissionError):
    """A test reached a base it must never open."""


class _RealDatabaseGuard:
    """Audit hook refusing, before the file is touched:

    - any open of the operator's data (folders, or the `TAKTIK_DB_PATH` file and its -wal/-shm);
    - any SQLite open in the default data folder, where an accessor lands when nothing injected
      a base.
    """

    def __init__(self, sealed_folders, sealed_files, default_folder):
        self._sealed_folders = [self._norm(p) for p in sealed_folders]
        self._sealed_files = [self._norm(p) for p in sealed_files]
        self._default_folder = self._norm(default_folder)
        self._hits = []
        self._local = threading.local()

    @staticmethod
    def _norm(path):
        return os.path.normcase(os.path.abspath(path))

    @staticmethod
    def _under(path, folder):
        return path == folder or path.startswith(folder + os.sep)

    def _target(self, name):
        try:
            raw = os.fsdecode(os.fspath(name))
        except TypeError:
            return None
        if raw.startswith("file:"):
            raw = urllib.parse.unquote(raw[5:].split("?", 1)[0])
            stripped = raw.lstrip("/")
            if stripped[1:2] == ":":
                raw = stripped
        if raw in ("", ":memory:"):
            return None
        return self._norm(raw)

    def _refused(self, event, path):
        if any(path == f or path.startswith(f + "-") for f in self._sealed_files):
            return True
        if any(self._under(path, folder) for folder in self._sealed_folders):
            return True
        return event == "sqlite3.connect" and self._under(path, self._default_folder)

    def __call__(self, event, args):
        if (event != "sqlite3.connect" and event != "open") or not args:
            return
        if getattr(self._local, "busy", False):
            return
        path = self._target(args[0])
        if path is None or not self._refused(event, path):
            return
        self._local.busy = True
        try:
            frames = traceback.StackSummary.extract(
                traceback.walk_stack(sys._getframe(1)), limit=40, lookup_lines=False)
            where = [f"{os.path.relpath(f.filename, _CORE_ROOT)}:{f.lineno} in {f.name}"
                     for f in frames if f.filename.startswith(_CORE_ROOT)
                     and f.filename != __file__]
            self._hits.append((event, path, where[:10]))
        finally:
            self._local.busy = False
        raise RealDatabaseAccess(f"tests never open {path}")

    def take(self):
        hits, self._hits = self._hits, []
        return hits

    @staticmethod
    def explain(hits, previous=None):
        lines = ["Opened a base a test must never open (tests/unit/conftest.py guard):"]
        for event, path, where in hits:
            lines.append(f"  {event} {path}")
            lines.extend(f"      {frame}" for frame in where)
        lines.append("Give it a throwaway base: the `db`/`conn` fixtures, `tmp_path`, or a "
                     "monkeypatched accessor (`get_local_database`, the facade's `_db`).")
        if previous is not None:
            lines.extend(["", str(previous)])
        return "\n".join(lines)


_OPERATOR_FOLDERS, _OPERATOR_FILES = _operator_data(os.environ)
_THROWAWAY_APPDATA = tempfile.mkdtemp(prefix="taktik-tests-appdata-")
# Python derives the user site-packages from APPDATA on Windows: subprocesses keep the real one.
os.environ.setdefault("PYTHONUSERBASE", site.getuserbase())
os.environ["APPDATA"] = _THROWAWAY_APPDATA
for _name in ("TAKTIK_DB_PATH", "TAKTIK_DATA_DIR"):
    os.environ.pop(_name, None)
_DEFAULT_FOLDER = os.path.join(_THROWAWAY_APPDATA, _DATA_FOLDER)
os.makedirs(_DEFAULT_FOLDER)
# A decoy base: code that opens the default base only when it exists is caught too.
open(os.path.join(_DEFAULT_FOLDER, "taktik-data.db"), "wb").close()
_GUARD = _RealDatabaseGuard(
    sealed_folders=_OPERATOR_FOLDERS,
    sealed_files=_OPERATOR_FILES,
    default_folder=_DEFAULT_FOLDER,
)
sys.addaudithook(_GUARD)


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    outcome = yield
    hits = _GUARD.take()
    if hits:
        report = outcome.get_result()
        report.outcome = "failed"
        report.longrepr = _GUARD.explain(hits, report.longrepr)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    hits = _GUARD.take()
    if hits:
        report = outcome.get_result()
        report.outcome = "failed"
        report.longrepr = _GUARD.explain(hits, report.longrepr)


def pytest_sessionfinish(session, exitstatus):
    hits = _GUARD.take()
    if hits:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
        sys.stderr.write(_GUARD.explain(hits) + "\n")


def pytest_unconfigure(config):
    for handler in list(logging.getLogger().handlers):
        if getattr(handler, "baseFilename", "").startswith(_THROWAWAY_APPDATA):
            logging.getLogger().removeHandler(handler)
            handler.close()
    shutil.rmtree(_THROWAWAY_APPDATA, ignore_errors=True)


@pytest.fixture
def real_database_guard():
    """The guard itself, for tests that trigger a refusal on purpose and `take()` it."""
    return _GUARD


@pytest.fixture(autouse=True)
def _database_singletons_start_empty():
    """A singleton left by an earlier test would serve its base here and hide an unguarded path."""
    from taktik.core import database
    from taktik.core.database.local import service

    leaked = service._local_db_instance
    if isinstance(leaked, service.LocalDatabaseService):
        leaked.close()
    service._local_db_instance = None
    database.db_service = None


from taktik.core.database.local.service import LocalDatabaseService  # noqa: E402 - after the guard
from taktik.core.database.local.schema import create_schema
from taktik.core.database.local.migrations import run_migrations, _validate_sql_identifier


@pytest.fixture(autouse=True)
def _no_keyboard_given_back_at_exit(monkeypatch):
    """No test leaves a phone whose keyboard `atexit` would "give back" with the real adb at the
    end of pytest (the keyboard switch remembers the phone's own keyboard since 2026-09-24)."""
    from taktik.core.shared.input import taktik_keyboard

    monkeypatch.setattr(taktik_keyboard, "_original_ime", {})
    monkeypatch.setattr(taktik_keyboard, "_atexit_registered", True)


# Class attributes `install_instagram_ai_hooks` rewrites for the whole process. A test that
# installed the hooks left them installed: the interaction-engine tests collected after it ran
# the AI wrapper instead of the engine and made no gesture (13 failures in reverse order, found
# 2026-09-24; the polluter was test_instagram_ai_hooks.py).
_AI_HOOKED_ATTRIBUTES = (
    ("taktik.core.social_media.instagram.actions.business.workflows.post_url.workflow",
     "PostUrlBusiness", "in_thread_reply_writer"),
    ("taktik.core.social_media.instagram.actions.business.actions.comment.action",
     "CommentAction", "comment_on_post"),
    ("taktik.core.social_media.instagram.actions.core.base_business.interaction_engine",
     "InteractionEngineMixin", "_perform_interactions_on_profile"),
    ("taktik.core.social_media.instagram.actions.business.actions.like.orchestration",
     "LikeOrchestration", "like_current_post"),
)


@pytest.fixture(autouse=True)
def _ai_hooks_never_outlive_their_test():
    """Put back, after each test, the methods the Instagram AI hooks replace."""
    import importlib

    missing = object()
    saved = []
    for module_name, class_name, attribute in _AI_HOOKED_ATTRIBUTES:
        owner = getattr(importlib.import_module(module_name), class_name)
        saved.append((owner, attribute, owner.__dict__.get(attribute, missing)))
    yield
    for owner, attribute, value in saved:
        if value is missing:
            if attribute in owner.__dict__:
                delattr(owner, attribute)
        else:
            setattr(owner, attribute, value)


@pytest.fixture
def tmp_db_path(tmp_path: pathlib.Path) -> str:
    """Return a path to a fresh temporary SQLite file (deleted after test)."""
    return str(tmp_path / "taktik_test.db")


@pytest.fixture
def db(tmp_db_path: str) -> LocalDatabaseService:
    """Return a fully-initialised LocalDatabaseService backed by a temp DB.

    The service is closed automatically after the test.
    """
    svc = LocalDatabaseService(db_path=tmp_db_path)
    yield svc
    svc.close()


@pytest.fixture
def conn(tmp_db_path: str):
    """Return a raw sqlite3 connection with schema + migrations applied.

    Useful for tests that want direct SQL access without the service layer.
    """
    import sqlite3

    con = sqlite3.connect(tmp_db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    create_schema(con)
    run_migrations(con)
    yield con
    con.close()
