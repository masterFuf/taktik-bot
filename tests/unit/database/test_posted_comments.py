"""The comments we post get a rich record of their own, not just a ledger row.

`interactions` answers "what did we do, to whom, when". A comment is the one gesture that
also carries CONTENT plus production metadata (which model wrote it, what it cost, why,
which post it landed on) — none of which fits a generic ledger column. `posted_comments`
holds that; these tests lock its contract.
"""

import sqlite3

import pytest

from taktik.core.database.instagram_posted_comments import build_post_ref
from taktik.core.database.local.schema import create_schema
from taktik.core.database.repositories.instagram import PostedCommentRepository


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return PostedCommentRepository(conn)


def test_schema_is_created_with_its_indexes():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    cur = conn.cursor()
    cols = {row[1] for row in cur.execute("PRAGMA table_info(posted_comments)")}
    # The columns that justify a dedicated table (content + production metadata + post ref).
    assert {"comment_text", "ai_model", "ai_cost_usd", "ai_reasoning",
            "post_ref", "post_url", "session_id", "target_username"} <= cols
    indexes = {row[0] for row in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='posted_comments'")}
    assert "idx_posted_comments_session" in indexes
    assert "idx_posted_comments_sync_id" in indexes


def test_create_schema_is_idempotent():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    create_schema(conn)  # must not raise on an existing base


def test_record_stores_the_ai_production_metadata(repo):
    row_id = repo.record(
        target_username="alice", comment_text="Trop beau ce spot",
        account_id=1, session_id=42, post_author="alice", post_caption="Sunset",
        source="ai", ai_model="google/gemini-3-flash-preview", ai_cost_usd=0.00084,
        ai_reasoning="reacted to the sunset", language="fr",
    )
    assert row_id

    rows = repo.get_by_session(42)
    assert len(rows) == 1
    row = rows[0]
    assert row["comment_text"] == "Trop beau ce spot"
    assert row["ai_model"] == "google/gemini-3-flash-preview"
    assert row["ai_cost_usd"] == pytest.approx(0.00084)
    assert row["ai_reasoning"] == "reacted to the sunset"
    assert row["source"] == "ai"
    # sync_id is generated so the row can be Turso-synced cross-device later.
    assert row["sync_id"]


def test_template_comment_has_no_ai_metadata(repo):
    repo.record(target_username="bob", comment_text="Superbe", session_id=7, source="template")
    row = repo.get_by_session(7)[0]
    assert row["source"] == "template"
    assert row["ai_model"] is None and row["ai_cost_usd"] is None


def test_post_url_is_attached_after_the_fact(repo):
    # The shareable link costs a share-sheet round trip, so it is captured AFTER the
    # comment is posted: the row must exist first and be completed only on success.
    row_id = repo.record(target_username="alice", comment_text="hey", session_id=1)
    assert repo.get_by_target("alice")[0]["post_url"] is None

    assert repo.attach_post_url(row_id, "https://instagram.com/p/XYZ/") is True
    assert repo.get_by_target("alice")[0]["post_url"] == "https://instagram.com/p/XYZ/"


def test_reads_are_scoped_and_ordered(repo):
    repo.record(target_username="alice", comment_text="one", session_id=1)
    repo.record(target_username="alice", comment_text="two", session_id=2)
    repo.record(target_username="bob", comment_text="three", session_id=1)

    assert {r["comment_text"] for r in repo.get_by_session(1)} == {"one", "three"}
    assert {r["comment_text"] for r in repo.get_by_target("alice")} == {"one", "two"}


def test_post_ref_groups_comments_left_on_the_same_post():
    # Free identity (no extra UI gesture): same author + same caption => same ref.
    assert build_post_ref("Alice", "Hello world") == build_post_ref("alice", "Hello world")
    assert build_post_ref("alice", "Hello world") != build_post_ref("alice", "Another caption")
    assert build_post_ref("alice", "Hello world") != build_post_ref("bob", "Hello world")


def test_post_ref_degrades_instead_of_failing():
    assert build_post_ref("alice", None) == "alice"       # no caption: author alone
    assert build_post_ref("@Alice", None) == "alice"       # @ and case normalised
    assert build_post_ref(None, None) is None              # nothing to key on
