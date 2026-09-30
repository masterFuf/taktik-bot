"""The memory that stops a hashtag run re-opening a post it already mined.

Exercised against a real SQLite database, not a mock: the whole point of this table is what
SQLite does with it — the uniqueness that makes a re-record an update, the time window, and
the hashtag folding that decides whether a lookup finds anything at all.

That folding is the trap worth pinning. A row is stored bare and lowercased ("paris"), so a
lookup for "#Paris" only matches because both sides fold the same way. The normalisation
used to be spelled out at each of the four call sites; one of them forgetting it would have
produced a memory that never matches — a run silently re-working every post, every time.
"""

import sqlite3

import pytest

from taktik.core.database.repositories.instagram.hashtag import (
    ProcessedHashtagPostRepository,
    normalize_hashtag,
)


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE processed_hashtag_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            hashtag TEXT NOT NULL,
            post_author TEXT NOT NULL,
            post_caption_hash TEXT,
            post_caption_preview TEXT,
            likes_count INTEGER,
            comments_count INTEGER,
            likers_processed INTEGER DEFAULT 0,
            interactions_made INTEGER DEFAULT 0,
            processed_at TEXT,
            UNIQUE(account_id, hashtag, post_author, post_caption_hash)
        )
    """)
    conn.commit()
    return ProcessedHashtagPostRepository(conn)


@pytest.mark.parametrize("written,looked_up", [
    ("paris", "paris"),
    ("Paris", "#paris"),
    ("#PARIS", "Paris"),
    ("#paris", "#Paris"),
])
def test_a_hashtag_is_found_however_it_was_typed(repo, written, looked_up):
    """Both sides fold the same way, or the memory never matches."""
    assert repo.record(account_id=1, hashtag=written, post_author="alice",
                       post_caption_hash="h1") is True
    assert repo.is_processed(1, looked_up, "alice", post_caption_hash="h1") is True


def test_an_unknown_post_is_not_processed(repo):
    assert repo.is_processed(1, "paris", "alice", post_caption_hash="h1") is False


def test_the_memory_is_per_account(repo):
    """Two accounts working the same hashtag must not skip each other's posts."""
    repo.record(account_id=1, hashtag="paris", post_author="alice", post_caption_hash="h1")
    assert repo.is_processed(2, "paris", "alice", post_caption_hash="h1") is False


def test_without_a_caption_hash_the_match_falls_back_to_author(repo):
    """The caption could not be read, so author + hashtag is all we have."""
    repo.record(account_id=1, hashtag="paris", post_author="alice", post_caption_hash="h1")
    assert repo.is_processed(1, "paris", "alice") is True
    assert repo.is_processed(1, "paris", "bob") is False


def test_the_window_forgets_old_posts(repo):
    """Outside the window a post becomes workable again — that is what the limit is for."""
    repo.record(account_id=1, hashtag="paris", post_author="alice", post_caption_hash="h1")
    repo.conn.execute(
        "UPDATE processed_hashtag_posts SET processed_at = datetime('now', '-10 days')"
    )
    repo.conn.commit()

    assert repo.is_processed(1, "paris", "alice", post_caption_hash="h1",
                             hours_limit=168) is False          # 7 days
    assert repo.is_processed(1, "paris", "alice", post_caption_hash="h1",
                             hours_limit=24 * 30) is True       # 30 days


def test_recording_the_same_post_twice_updates_it(repo):
    """INSERT OR REPLACE: a second pass refreshes the counters, it does not duplicate."""
    repo.record(account_id=1, hashtag="paris", post_author="alice",
                post_caption_hash="h1", likers_processed=3)
    repo.record(account_id=1, hashtag="paris", post_author="alice",
                post_caption_hash="h1", likers_processed=9, interactions_made=2)

    rows = repo.list_for_account(1)
    assert len(rows) == 1
    assert rows[0]["likers_processed"] == 9
    assert rows[0]["interactions_made"] == 2


def test_a_long_caption_preview_is_truncated(repo):
    """The preview is for display; the column is not meant to hold a whole caption."""
    repo.record(account_id=1, hashtag="paris", post_author="alice",
                post_caption_hash="h1", post_caption_preview="x" * 500)
    assert len(repo.list_for_account(1)[0]["post_caption_preview"]) == 100


def test_listing_can_be_narrowed_to_one_hashtag(repo):
    repo.record(account_id=1, hashtag="paris", post_author="alice", post_caption_hash="h1")
    repo.record(account_id=1, hashtag="lyon", post_author="bob", post_caption_hash="h2")

    assert len(repo.list_for_account(1)) == 2
    narrowed = repo.list_for_account(1, hashtag="#Paris")
    assert [r["post_author"] for r in narrowed] == ["alice"]


def test_a_broken_table_does_not_stop_the_run(repo):
    """A memory that cannot answer must report 'unseen', never raise into the workflow."""
    repo.conn.execute("DROP TABLE processed_hashtag_posts")
    repo.conn.commit()

    assert repo.is_processed(1, "paris", "alice") is False
    assert repo.record(account_id=1, hashtag="paris", post_author="alice") is False
    assert repo.list_for_account(1) == []


def test_normalize_hashtag_handles_nothing(repo):
    assert normalize_hashtag("") == ""
    assert normalize_hashtag(None) == ""
