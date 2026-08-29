"""TikTok DM persistence, and the direction it cannot read off the screen.

`DMActions.get_messages` marks every message `is_sent: False` -- the mobile UI shows no sender.
Filing that as-is would build a table stating we never answered anybody, which is the one
question these tables exist to answer. What we send is certain at send time; these tests pin the
rule that recovers the rest.
"""

import sqlite3

import pytest

from taktik.core.database.messaging import DmConversationService
from taktik.core.database.local.schemas.messaging import (
    create_messaging_indexes,
    create_messaging_tables,
)


ACCOUNT_ID = 11
PARTNER = "allocingles"


@pytest.fixture
def database(tmp_path, monkeypatch):
    """A real SQLite file: the direction rule is a property of what is stored, not of a mock."""
    path = tmp_path / "taktik.db"
    connection = sqlite3.connect(path)
    create_messaging_tables(connection.cursor())
    create_messaging_indexes(connection.cursor())
    connection.commit()
    connection.close()

    monkeypatch.setattr(
        "taktik.core.database.messaging.get_default_database_path", lambda: str(path)
    )
    return path


@pytest.fixture
def persistence(monkeypatch):
    from bridges.tiktok.workflows.engagement.runtime import dm_persistence

    # The profile link is a separate concern with its own database service; the direction rule
    # under test does not depend on it.
    monkeypatch.setattr(dm_persistence, "configure_db_service", lambda: None)
    monkeypatch.setattr(dm_persistence, "_partner_profile_id", lambda handle: None)
    return dm_persistence


def _stored(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT direction, text FROM dm_messages ORDER BY seq"
    ).fetchall()
    connection.close()
    return [(row["direction"], row["text"]) for row in rows]


def test_a_read_message_defaults_to_received(database, persistence):
    persistence.record_conversations(
        ACCOUNT_ID, [{"name": PARTNER, "messages": [{"text": "salut", "type": "text"}]}]
    )
    assert _stored(database) == [("received", "salut")]


def test_our_own_message_is_recognised_on_a_later_read(database, persistence):
    """The reader sees no sender. What makes this ours is that we recorded sending it."""
    persistence.record_sent(ACCOUNT_ID, PARTNER, "Bien recu")
    persistence.record_conversations(
        ACCOUNT_ID,
        [{"name": PARTNER, "messages": [{"text": "salut"}, {"text": "Bien recu"}]}],
    )
    assert ("sent", "Bien recu") in _stored(database)
    assert ("received", "Bien recu") not in _stored(database)


def test_the_answered_signal_is_the_point_of_all_this(database, persistence):
    persistence.record_conversations(ACCOUNT_ID, [{"name": PARTNER, "messages": [{"text": "salut"}]}])
    state = DmConversationService.thread_answer_state("tiktok", ACCOUNT_ID, PARTNER)
    assert state["has_sent"] is False

    persistence.record_sent(ACCOUNT_ID, PARTNER, "Bien recu")
    persistence.record_conversations(
        ACCOUNT_ID, [{"name": PARTNER, "messages": [{"text": "salut"}, {"text": "Bien recu"}]}]
    )
    assert DmConversationService.thread_answer_state("tiktok", ACCOUNT_ID, PARTNER)["has_sent"] is True


def test_a_second_read_does_not_duplicate_the_thread_or_its_messages(database, persistence):
    conversation = [{"name": PARTNER, "messages": [{"text": "salut"}, {"text": "ca va ?"}]}]
    persistence.record_conversations(ACCOUNT_ID, conversation)
    persistence.record_conversations(ACCOUNT_ID, conversation)

    connection = sqlite3.connect(database)
    assert connection.execute("SELECT COUNT(*) FROM dm_threads").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM dm_messages").fetchone()[0] == 2
    connection.close()


def test_a_conversation_without_messages_leaves_the_thread_alone(database, persistence):
    persistence.record_conversations(ACCOUNT_ID, [{"name": PARTNER, "messages": [{"text": "salut"}]}])
    persistence.record_conversations(ACCOUNT_ID, [{"name": PARTNER, "messages": []}])

    connection = sqlite3.connect(database)
    count = connection.execute("SELECT message_count FROM dm_threads").fetchone()[0]
    connection.close()
    assert count == 1


def test_only_the_messages_that_actually_left_are_recorded(database, persistence):
    """A row for a message that never went out would claim an answer no screen can back up."""
    persistence.record_sent_results(
        ACCOUNT_ID,
        [{"conversation": PARTNER, "message": "parti"}, {"conversation": "other", "message": "rate"}],
        [{"conversation": PARTNER, "success": True}, {"conversation": "other", "success": False}],
    )
    assert _stored(database) == [("sent", "parti")]


def test_nothing_is_written_without_an_identified_account(database, persistence):
    persistence.record_conversations(None, [{"name": PARTNER, "messages": [{"text": "salut"}]}])
    persistence.record_sent(None, PARTNER, "Bien recu")
    assert _stored(database) == []


def test_a_display_name_is_kept_as_partner_but_never_linked_as_a_handle(database, persistence):
    """A conversation header can show "Marie D 🌸"; that is not a handle and must not become one."""
    assert persistence._looks_like_handle("Marie D") is False
    assert persistence._looks_like_handle("marie.d_1") is True

    persistence.record_conversations(
        ACCOUNT_ID, [{"name": "Marie D", "messages": [{"text": "coucou"}]}]
    )
    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT partner_username, partner_profile_id FROM dm_threads"
    ).fetchone()
    connection.close()
    # The repository lowercases the partner on both write and lookup, so the thread key stays
    # stable whatever casing a header shows.
    assert row == ("marie d", None)


def test_our_message_stays_ours_when_the_header_changes_case(database, persistence):
    """The thread key is lowercased on write AND on lookup; the direction rule rides on that."""
    persistence.record_sent(ACCOUNT_ID, "AlloCinGles", "Bien recu")
    persistence.record_conversations(
        ACCOUNT_ID, [{"name": "allocingles", "messages": [{"text": "Bien recu"}]}]
    )
    assert _stored(database) == [("sent", "Bien recu")]


def test_the_logged_in_handle_is_normalised_before_it_becomes_an_account(persistence, monkeypatch):
    seen = []

    class FakeService:
        def get_or_create_account(self, username, is_bot=False):
            seen.append((username, is_bot))
            return 42, False

    monkeypatch.setattr(persistence, "get_db_service", lambda: FakeService())
    assert persistence.resolve_account_id("@AlloCinGles") == 42
    assert seen == [("allocingles", True)]

    # An unreadable profile is not an account: persistence is skipped rather than attributed
    # to a made-up row.
    assert persistence.resolve_account_id("") is None
    assert persistence.resolve_account_id("Marie D") is None
