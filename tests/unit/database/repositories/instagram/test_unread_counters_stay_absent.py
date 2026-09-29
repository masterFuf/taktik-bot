"""A counter that was not read is no count: it stays absent (NULL), never 0.

`profile_stats_history` is a series: one snapshot of a profile's counters each time it is read.
`ProfileRepository.record_stats_history` filled a counter it was not given with 0, and
`LocalDatabaseService.save_profile` asked a snapshot of a profile of which only the name was read (a
row of a list, never opened): its series fell to 0 followers, 0 followings, 0 posts. A new profile
saved without its counters was written as a public profile with 0 followers
(`ProfileRepository.get_or_create`). And the visit's own chain (`save_profile_to_database`,
`InstagramProfile`, `LocalDatabaseClient.save_profile`) turned a counter or a privacy it did not
have into 0 or « public » before the repository saw it, over what the base knew.

As the lot `correctifs` did for `send_profile_captured`: what was not read stays out, never 0 or
false. The three counters of a snapshot are NOT NULL in its table, which has no room for an unread
one: without all three, no snapshot. A flag not read stays NULL.
"""

from taktik.core.database.local.client import LocalDatabaseClient
from taktik.core.database.local.service import LocalDatabaseService
from taktik.core.database.repositories.instagram.profile.profile_repository import ProfileRepository
from taktik.core.social_media.instagram.actions.business.management.profile import persistence


def _snapshots(con, profile_id):
    return con.execute("SELECT * FROM profile_stats_history WHERE profile_id = ?", (profile_id,)).fetchall()


def _row(con, username):
    return con.execute(
        "SELECT followers_count, following_count, posts_count, is_private, is_verified, is_business "
        "FROM social_profiles WHERE platform = 'instagram' AND username = ?",
        (username,),
    ).fetchone()


# --- the series --------------------------------------------------------------------------------


def test_a_snapshot_needs_its_three_counters_read(conn):
    repo = ProfileRepository(conn)
    profile_id, _ = repo.get_or_create("half_read", followers_count=1000, following_count=42)

    assert repo.record_stats_history(profile_id, {"followers_count": 1000, "following_count": 42}) is False

    assert _snapshots(conn, profile_id) == [], "a snapshot with a posts count nobody read"


def test_a_snapshot_keeps_a_flag_not_read_null(conn):
    repo = ProfileRepository(conn)
    profile_id, _ = repo.get_or_create("fully_read", followers_count=1000, following_count=42, posts_count=12)

    assert repo.record_stats_history(
        profile_id, {"followers_count": 1000, "following_count": 42, "posts_count": 12}) is True

    (snapshot,) = _snapshots(conn, profile_id)
    assert (snapshot["followers_count"], snapshot["following_count"], snapshot["posts_count"]) == (1000, 42, 12)
    assert snapshot["is_verified"] is None


def test_a_list_row_saved_without_its_counters_has_no_snapshot(db: LocalDatabaseService):
    # A row of a scraped list, never opened: its name, nothing counted.
    result = db.save_profile({"username": "list_row", "full_name": "List Row"})

    assert _snapshots(db._get_connection(), result["profile_id"]) == []


def test_a_counter_read_as_none_is_saved_without_a_snapshot(db: LocalDatabaseService):
    # The visit could not read the followers: None, which the service compared with 0.
    result = db.save_profile({"username": "no_followers_read", "followers_count": None,
                              "following_count": 5, "posts_count": 3})

    con = db._get_connection()
    assert _snapshots(con, result["profile_id"]) == []
    assert _row(con, "no_followers_read")["followers_count"] is None


# --- a new profile -----------------------------------------------------------------------------


def test_a_new_profile_keeps_what_was_not_read_null(conn):
    ProfileRepository(conn).get_or_create("fresh_row", full_name="Fresh Row")

    assert tuple(_row(conn, "fresh_row")) == (None, None, None, None, None, None), \
        "a profile nobody opened passed for a public profile with 0 followers"


def test_a_new_profile_keeps_what_was_read(conn):
    ProfileRepository(conn).get_or_create("read_row", followers_count=12, following_count=0, posts_count=3,
                                          is_private=False, is_verified=True)

    assert tuple(_row(conn, "read_row")) == (12, 0, 3, 0, 1, None)


def test_the_profile_reader_keeps_a_flag_not_read_unknown(conn):
    repo = ProfileRepository(conn)
    repo.get_or_create("fresh_flags")

    profile = repo.find_by_username("fresh_flags")

    assert (profile["is_private"], profile["is_verified"], profile["is_business"]) == (None, None, None)


# --- the visit's chain: save_profile_to_database -> InstagramProfile -> LocalDatabaseClient ------


def _client_on(db: LocalDatabaseService) -> LocalDatabaseClient:
    """The production client, on the test's base instead of the process's."""
    client = LocalDatabaseClient.__new__(LocalDatabaseClient)
    client.local_db = db
    return client


def test_the_visit_saves_a_counter_it_did_not_read_as_absent(db: LocalDatabaseService, monkeypatch):
    monkeypatch.setattr(persistence, "get_db_service", lambda: _client_on(db))

    persistence.save_profile_to_database({"username": "visited", "full_name": "Visited",
                                          "following_count": 7, "posts_count": 2})

    con = db._get_connection()
    row = _row(con, "visited")
    assert (row["followers_count"], row["following_count"], row["posts_count"]) == (None, 7, 2)
    assert row["is_private"] is None
    profile_id = con.execute("SELECT legacy_profile_id FROM social_profiles WHERE username = 'visited'").fetchone()[0]
    assert _snapshots(con, profile_id) == []


def test_the_visit_keeps_what_the_base_knew_when_it_did_not_read_it(db: LocalDatabaseService, monkeypatch):
    db.get_or_create_profile({"username": "known", "followers_count": 500, "following_count": 80,
                              "posts_count": 9, "is_private": True})
    monkeypatch.setattr(persistence, "get_db_service", lambda: _client_on(db))

    persistence.save_profile_to_database({"username": "known", "full_name": "Known", "posts_count": 10})

    row = _row(db._get_connection(), "known")
    assert (row["followers_count"], row["following_count"], row["posts_count"]) == (500, 80, 10)
    assert row["is_private"] == 1, "a privacy the visit did not read turned the profile public"
