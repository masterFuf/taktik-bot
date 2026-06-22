"""Unit tests for DM conversation/message persistence repositories."""

from taktik.core.database.repositories.messaging import (
    DmThreadRepository,
    DmMessageRepository,
)


def test_thread_upsert_is_idempotent_per_account_and_partner(conn):
    repo = DmThreadRepository(conn)

    first = repo.upsert(
        platform="instagram",
        account_id=1,
        partner_username="TargetUser",
        last_message_text="Bonjour",
        last_message_is_ours=False,
        message_count=2,
    )
    # Same (platform, account, partner) -> same row, same sync_id (case-insensitive).
    second = repo.upsert(
        platform="instagram",
        account_id=1,
        partner_username="targetuser",
        last_message_text="Salut !",
        last_message_is_ours=True,
        message_count=3,
    )

    assert first == second
    rows = repo.query("SELECT * FROM dm_threads")
    assert len(rows) == 1
    assert rows[0]["partner_username"] == "targetuser"
    assert rows[0]["last_message_text"] == "Salut !"
    assert rows[0]["last_message_is_ours"] == 1
    assert rows[0]["message_count"] == 3


def test_thread_is_scoped_by_account_and_platform(conn):
    repo = DmThreadRepository(conn)
    repo.upsert(platform="instagram", account_id=1, partner_username="bob")
    repo.upsert(platform="instagram", account_id=2, partner_username="bob")
    repo.upsert(platform="tiktok", account_id=1, partner_username="bob")

    assert len(repo.query("SELECT * FROM dm_threads")) == 3


def test_messages_dedup_on_reread_by_content(conn):
    threads = DmThreadRepository(conn)
    messages = DmMessageRepository(conn)
    thread_sync_id = threads.upsert(platform="instagram", account_id=1, partner_username="bob")

    inserted_first = messages.add_message(
        platform="instagram", thread_sync_id=thread_sync_id,
        direction="received", text="Bonjour", seq=0,
    )
    # Re-reading the same conversation must not duplicate identical messages.
    inserted_again = messages.add_message(
        platform="instagram", thread_sync_id=thread_sync_id,
        direction="received", text="Bonjour", seq=0,
    )
    # A different direction with same text is a distinct message.
    inserted_sent = messages.add_message(
        platform="instagram", thread_sync_id=thread_sync_id,
        direction="sent", text="Bonjour", seq=1,
    )

    assert inserted_first is True
    assert inserted_again is False
    assert inserted_sent is True
    rows = messages.query("SELECT * FROM dm_messages ORDER BY seq")
    assert len(rows) == 2
    assert rows[0]["direction"] == "received"
    assert rows[1]["direction"] == "sent"


def test_find_account_id_by_partner(conn):
    repo = DmThreadRepository(conn)
    assert repo.find_account_id("instagram", "bob") is None

    repo.upsert(platform="instagram", account_id=42, partner_username="Bob")

    # The send path reuses this to attribute a reply without re-visiting our profile.
    assert repo.find_account_id("instagram", "bob") == 42
    assert repo.find_account_id("tiktok", "bob") is None


def test_message_carries_ai_metadata(conn):
    threads = DmThreadRepository(conn)
    messages = DmMessageRepository(conn)
    thread_sync_id = threads.upsert(platform="tiktok", account_id=5, partner_username="alice")

    messages.add_message(
        platform="tiktok", thread_sync_id=thread_sync_id, direction="sent",
        text="Merci !", ai_model="google/gemini-2.5-flash-lite", ai_cost_usd=0.00004,
    )

    row = messages.query_one("SELECT * FROM dm_messages")
    assert row["ai_model"] == "google/gemini-2.5-flash-lite"
    assert row["thread_sync_id"] == thread_sync_id
