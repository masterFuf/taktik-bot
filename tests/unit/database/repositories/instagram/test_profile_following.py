"""Following edges discovered on other profiles — the domain that had no test at all.

Against a real SQLite database, because everything that matters here is what SQLite does:
the unique constraint that makes a re-read a no-op, the count of rows actually inserted, the
`classified_at IS NULL` guard that writes a verdict once, and a JOIN whose shape depends on
which tables the base happens to have.

The count is the reason this file exists. `save_edges` promised "the number of new rows" and
read it from `SELECT changes()` after an `executemany` — which reports the LAST statement
only, so inserting two hundred edges returned 1. Nothing failed; the debug trace simply lied
about the size of every following list ever saved.
"""

import sqlite3

import pytest

from taktik.core.database.repositories.instagram.social_graph import (
    ProfileFollowingRepository,
    profile_ai_read_model,
)


def _base(with_enrichment: bool = False) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE profile_following (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_username TEXT NOT NULL,
            profile_id INTEGER,
            following_username TEXT NOT NULL,
            following_id INTEGER,
            session_id TEXT,
            niche_category TEXT,
            niche TEXT,
            gender TEXT,
            classified_at TEXT,
            discovered_at TEXT DEFAULT (datetime('now')),
            UNIQUE(profile_username, following_username)
        )
    """)
    conn.execute("""
        CREATE TABLE instagram_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            location_city TEXT
        )
    """)
    if with_enrichment:
        conn.execute("""
            CREATE TABLE profile_ai_enrichments (
                enrichment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT,
                profile_id INTEGER,
                ai_niche TEXT,
                ai_specific_niche TEXT,
                ai_profession TEXT,
                location_city TEXT,
                updated_at TEXT
            )
        """)
    conn.commit()
    return conn


@pytest.fixture
def repo():
    return ProfileFollowingRepository(_base())


def test_the_count_is_the_number_of_rows_actually_inserted(repo):
    """The bug this domain carried: `SELECT changes()` after executemany reported 1."""
    inserted = repo.save_edges("alice", ["b1", "b2", "b3", "b4", "b5"])
    assert inserted == 5, "the caller logs this number — it must match reality"
    assert len(repo.following_of("alice")) == 5


def test_re_reading_the_same_profile_inserts_nothing(repo):
    """INSERT OR IGNORE: a second pass over the same list is a no-op, not an error."""
    assert repo.save_edges("alice", ["b1", "b2"]) == 2
    assert repo.save_edges("alice", ["b1", "b2"]) == 0
    assert len(repo.following_of("alice")) == 2


def test_only_the_new_edges_are_counted(repo):
    repo.save_edges("alice", ["b1", "b2"])
    assert repo.save_edges("alice", ["b2", "b3", "b4"]) == 2


@pytest.mark.parametrize("empty", [[], None, ["", None]])
def test_nothing_to_save_is_not_an_error(repo, empty):
    assert repo.save_edges("alice", empty) == 0


def test_an_unnamed_profile_saves_nothing(repo):
    assert repo.save_edges("", ["b1"]) == 0


def test_known_accounts_are_linked_by_id(repo):
    """The edge carries the FK when we already know the account, for later joins."""
    repo.conn.execute("INSERT INTO instagram_profiles (username) VALUES ('alice')")
    repo.conn.execute("INSERT INTO instagram_profiles (username) VALUES ('b1')")
    repo.conn.commit()

    repo.save_edges("alice", ["b1", "unknown_one"])
    rows = {r["following_username"]: r for r in repo.following_of("alice")}
    assert rows["b1"]["following_id"] is not None
    assert rows["unknown_one"]["following_id"] is None


def test_a_classification_is_written_once(repo):
    """Re-running the batch must never overwrite an earlier verdict.

    Read from the table directly, not through `following_of`: that read aliases the AI
    columns of `profile_ai_enrichments` onto the same names, so it never surfaces the
    classification stored on the edge itself. Pinned as-is — it is the behaviour the two
    enriched reads have always had.
    """
    repo.save_edges("alice", ["b1"])
    assert repo.save_classifications({"b1": {"niche_category": "sport", "gender": "f"}}) == 1
    assert repo.save_classifications({"b1": {"niche_category": "food", "gender": "m"}}) == 0

    stored = repo.conn.execute(
        "SELECT niche_category, gender FROM profile_following WHERE following_username = 'b1'"
    ).fetchone()
    assert tuple(stored) == ("sport", "f")


def test_the_enriched_read_does_not_surface_the_edge_classification(repo):
    """Documented quirk, not a change: `following_of` aliases the enrichment columns onto
    `niche_category`, so a classification written on the edge is invisible there."""
    repo.save_edges("alice", ["b1"])
    repo.save_classifications({"b1": {"niche_category": "sport"}})

    assert repo.following_of("alice")[0]["niche_category"] is None


def test_a_partial_classification_gets_its_defaults(repo):
    repo.save_edges("alice", ["b1"])
    repo.save_classifications({"b1": {}})

    row = repo.conn.execute(
        "SELECT niche_category, niche, gender FROM profile_following"
    ).fetchone()
    assert tuple(row) == ("other", "Other", "unknown")


def test_classifying_nothing_is_not_an_error(repo):
    assert repo.save_classifications({}) == 0


def test_unclassified_usernames_are_the_pending_work(repo):
    repo.save_edges("alice", ["b1", "b2"])
    repo.save_classifications({"b1": {"niche_category": "sport"}})

    assert repo.unclassified_usernames() == ["b2"]


def test_the_pending_list_is_deduplicated(repo):
    """Two profiles following the same account is one classification to make, not two."""
    repo.save_edges("alice", ["shared"])
    repo.save_edges("bob", ["shared"])

    assert repo.unclassified_usernames() == ["shared"]


def test_seed_list_reads_the_edge_from_the_other_end(repo):
    """profiles_following answers 'who do we know that follows @x'."""
    repo.save_edges("alice", ["source"])
    repo.save_edges("bob", ["source"])
    repo.save_edges("carol", ["someone_else"])

    followers = {r["profile_username"] for r in repo.profiles_following("source")}
    assert followers == {"alice", "bob"}


def test_a_base_without_the_enrichment_table_still_reads(repo):
    """A standalone base may predate profile_ai_enrichments: read what exists, do not fail."""
    repo.save_edges("alice", ["b1"])
    rows = repo.following_of("alice")

    assert len(rows) == 1
    assert rows[0]["niche_category"] is None      # nothing to enrich from
    assert rows[0]["profession"] is None


def test_the_enrichment_join_takes_the_latest_verdict():
    """With the table present, the most recently updated enrichment wins."""
    conn = _base(with_enrichment=True)
    conn.execute("INSERT INTO instagram_profiles (username, location_city) VALUES ('b1', 'Lyon')")
    pid = conn.execute("SELECT profile_id FROM instagram_profiles").fetchone()[0]
    conn.executemany(
        """INSERT INTO profile_ai_enrichments
           (platform, profile_id, ai_niche, ai_specific_niche, ai_profession, location_city, updated_at)
           VALUES ('instagram', ?, ?, ?, ?, ?, ?)""",
        [(pid, "old", "old_sub", "old_job", None, "2026-01-01 00:00:00"),
         (pid, "new", "new_sub", "new_job", "Paris", "2026-06-01 00:00:00")],
    )
    conn.commit()

    repo = ProfileFollowingRepository(conn)
    repo.save_edges("alice", ["b1"])
    row = repo.following_of("alice")[0]

    assert row["niche_category"] == "new"
    assert row["profession"] == "new_job"
    assert row["cities"] == "Paris"           # enrichment wins over the factual column


def test_the_factual_city_is_used_when_the_ai_has_none():
    conn = _base(with_enrichment=True)
    conn.execute("INSERT INTO instagram_profiles (username, location_city) VALUES ('b1', 'Lyon')")
    pid = conn.execute("SELECT profile_id FROM instagram_profiles").fetchone()[0]
    conn.execute(
        """INSERT INTO profile_ai_enrichments
           (platform, profile_id, ai_niche, location_city, updated_at)
           VALUES ('instagram', ?, 'sport', NULL, '2026-06-01 00:00:00')""",
        (pid,),
    )
    conn.commit()

    repo = ProfileFollowingRepository(conn)
    repo.save_edges("alice", ["b1"])
    assert repo.following_of("alice")[0]["cities"] == "Lyon"


def test_the_read_model_adapts_to_the_base():
    without = profile_ai_read_model(_base(with_enrichment=False), "p")
    assert without["join"] == ""
    assert without["niche"] == "NULL"

    with_it = profile_ai_read_model(_base(with_enrichment=True), "p")
    assert "profile_ai_enrichments" in with_it["join"]
    assert with_it["niche"] == "pae.ai_niche"


def test_a_broken_table_does_not_raise_into_the_workflow(repo):
    repo.conn.execute("DROP TABLE profile_following")
    repo.conn.commit()

    assert repo.save_edges("alice", ["b1"]) == 0
    assert repo.save_classifications({"b1": {}}) == 0
    assert repo.unclassified_usernames() == []
    assert repo.profiles_following("source") == []
    assert repo.following_of("alice") == []
