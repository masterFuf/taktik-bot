"""Who has written in our DM thread with someone, as the conversation record knows it.

The welcome DM's locks ask this before writing to a new follower. They used to ask a narrower
question -- "does the thread carry a message of OURS?" -- so a follower who had written to us and
never got an answer read as a stranger, and was greeted as one.

The record is written by the production writers here (the DM readers, our sends), into a real
SQLite file: the answer is a property of what is stored.
"""

import sqlite3

import pytest

from taktik.core.database.local.schemas.messaging import (
    create_messaging_indexes,
    create_messaging_tables,
)
from taktik.core.database.messaging import (
    NOBODY_HAS_WRITTEN,
    ONLY_THEY_HAVE_WRITTEN,
    WE_HAVE_WRITTEN,
    DmConversationService,
    who_has_written,
)

ACCOUNT_ID = 11
OTHER_ACCOUNT_ID = 12


@pytest.fixture
def database(tmp_path, monkeypatch):
    path = tmp_path / "taktik.db"
    connection = sqlite3.connect(path)
    create_messaging_tables(connection.cursor())
    create_messaging_indexes(connection.cursor())
    connection.commit()
    connection.close()
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))
    return path


@pytest.fixture
def tiktok_record(monkeypatch):
    """The TikTok writers, without the profile link (a separate concern with its own service)."""
    import taktik.core.database as database
    from taktik.core.database import tiktok_dm

    monkeypatch.setattr(database, "configure_db_service", lambda: None)
    monkeypatch.setattr(tiktok_dm, "_partner_profile_id", lambda handle: None)
    return tiktok_dm


def _instagram_read(partner, *messages):
    """What the Instagram DM reader records for one conversation."""
    DmConversationService.record_conversation(
        platform="instagram", account_id=ACCOUNT_ID, partner_username=partner,
        messages=[{"direction": direction, "text": text} for direction, text in messages],
    )


def test_nobody_has_written_when_no_thread_is_on_record(database):
    assert who_has_written("instagram", ACCOUNT_ID, ["newbie"]) == NOBODY_HAS_WRITTEN


def test_a_thread_holding_only_their_messages_means_they_wrote_to_us(database):
    """The case the locks missed: someone wrote, we never answered."""
    _instagram_read("newbie", ("received", "salut, j'adore ton compte"))

    assert who_has_written("instagram", ACCOUNT_ID, ["newbie"]) == ONLY_THEY_HAVE_WRITTEN


def test_once_we_have_answered_the_thread_is_ours_too(database):
    _instagram_read("newbie", ("received", "salut, j'adore ton compte"))
    DmConversationService.record_sent_message(
        platform="instagram", account_id=ACCOUNT_ID, partner_username="newbie", text="merci !",
    )

    assert who_has_written("instagram", ACCOUNT_ID, ["newbie"]) == WE_HAVE_WRITTEN


def test_a_thread_we_opened_and_nobody_answered_is_ours(database):
    DmConversationService.record_sent_message(
        platform="instagram", account_id=ACCOUNT_ID, partner_username="newbie", text="bienvenue",
    )

    assert who_has_written("instagram", ACCOUNT_ID, ["newbie"]) == WE_HAVE_WRITTEN


def test_a_sticker_from_them_is_them_writing(database, tiktok_record):
    """A sticker carries no text; it is still them opening the conversation."""
    tiktok_record.record_conversations(
        ACCOUNT_ID, [{"name": "fan_one", "messages": [{"type": "sticker", "text": None}]}]
    )

    assert who_has_written("tiktok", ACCOUNT_ID, ["fan_one"]) == ONLY_THEY_HAVE_WRITTEN


def test_a_tiktok_thread_read_from_the_inbox_is_filed_under_the_display_name(database, tiktok_record):
    """The TikTok DM read files a thread under the conversation header, which shows the DISPLAY
    NAME. Asked by handle alone, the record knows nothing of it; asked with the name the
    new-followers page showed, it does."""
    tiktok_record.record_conversations(
        ACCOUNT_ID, [{"name": "Fan Two", "messages": [{"text": "coucou", "is_sent": False}]}]
    )

    assert who_has_written("tiktok", ACCOUNT_ID, ["fan_two"]) == NOBODY_HAS_WRITTEN
    assert who_has_written("tiktok", ACCOUNT_ID, ["fan_two", "Fan Two"]) == ONLY_THEY_HAVE_WRITTEN


def test_our_message_in_either_thread_makes_the_conversation_ours(database, tiktok_record):
    """Their message under the display name, ours under the handle: we are already talking."""
    tiktok_record.record_conversations(
        ACCOUNT_ID, [{"name": "Fan Two", "messages": [{"text": "coucou", "is_sent": False}]}]
    )
    tiktok_record.record_sent(ACCOUNT_ID, "fan_two", "merci pour le suivi")

    assert who_has_written("tiktok", ACCOUNT_ID, ["fan_two", "Fan Two"]) == WE_HAVE_WRITTEN


def test_names_are_matched_as_the_record_stores_them(database):
    _instagram_read("newbie", ("received", "hello"))

    assert who_has_written("instagram", ACCOUNT_ID, ["@Newbie "]) == ONLY_THEY_HAVE_WRITTEN


def test_another_account_s_thread_says_nothing_about_this_one(database):
    DmConversationService.record_conversation(
        platform="instagram", account_id=OTHER_ACCOUNT_ID, partner_username="newbie",
        messages=[{"direction": "received", "text": "hello"}],
    )

    assert who_has_written("instagram", ACCOUNT_ID, ["newbie"]) == NOBODY_HAS_WRITTEN


def test_another_platform_s_thread_says_nothing_about_this_one(database):
    _instagram_read("newbie", ("received", "hello"))

    assert who_has_written("tiktok", ACCOUNT_ID, ["newbie"]) == NOBODY_HAS_WRITTEN


def test_a_record_that_cannot_be_read_raises_instead_of_answering_nobody(tmp_path, monkeypatch):
    """A lock must be able to refuse. "Nobody wrote" from a database that was never opened is
    how a private message goes to someone we were already talking to."""
    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "missing.db"))

    with pytest.raises(FileNotFoundError):
        who_has_written("instagram", ACCOUNT_ID, ["newbie"])


def test_a_query_that_fails_raises_too(tmp_path, monkeypatch):
    path = tmp_path / "broken.db"
    connection = sqlite3.connect(path)
    # A `dm_threads` without the columns the lookup reads.
    connection.execute("CREATE TABLE dm_threads (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))

    with pytest.raises(sqlite3.Error):
        who_has_written("instagram", ACCOUNT_ID, ["newbie"])
