"""Following edges discovered on other profiles — the domain that had no test at all.

Against a real SQLite database, because everything that matters here is what SQLite does:
the unique constraint that makes a re-read a no-op, the count of rows actually inserted, the
`classified_at IS NULL` guard that writes a verdict once.

The count is the reason this file exists. `save_edges` promised "the number of new rows" and
read it from `SELECT changes()` after an `executemany` — which reports the LAST statement
only, so inserting two hundred edges returned 1. Nothing failed; the debug trace simply lied
about the size of every following list ever saved.
"""

import sqlite3
import warnings
from datetime import datetime, timezone

import pytest

from taktik.core.database.repositories.instagram.social_graph import ProfileFollowingRepository


def _base() -> sqlite3.Connection:
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
    conn.commit()
    return conn


@pytest.fixture
def repo():
    return ProfileFollowingRepository(_base())


def _edges(repo, profile_username):
    """What is stored for one profile, read from the table (no repository read lists edges)."""
    return repo.conn.execute(
        "SELECT following_username, following_id FROM profile_following WHERE profile_username = ?",
        (profile_username,),
    ).fetchall()


def test_the_count_is_the_number_of_rows_actually_inserted(repo):
    """The bug this domain carried: `SELECT changes()` after executemany reported 1."""
    inserted = repo.save_edges("alice", ["b1", "b2", "b3", "b4", "b5"])
    assert inserted == 5, "the caller logs this number — it must match reality"
    assert len(_edges(repo, "alice")) == 5


def test_re_reading_the_same_profile_inserts_nothing(repo):
    """INSERT OR IGNORE: a second pass over the same list is a no-op, not an error."""
    assert repo.save_edges("alice", ["b1", "b2"]) == 2
    assert repo.save_edges("alice", ["b1", "b2"]) == 0
    assert len(_edges(repo, "alice")) == 2


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
    rows = {r["following_username"]: r for r in _edges(repo, "alice")}
    assert rows["b1"]["following_id"] is not None
    assert rows["unknown_one"]["following_id"] is None


def test_a_classification_is_written_once(repo):
    """Re-running the batch must never overwrite an earlier verdict."""
    repo.save_edges("alice", ["b1"])
    assert repo.save_classifications({"b1": {"niche_category": "sport", "gender": "f"}}) == 1
    assert repo.save_classifications({"b1": {"niche_category": "food", "gender": "m"}}) == 0

    stored = repo.conn.execute(
        "SELECT niche_category, gender FROM profile_following WHERE following_username = 'b1'"
    ).fetchone()
    assert tuple(stored) == ("sport", "f")


def test_the_classification_time_is_utc_and_asks_no_deprecated_clock(repo):
    """`datetime.utcnow()` is deprecated since Python 3.12 and warns. The time written is the
    same UTC wall clock, in the same `YYYY-MM-DD HH:MM:SS` text, taken from an aware clock."""
    repo.save_edges("alice", ["b1"])
    before = datetime.now(timezone.utc).replace(microsecond=0)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        assert repo.save_classifications({"b1": {"niche_category": "sport"}}) == 1
    after = datetime.now(timezone.utc)

    stored = repo.conn.execute("SELECT classified_at FROM profile_following").fetchone()[0]
    written = datetime.strptime(stored, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    assert before <= written <= after


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


@pytest.mark.parametrize(
    "call",
    [
        lambda repo: repo.save_edges("alice", ["b1"]),
        lambda repo: repo.unclassified_usernames(),
    ],
    ids=["save_edges", "unclassified_usernames"],
)
def test_a_broken_table_raises_instead_of_reading_as_empty(repo, call):
    """0 would read as "every edge already known", [] as "nothing pending". The caller decides what a refusal costs its run, and says it."""
    repo.conn.execute("DROP TABLE profile_following")
    repo.conn.commit()

    with pytest.raises(sqlite3.DatabaseError):
        call(repo)


def _refuse_following(conn: sqlite3.Connection, username: str) -> None:
    """An insert SQLite itself refuses (a trigger), as a locked or damaged base would."""
    conn.execute(f"""
        CREATE TRIGGER refuse_edge_{username} BEFORE INSERT ON profile_following
        WHEN NEW.following_username = '{username}'
        BEGIN SELECT RAISE(ABORT, 'refused'); END
    """)
    conn.commit()


def test_a_refused_list_leaves_no_half_written_edges(repo):
    """The first edges of a refused list must not wait in the open transaction for the
    next commit of another repository on the same connection."""
    _refuse_following(repo.conn, "b3")

    with pytest.raises(sqlite3.DatabaseError):
        repo.save_edges("alice", ["b1", "b2", "b3"])
    repo.conn.commit()

    count = repo.conn.execute("SELECT COUNT(*) FROM profile_following").fetchone()[0]
    assert count == 0


def _refuse_classifying(conn: sqlite3.Connection, username: str) -> None:
    """A write SQLite itself refuses (a trigger), as a locked or damaged base would."""
    conn.execute(f"""
        CREATE TRIGGER refuse_{username} BEFORE UPDATE ON profile_following
        WHEN NEW.following_username = '{username}'
        BEGIN SELECT RAISE(ABORT, 'refused'); END
    """)
    conn.commit()


def test_a_refused_classification_raises_instead_of_reading_as_already_done(repo):
    """The verdicts were paid for: a failed write must not return 0, which reads as
    "already classified". The workflow catches it and says how many were lost."""
    repo.save_edges("alice", ["b1"])
    _refuse_classifying(repo.conn, "b1")

    with pytest.raises(sqlite3.DatabaseError):
        repo.save_classifications({"b1": {"niche_category": "sport"}})


def test_a_refused_batch_leaves_no_half_written_classification(repo):
    """The first verdict of a refused batch must not wait in the open transaction for the
    next commit of another repository on the same connection."""
    repo.save_edges("alice", ["b1", "b2"])
    _refuse_classifying(repo.conn, "b2")

    with pytest.raises(sqlite3.DatabaseError):
        repo.save_classifications({"b1": {"niche_category": "sport"}, "b2": {}})
    repo.conn.commit()

    assert sorted(repo.unclassified_usernames()) == ["b1", "b2"]
