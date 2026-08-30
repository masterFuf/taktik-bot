"""Collected posts: one row per post, whatever copy of its link we were handed.

A `post_url` workflow can only navigate to a shareable URL, and Instagram's share sheet
stamps every copy of that URL with a per-copy `?igsh=` token. Keyed raw, the same post
would be stored once per copy; the repository therefore normalises before writing.
Counters are a snapshot (a re-scan overwrites them), and a read that failed (None) never
erases a value we already measured.
"""

import sqlite3

import pytest

from taktik.core.database.instagram_post_identity import (
    canonical_post_url,
    post_shortcode_from_url,
)
from taktik.core.database.local.schema import create_schema
from taktik.core.database.local.migrations import run_migrations
from taktik.core.database.repositories.instagram import SocialPostRepository

SHARE_LINK = "https://www.instagram.com/p/DAbC123xyz/?igsh=MWQ1ZmE0NzE2Zg=="
SAME_POST_OTHER_COPY = "https://www.instagram.com/p/DAbC123xyz/?igsh=b3RoZXJ0b2tlbg=="


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
    assert post_shortcode_from_url(SHARE_LINK) == "DAbC123xyz"


# ── The table ────────────────────────────────────────────────────────────────

def test_the_table_holds_only_what_the_collector_writes():
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(social_posts)")}
    assert cols == {
        "id", "platform", "post_key", "post_url", "author_username", "likes_count",
        "comments_count", "first_seen_at", "last_scraped_at", "sync_id",
    }


def test_the_identity_is_unique_per_platform_and_the_url_is_not():
    """La clé a quitté l'URL le 2026-08-30. Sur Instagram les deux disent la même chose — l'URL
    normalisée EST l'identité — mais TikTok fabrique un lien court différent à chaque copie, donc
    une vidéo serait stockée une fois par visite si l'URL faisait foi."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute("INSERT INTO social_posts (platform, post_key, post_url, author_username) "
                 "VALUES ('instagram', 'k', 'u', 'a')")

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO social_posts (platform, post_key, post_url, author_username) "
                     "VALUES ('instagram', 'k', 'autre-url', 'b')")

    # Deux liens différents pour la MÊME identité : c'est le cas TikTok, et il doit passer.
    conn.execute("INSERT INTO social_posts (platform, post_key, post_url, author_username) "
                 "VALUES ('tiktok', 'tiktok:keo:0612:abc', 'https://vm.tiktok.com/AAA/', 'keo')")
    conn.execute("UPDATE social_posts SET post_url = 'https://vm.tiktok.com/BBB/' "
                 "WHERE platform = 'tiktok'")
    assert conn.execute("SELECT COUNT(*) FROM social_posts WHERE platform='tiktok'").fetchone()[0] == 1


def test_an_empty_legacy_table_is_rebuilt_without_the_cut_columns():
    """The table shipped briefly with seven columns built for a scheme that was cut."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute("DROP TABLE social_posts")
    conn.execute("""
        CREATE TABLE social_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, platform TEXT, post_url TEXT,
            shortcode TEXT, post_type TEXT, author_username TEXT, post_ref TEXT,
            caption_preview TEXT, likes_count INTEGER, comments_count INTEGER,
            posted_at_label TEXT, grid_position INTEGER, scraping_id INTEGER,
            first_seen_at TEXT, last_scraped_at TEXT, updated_at TEXT, sync_id TEXT
        )
    """)

    run_migrations(conn)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(social_posts)")}
    assert "post_ref" not in cols and "grid_position" not in cols
    assert "post_url" in cols and "likes_count" in cols


def test_a_populated_legacy_table_is_left_alone():
    """A migration must stay safe on a populated base: dropping would take real rows."""
    conn = sqlite3.connect(":memory:")
    create_schema(conn)
    conn.execute("DROP TABLE social_posts")
    conn.execute("CREATE TABLE social_posts (id INTEGER PRIMARY KEY, post_ref TEXT, post_url TEXT)")
    conn.execute("INSERT INTO social_posts (post_ref, post_url) VALUES ('a:b', 'u')")

    run_migrations(conn)

    assert conn.execute("SELECT COUNT(*) FROM social_posts").fetchone()[0] == 1


# ── Writing ──────────────────────────────────────────────────────────────────

def test_two_copies_of_the_same_link_are_one_row(repo):
    repo.record(post_url=SHARE_LINK, author_username="@Alice", likes_count=120, comments_count=9)
    repo.record(post_url=SAME_POST_OTHER_COPY, author_username="alice", likes_count=131, comments_count=11)

    assert repo.query("SELECT COUNT(*) AS n FROM social_posts")[0]["n"] == 1
    row = repo.find_by_url(SAME_POST_OTHER_COPY)
    assert row["post_url"] == "https://www.instagram.com/p/DAbC123xyz/"
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


def test_an_unusable_url_or_author_is_refused_not_stored(repo):
    assert repo.record(post_url="https://www.instagram.com/alice/", author_username="alice") is None
    assert repo.record(post_url=SHARE_LINK, author_username="") is None
    assert repo.query("SELECT COUNT(*) AS n FROM social_posts")[0]["n"] == 0


# ── Reading ──────────────────────────────────────────────────────────────────

def test_an_accounts_posts_come_biggest_first(repo):
    repo.record(post_url="https://www.instagram.com/p/A/", author_username="alice", likes_count=300)
    repo.record(post_url="https://www.instagram.com/reel/B/", author_username="alice", likes_count=50)
    repo.record(post_url="https://www.instagram.com/p/C/", author_username="bob", likes_count=900)

    urls = [r["post_url"] for r in repo.list_for_author("@Alice")]
    assert urls == ["https://www.instagram.com/p/A/", "https://www.instagram.com/reel/B/"]
    assert repo.count_for_author("alice") == 2
    assert repo.list_for_author("") == []

def test_a_tiktok_post_keeps_one_row_across_four_different_links(repo):
    """Le cas mesuré : quatre copies du lien d'une même vidéo rendent quatre URLs. Sans identité
    séparée, la vidéo serait stockée quatre fois et aucune relecture ne retrouverait la ligne."""
    from taktik.core.database.tiktok_post_identity import tiktok_post_key

    key = tiktok_post_key("Kéo", "· 06-12", "Le secret de ma réussite en bio")
    for short in ("ZN8FUVpSM", "ZN8FUWHSs", "ZN8FUcEWh", "ZN8FUtvAr"):
        repo.record(
            post_url=f"https://vm.tiktok.com/{short}/",
            author_username="keo2edit",
            likes_count=10,
            platform="tiktok",
            post_key=key,
        )

    assert repo.query("SELECT COUNT(*) AS n FROM social_posts")[0]["n"] == 1
    row = repo.find_by_key(key, platform="tiktok")
    assert row is not None
    # L'URL retenue est la DERNIÈRE vue : sur TikTok la copie la plus récente est celle qui a le
    # plus de chances de résoudre encore.
    assert row["post_url"].endswith("ZN8FUtvAr/")


def test_instagram_still_keys_on_its_normalised_url(repo):
    """Rien ne change pour la plateforme dont l'URL EST l'identité : le paramètre est optionnel
    et retombe sur l'URL normalisée."""
    repo.record(post_url=SHARE_LINK, author_username="alice", likes_count=1)
    repo.record(post_url=SAME_POST_OTHER_COPY, author_username="alice", likes_count=2)

    assert repo.query("SELECT COUNT(*) AS n FROM social_posts")[0]["n"] == 1
    row = repo.find_by_key("https://www.instagram.com/p/DAbC123xyz/")
    assert row is not None and row["likes_count"] == 2
