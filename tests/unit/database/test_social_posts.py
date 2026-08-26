"""The post catalogue: one row per post, whatever copy of its link we were handed.

A `post_url` workflow can only deep-link to a shareable URL, and Instagram's share sheet
stamps every copy of that URL with a per-copy `?igsh=` token. Keyed raw, the same post
would be catalogued once per copy; the repository therefore normalises before writing.
Counters are a snapshot (a re-scrape overwrites them), and a read that failed (None)
never erases a value we already measured.
"""

import sqlite3

import pytest

from taktik.core.database.instagram_post_identity import (
    build_post_ref,
    canonical_post_url,
    post_shortcode_from_url,
    post_type_from_url,
)
from taktik.core.database.local.schema import create_schema
from taktik.core.database.repositories.instagram import SocialPostRepository

SHARE_LINK = "https://www.instagram.com/p/DAbC123xyz/?igsh=MWQ1ZmE0NzE2Zg=="
SAME_POST_OTHER_COPY = "https://www.instagram.com/p/DAbC123xyz/?igsh=b3RoZXJ0b2tlbg=="
CAPTION = "Nouvelle collection printemps disponible en boutique"


@pytest.fixture
def repo():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    return SocialPostRepository(conn)


# ── URL identity ─────────────────────────────────────────────────────────────

def test_canonical_url_drops_the_per_copy_share_token():
    assert canonical_post_url(SHARE_LINK) == "https://www.instagram.com/p/DAbC123xyz/"
    assert canonical_post_url(SHARE_LINK) == canonical_post_url(SAME_POST_OTHER_COPY)


def test_canonical_url_accepts_every_shape_the_app_hands_out():
    assert canonical_post_url("instagram.com/reel/XyZ/") == "https://www.instagram.com/reel/XyZ/"
    assert canonical_post_url("https://www.instagram.com/reels/XyZ") == "https://www.instagram.com/reel/XyZ/"
    assert canonical_post_url("https://www.instagram.com/alice/p/XyZ/#c") == "https://www.instagram.com/p/XyZ/"
    assert canonical_post_url("https://www.instagram.com/tv/XyZ/") == "https://www.instagram.com/p/XyZ/"


def test_a_url_without_a_shortcode_has_no_identity():
    assert canonical_post_url("https://www.instagram.com/alice/") is None
    assert canonical_post_url("") is None
    assert canonical_post_url(None) is None
    assert post_shortcode_from_url("https://www.instagram.com/alice/") is None


def test_shortcode_and_type_are_read_from_the_url():
    assert post_shortcode_from_url(SHARE_LINK) == "DAbC123xyz"
    assert post_type_from_url(SHARE_LINK) == "post"
    assert post_type_from_url("https://www.instagram.com/reel/XyZ/") == "reel"


# ── Writing ──────────────────────────────────────────────────────────────────

def test_schema_keys_a_post_on_its_canonical_url_per_platform():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(social_posts)")}
    assert {"post_url", "author_username", "post_ref", "likes_count", "comments_count",
            "first_seen_at", "last_scraped_at", "sync_id"} <= cols
    conn.execute("INSERT INTO social_posts (platform, post_url, author_username) VALUES ('instagram', 'u', 'a')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO social_posts (platform, post_url, author_username) VALUES ('instagram', 'u', 'b')")


def test_two_copies_of_the_same_link_are_one_row(repo):
    repo.record(post_url=SHARE_LINK, author_username="@Alice", likes_count=120, comments_count=9)
    repo.record(post_url=SAME_POST_OTHER_COPY, author_username="alice", likes_count=131, comments_count=11)

    assert repo.query("SELECT COUNT(*) AS n FROM social_posts")[0]["n"] == 1
    row = repo.find_by_url(SAME_POST_OTHER_COPY)
    assert row["post_url"] == "https://www.instagram.com/p/DAbC123xyz/"
    assert row["shortcode"] == "DAbC123xyz"
    assert row["post_type"] == "post"
    assert row["author_username"] == "alice"
    assert (row["likes_count"], row["comments_count"]) == (131, 11)


