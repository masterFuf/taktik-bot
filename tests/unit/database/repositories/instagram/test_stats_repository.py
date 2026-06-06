"""Unit tests for the Instagram daily stats repository."""

from taktik.core.database.repositories.instagram.stats import StatsRepository


def test_increment_interaction_updates_daily_stats(conn):
    repo = StatsRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (username, is_bot) VALUES ('bot', 1)")
    account_id = conn.execute(
        "SELECT account_id FROM instagram_accounts WHERE username = 'bot'"
    ).fetchone()["account_id"]

    assert repo.increment_interaction(account_id, "LIKE") is True
    assert repo.increment_interaction(account_id, "FOLLOW") is True

    stats = repo.get_account_stats(account_id, days=1)
    assert stats["total_likes"] == 1
    assert stats["total_follows"] == 1


def test_mark_as_synced_updates_synced_flags(conn):
    repo = StatsRepository(conn)
    conn.execute("INSERT INTO instagram_accounts (username, is_bot) VALUES ('bot', 1)")
    account_id = conn.execute(
        "SELECT account_id FROM instagram_accounts WHERE username = 'bot'"
    ).fetchone()["account_id"]

    repo.increment_interaction(account_id, "LIKE")
    unsynced = repo.find_unsynced()

    assert len(unsynced) == 1
    assert unsynced[0]["synced_to_api"] == 0

    assert repo.mark_as_synced([unsynced[0]["id"]]) is True

    synced = conn.execute(
        "SELECT synced_to_api, synced_at FROM daily_stats_unified WHERE id = ?",
        (unsynced[0]["id"],),
    ).fetchone()
    assert synced["synced_to_api"] == 1
    assert synced["synced_at"] is not None
