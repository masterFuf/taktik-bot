"""What was SENT is recorded, once for the stable half and per call for the rest.

The point of the design is size: the system prompt of a classification is ~9 KB and byte-identical
from one call to the next, so storing it per call would write ~150 MB a month for a single distinct
string. It is content-addressed instead — hashed once, pointed at afterwards. These tests lock both
halves of that: the body travels once, and the pointer resolves.
"""

import sqlite3

import pytest

from taktik.core.app.ai.providers.openrouter import AIService
from taktik.core.database.local.schema import create_schema
from taktik.core.database.repositories.eval import PromptCaptureRepository


@pytest.fixture()
def repo(tmp_path):
    conn = sqlite3.connect(tmp_path / "capture.db")
    conn.row_factory = sqlite3.Row
    create_schema(conn)
    return PromptCaptureRepository(conn, None), conn


def test_the_body_travels_once_and_the_pointer_afterwards():
    """A 9 KB prompt identical on every call must not be handed out on every call."""
    service = AIService(api_key="test-key")

    first = service.build_prompt_capture("STABLE SYSTEM PROMPT", "profile A")
    second = service.build_prompt_capture("STABLE SYSTEM PROMPT", "profile B")

    assert first["hash"] == second["hash"]
    assert first["system"] == "STABLE SYSTEM PROMPT"
    assert "system" not in second, "the body was handed out twice for the same hash"
    # The half that actually varies rides on every call.
    assert first["user"] == "profile A" and second["user"] == "profile B"


def test_a_changed_prompt_is_a_different_body():
    """The hash is what tells a run under the old prompt from one under the new."""
    service = AIService(api_key="test-key")
    a = service.build_prompt_capture("PROMPT V1", "x")
    b = service.build_prompt_capture("PROMPT V2", "x")
    assert a["hash"] != b["hash"]
    assert "system" in b


def test_cacheable_blocks_are_hashed_as_one_message():
    """`cacheable_system()` returns blocks; the hash must describe the whole system message."""
    service = AIService(api_key="test-key")
    capture = service.build_prompt_capture(
        [{"type": "text", "text": "STABLE"}, {"type": "text", "text": "VARIABLE"}], "x"
    )
    assert capture["system"] == "STABLE\nVARIABLE"


def test_a_body_seen_again_counts_a_use_without_being_rewritten(repo):
    """Later calls carry no body; the row must keep the text it already has."""
    repository, conn = repo
    repository.remember_body("h1", "profile", "THE PROMPT")
    repository.remember_body("h1", "profile", None)
    repository.remember_body("h1", "profile", None)

    row = conn.execute("SELECT body, uses FROM ai_prompt_bodies WHERE hash = 'h1'").fetchone()
    assert row["body"] == "THE PROMPT", "an empty later call overwrote the stored body"
    assert row["uses"] == 3


def test_a_capture_written_before_the_comment_is_bound_after(repo):
    """The comment's id only exists once it is published.

    Writing the capture first is what keeps the prompt of a comment REFUSED downstream — the one
    case worth reading — so the binding has to happen afterwards.
    """
    repository, conn = repo
    capture_id = repository.record_call(
        kind="comment", username="someone", model="qwen/qwen3.7-flash",
        prompt_hash="h1", user_prompt="the post caption", persona_json='{"niche": "beauty"}',
    )
    assert capture_id

    row = conn.execute("SELECT comment_id FROM ai_call_captures WHERE id = ?", (capture_id,)).fetchone()
    assert row["comment_id"] is None

    repository.attach_comment_id(capture_id, 4242)
    row = conn.execute("SELECT comment_id FROM ai_call_captures WHERE id = ?", (capture_id,)).fetchone()
    assert row["comment_id"] == 4242