def test_a_failed_counter_read_never_erases_a_measured_one(repo):
    repo.record(post_url=SHARE_LINK, author_username="alice", likes_count=120, comments_count=9)
    repo.record(post_url=SHARE_LINK, author_username="alice", likes_count=None, comments_count=None)

    row = repo.find_by_url(SHARE_LINK)
    assert (row["likes_count"], row["comments_count"]) == (120, 9)


def test_first_seen_survives_a_refresh_while_last_scraped_moves(repo):
    repo.record(post_url=SHARE_LINK, author_username="alice", likes_count=1)
    repo.execute("UPDATE social_posts SET first_seen_at = '2026-01-01 00:00:00', last_scraped_at = '2026-01-01 00:00:00'")
    repo.record(post_url=SHARE_LINK, author_username="alice", likes_count=2)

    row = repo.find_by_url(SHARE_LINK)
    assert row["first_seen_at"] == "2026-01-01 00:00:00"
    assert row["last_scraped_at"] != "2026-01-01 00:00:00"
    assert row["updated_at"] == row["last_scraped_at"]


def test_an_unusable_url_or_author_is_refused_not_stored(repo):
    assert repo.record(post_url="https://www.instagram.com/alice/", author_username="alice") is None
    assert repo.record(post_url=SHARE_LINK, author_username="") is None
    assert repo.query("SELECT COUNT(*) AS n FROM social_posts")[0]["n"] == 0


def test_caption_is_stored_as_a_bounded_preview(repo):
    repo.record(post_url=SHARE_LINK, author_username="alice", caption_preview="x" * 1000)
    assert len(repo.find_by_url(SHARE_LINK)["caption_preview"]) == 300


# ── Recognising a post before paying for its URL ─────────────────────────────

def test_a_known_post_is_found_by_its_author_caption_identity(repo):
    ref = build_post_ref("alice", CAPTION)
    repo.record(post_url=SHARE_LINK, author_username="alice", post_ref=ref, likes_count=10, comments_count=1)

    assert repo.find_by_ref(ref)["post_url"] == "https://www.instagram.com/p/DAbC123xyz/"
    assert repo.find_by_ref(build_post_ref("alice", "another caption entirely")) is None


def test_counters_of_a_recognised_post_refresh_without_its_url(repo):
    ref = build_post_ref("alice", CAPTION)
    repo.record(post_url=SHARE_LINK, author_username="alice", post_ref=ref, likes_count=10, comments_count=1)

    assert repo.refresh_counts_by_ref(ref, likes_count=42, comments_count=None) is True
    row = repo.find_by_url(SHARE_LINK)
    assert (row["likes_count"], row["comments_count"]) == (42, 1)
    assert repo.refresh_counts_by_ref("nobody:000000000000", 1, 1) is False


# ── Reading the catalogue ────────────────────────────────────────────────────

def _seed(repo):
    repo.record(post_url="https://www.instagram.com/p/A/", author_username="alice", likes_count=300, comments_count=4)
    repo.record(post_url="https://www.instagram.com/reel/B/", author_username="alice", likes_count=50, comments_count=40)
    repo.record(post_url="https://www.instagram.com/p/C/", author_username="bob", likes_count=900, comments_count=0)


def test_an_authors_posts_come_biggest_first(repo):
    _seed(repo)
    urls = [r["post_url"] for r in repo.list_for_author("@Alice")]
    assert urls == ["https://www.instagram.com/p/A/", "https://www.instagram.com/reel/B/"]
    assert repo.count_for_author("alice") == 2
    assert repo.list_for_author("") == []


def test_top_posts_filters_on_counters_and_orders_by_the_asked_one(repo):
    _seed(repo)
    assert [r["shortcode"] for r in repo.top_posts(min_likes=100)] == ["C", "A"]
    assert [r["shortcode"] for r in repo.top_posts(order_by="comments_count")] == ["B", "A", "C"]
    assert [r["shortcode"] for r in repo.top_posts(author_username="alice", min_comments=10)] == ["B"]


def test_top_posts_only_sorts_by_catalogue_columns(repo):
    with pytest.raises(ValueError):
        repo.top_posts(order_by="1; DROP TABLE social_posts")
