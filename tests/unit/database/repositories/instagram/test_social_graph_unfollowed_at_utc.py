"""`unfollowed_at` is stamped on the clock of the rest of the follow graph: SQLite's, in UTC.

`first_seen_at` and `last_seen_at` are SQLite's `datetime('now')`, in UTC, and the interactions are
stamped in UTC too. `unfollowed_at` was the only one written from Python's `datetime.now()`, the
machine's local time: on a phone proof in France the UNFOLLOW interaction and the row it closed
were two hours apart. Any age computed from it was off by the machine's offset.

The machine here is made to live three hours east of UTC (its local clock is the only thing the
old code read), so the test is red on any machine, a UTC one included.
"""

from datetime import datetime, timedelta, timezone

import pytest

from taktik.core.database.repositories.instagram.social_graph import SocialGraphRepository
from taktik.core.database.repositories.instagram.social_graph import social_graph_repository as module

FORMAT = "%Y-%m-%d %H:%M:%S"


class _ClockThreeHoursEast(datetime):
    """`datetime` whose local time is three hours ahead of UTC, as on a machine east of Greenwich."""

    @classmethod
    def now(cls, tz=None):
        utc = datetime.now(timezone.utc)
        if tz is not None:
            return utc.astimezone(tz)
        return (utc + timedelta(hours=3)).replace(tzinfo=None)


def _row(conn, account_id, direction):
    return conn.execute(
        "SELECT unfollowed_at, last_seen_at FROM social_graph_sync "
        "WHERE account_id = ? AND username = 'someone' AND direction = ?",
        (account_id, direction),
    ).fetchone()


def _close(repo, account_id, direction):
    if direction == "following":
        repo.upsert_following("someone", "Someone", account_id, followed_by_bot=True, source="bot_follow")
        repo.mark_unfollowed("someone", account_id)
    else:
        repo.upsert_follower("someone", account_id, display_name="Someone")
        repo.mark_follower_gone("someone", account_id)


@pytest.mark.parametrize("platform", ["instagram", "tiktok"])
@pytest.mark.parametrize("direction", ["following", "follower"])
def test_a_closed_row_is_stamped_in_utc_like_the_rest_of_the_graph(conn, monkeypatch, platform, direction):
    monkeypatch.setattr(module, "datetime", _ClockThreeHoursEast)
    conn.execute(
        "INSERT INTO accounts (platform, legacy_account_id, username, is_bot) VALUES (?, 7, 'bot', 1)",
        (platform,),
    )
    conn.commit()
    repo = SocialGraphRepository(conn).for_platform(platform)

    _close(repo, 7, direction)

    row = _row(conn, 7, direction)
    assert row["unfollowed_at"] is not None
    unfollowed_at = datetime.strptime(row["unfollowed_at"], FORMAT)
    last_seen_at = datetime.strptime(row["last_seen_at"], FORMAT)
    utc_now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Same clock as `last_seen_at`, written in the same second or so, and that clock is UTC.
    assert abs((unfollowed_at - last_seen_at).total_seconds()) < 60
    assert abs((unfollowed_at - utc_now).total_seconds()) < 60
