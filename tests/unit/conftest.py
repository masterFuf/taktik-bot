"""
Shared pytest fixtures for the TAKTIK bot test suite.

All DB-related tests use an in-memory or temp-file SQLite database so they
never touch the real %APPDATA% database.
"""
import tempfile
import pathlib
import pytest

from taktik.core.database.local.service import LocalDatabaseService
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
