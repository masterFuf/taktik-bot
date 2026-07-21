"""A stored filter decision can expire, so a rejected profile gets another look.

`is_filtered` had no time bound: once a profile was filtered for an account it was
excluded from that account forever. But the dominant reasons describe a MOMENT, not a
profile — "Too few posts (0 < 3)" and "Private profile" were the top two on the real DB,
where 2424 of 3750 filtered rows were older than 60 days and still blocking.

The bound stays OPT-OUT: `max_age_days=None` keeps the permanent behaviour for an
operator who wants it.
"""

import sqlite3

import pytest

from taktik.core.database.repositories.instagram.interaction.interaction_repository import (
    InteractionRepository,
)


ACCOUNT = 42
OTHER_ACCOUNT = 43


@pytest.fixture
def repo():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute(
        """
        CREATE TABLE filtered_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            profile_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            filtered_at TEXT DEFAULT (datetime('now')),
            reason TEXT
        )
        """
    )

    def _add(username, account_id, days_ago):
        con.execute(
            "INSERT INTO filtered_profiles (platform, profile_id, account_id, username, filtered_at, reason) "
            "VALUES ('instagram', 1, ?, ?, datetime('now', '-' || ? || ' days'), 'Too few posts (0 < 3)')",
            (account_id, username, days_ago),
        )

    _add("fresh", ACCOUNT, 5)
    _add("stale", ACCOUNT, 200)
    _add("other_account", OTHER_ACCOUNT, 5)
    con.commit()

    class _Repo(InteractionRepository):
        def __init__(self):
            pass

        def query_one(self, sql, params=()):
            return con.execute(sql, params).fetchone()

    return _Repo()


def test_without_a_bound_every_stored_filter_still_applies(repo):
    # Operator chose permanent filtering: nothing expires.
    assert repo.is_filtered("fresh", ACCOUNT) is True
    assert repo.is_filtered("stale", ACCOUNT) is True


def test_a_recent_filter_still_applies_within_the_delay(repo):
    assert repo.is_filtered("fresh", ACCOUNT, max_age_days=90) is True


def test_an_old_filter_expires_and_the_profile_is_re_evaluated(repo):
    # Filtered 200 days ago, delay 90 -> no longer filtered: it gets looked at again.
    assert repo.is_filtered("stale", ACCOUNT, max_age_days=90) is False


def test_expiry_is_still_scoped_to_the_account(repo):
    # A profile filtered by ANOTHER account was never this account's business.
    assert repo.is_filtered("other_account", ACCOUNT, max_age_days=90) is False
    assert repo.is_filtered("other_account", OTHER_ACCOUNT, max_age_days=90) is True


def test_zero_is_treated_as_no_bound(repo):
    # RevisitPolicy maps "never" to None, but a stray 0 must not expire everything.
    assert repo.is_filtered("stale", ACCOUNT, max_age_days=0) is True
