"""The prompt-capture facade writes through the database SINGLETON, never a fresh service.

Building `LocalDatabaseService` replays the whole migration suite, rebuilds the SQLAlchemy engine
and takes a write lock on a file shared with the Electron app. The facade is called on the comment
path, twice per comment (`record` when the model answers, `attach_comment` once the comment is
published), so a fresh instance per call meant two full database initialisations per comment --
and two SQLite connections nobody ever closed.

`scripts/audit_database_singleton.py` catches the direct call statically; this test locks the
behaviour: no construction at all, and the rows land in the base the singleton already holds.
"""

import pytest

from taktik.core.database.ai_prompt_captures import AiPromptCaptures
from taktik.core.database.local import service as service_module


@pytest.fixture
def singleton(db, monkeypatch):
    """Install the fixture service as THE singleton, and make any further construction visible."""
    monkeypatch.setattr(service_module, "_local_db_instance", db)

    built = []

    def _refuse_construction(self, *args, **kwargs):
        built.append((args, kwargs))
        raise AssertionError("LocalDatabaseService was constructed instead of reused")

    monkeypatch.setattr(service_module.LocalDatabaseService, "__init__", _refuse_construction)
    return db, built


def test_record_and_attach_reuse_the_singleton(singleton):
    db, built = singleton

    capture_id = AiPromptCaptures.record(
        {"hash": "h1", "system": "STABLE SYSTEM PROMPT", "user": "the post caption"},
        kind="comment",
        username="someone",
        model="qwen/qwen3.7-flash",
    )
    attached = AiPromptCaptures.attach_comment(capture_id, 4242)
    # A later call of the same run carries no body, only the pointer.
    second_id = AiPromptCaptures.record({"hash": "h1", "user": "another caption"}, kind="comment")

    assert built == [], "the facade built a second database service instead of the singleton"
    assert capture_id and attached and second_id

    conn = db._get_connection()
    call = conn.execute(
        "SELECT comment_id, prompt_hash, user_prompt FROM ai_call_captures WHERE id = ?",
        (capture_id,),
    ).fetchone()
    assert call["comment_id"] == 4242
    assert call["prompt_hash"] == "h1"
    assert call["user_prompt"] == "the post caption"

    body = conn.execute("SELECT body, uses FROM ai_prompt_bodies WHERE hash = 'h1'").fetchone()
    assert body["body"] == "STABLE SYSTEM PROMPT"
    assert body["uses"] == 2


def test_a_database_failure_is_still_swallowed(monkeypatch):
    """Going through the accessor must not lose the best-effort contract: no capture, no crash."""

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(service_module, "get_local_database", _boom)

    assert AiPromptCaptures.record({"hash": "h1", "user": "x"}, kind="comment") is None
    assert AiPromptCaptures.attach_comment(1, 2) is False
