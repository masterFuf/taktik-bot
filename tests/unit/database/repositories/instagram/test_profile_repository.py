"""Unit tests for the Instagram profile repository."""

import pytest

from taktik.core.database.repositories.instagram.profile.profile_repository import (
    MARK_UNREACHABLE_SQL,
    ProfileRepository,
)


def test_record_stats_history_persists_enriched_profile_snapshot(conn):
    repo = ProfileRepository(conn)
    profile_id, _ = repo.get_or_create(
        "creator",
        followers_count=1000,
        following_count=42,
        posts_count=12,
    )

    assert repo.record_stats_history(
        profile_id,
        {
            "followers_count": 1000,
            "following_count": 42,
            "posts_count": 12,
            "is_verified": True,
            "external_url": "https://example.com",
            "profile_pic_url": "https://example.com/avatar.jpg",
        },
    ) is True

    row = conn.execute(
        "SELECT * FROM profile_stats_history WHERE profile_id = ?",
        (profile_id,),
    ).fetchone()
    assert row["followers_count"] == 1000
    assert row["is_verified"] == 1
    assert row["external_url"] == "https://example.com"


def test_profile_existence_helpers_support_creation_window(conn):
    repo = ProfileRepository(conn)
    repo.get_or_create("known")

    assert repo.exists_by_username("known") is True
    assert repo.exists_by_username("known", days=7) is True
    assert repo.exists_by_username("missing") is False
    assert repo.is_recently_scraped("known", days=7) is True
    assert repo.is_recently_scraped("missing", days=7) is False


def test_a_row_holding_a_handle_or_a_name_was_not_visited(conn):
    repo = ProfileRepository(conn)
    repo.get_or_create("author_of_a_liked_post")
    repo.get_or_create("name_from_a_list", full_name="A name")

    assert repo.exists_by_username("author_of_a_liked_post") is True
    assert repo.was_visited("author_of_a_liked_post") is False
    assert repo.was_visited("name_from_a_list") is False
    assert repo.was_visited("missing") is False


@pytest.mark.parametrize("column, value", [
    ("followers_count", 1),
    ("following_count", 1),
    ("posts_count", 1),
    ("likes_count", 1),
    ("biography", "A bio"),
    ("profile_pic_path", "pictures/a.jpg"),
])
def test_what_only_the_page_gives_makes_a_profile_visited(conn, column, value):
    repo = ProfileRepository(conn)
    repo.get_or_create("read")
    conn.execute(f"UPDATE social_profiles SET {column} = ? WHERE username = 'read'", (value,))

    assert repo.was_visited("read") is True


@pytest.mark.parametrize("column, value", [
    ("followers_count", 0),
    ("following_count", 0),
    ("posts_count", 0),
    ("likes_count", 0),
    ("biography", ""),
    ("profile_pic_path", ""),
])
def test_an_empty_value_is_no_visit(conn, column, value):
    repo = ProfileRepository(conn)
    repo.get_or_create("empty")
    conn.execute(f"UPDATE social_profiles SET {column} = ? WHERE username = 'empty'", (value,))

    assert repo.was_visited("empty") is False


def test_a_page_that_could_not_be_opened_counts_as_visited(conn):
    repo = ProfileRepository(conn)
    repo.get_or_create("gone")
    conn.execute(MARK_UNREACHABLE_SQL, ("instagram", "gone"))

    assert repo.was_visited("gone") is True


def test_a_visit_keeps_the_creation_window_of_the_existence_check(conn):
    repo = ProfileRepository(conn)
    repo.get_or_create("read", followers_count=10)
    assert repo.was_visited("read", days=7) is True

    conn.execute("UPDATE social_profiles SET created_at = datetime('now', '-30 days') WHERE username = 'read'")

    assert repo.was_visited("read", days=7) is False
    assert repo.was_visited("read") is True


def test_get_known_usernames_returns_limited_set(conn):
    repo = ProfileRepository(conn)
    for username in ("a", "b", "c"):
        repo.get_or_create(username)

    assert repo.get_known_usernames(limit=2) <= {"a", "b", "c"}
    assert len(repo.get_known_usernames(limit=2)) == 2
    assert repo.get_known_usernames(days=7, limit=10) == {"a", "b", "c"}


def test_profile_ai_enrichment_ignores_legacy_profile_fields(conn):
    repo = ProfileRepository(conn)
    profile_id, _ = repo.get_or_create(
        "enriched_creator",
        full_name="Legacy Name",
        biography="Bio",
    )

    # Vague B: instagram_profiles is now a compat VIEW over social_profiles and the
    # legacy ai_* classification columns no longer exist (they read NULL), so the
    # "ignore legacy ai_* fields" behaviour is now structural. We only seed
    # location_city (a real column, written via social_profiles) to verify the
    # enrichment overlay vs the profile fallback.
    conn.execute(
        "UPDATE social_profiles SET location_city = 'Legacy City' "
        "WHERE platform = 'instagram' AND legacy_profile_id = ?",
        (profile_id,),
    )
    legacy_only_profile_id, _ = repo.get_or_create(
        "legacy_only_creator",
        full_name="Legacy Only",
        biography="Bio",
    )
    conn.execute(
        "UPDATE social_profiles SET location_city = 'Legacy Only City' "
        "WHERE platform = 'instagram' AND legacy_profile_id = ?",
        (legacy_only_profile_id,),
    )
    conn.execute(
        """
        INSERT INTO profile_ai_enrichments (
            platform, profile_id, username, provider, model, criteria_hash,
            ai_niche, ai_specific_niche, ai_profession, ai_profession_tags,
            location_city, source, updated_at
        ) VALUES (
            'instagram', ?, 'enriched_creator', 'test', 'test-model', 'criteria',
            'enriched_niche', 'enriched_sub', 'enriched_profession',
            '["enriched"]', 'Enriched City', 'test', '2026-06-06T12:00:00'
        )
        """,
        (profile_id,),
    )
    conn.commit()

    rows = {
        row["username"]: row
        for row in repo.find_profiles_with_latest_qualification([
            "enriched_creator",
            "legacy_only_creator",
        ])
    }

    assert rows["enriched_creator"]["niche_category"] == "enriched_niche"
    assert rows["enriched_creator"]["niche"] == "enriched_sub"
    assert rows["enriched_creator"]["profession"] == "enriched_profession"
    assert rows["enriched_creator"]["profession_tags"] == '["enriched"]'
    assert rows["enriched_creator"]["cities"] == "Enriched City"

    assert rows["legacy_only_creator"]["niche_category"] is None
    assert rows["legacy_only_creator"]["niche"] is None
    assert rows["legacy_only_creator"]["profession"] is None
    assert rows["legacy_only_creator"]["profession_tags"] is None
    assert rows["legacy_only_creator"]["cities"] == "Legacy Only City"


def test_a_kept_picture_is_one_with_a_path(conn):
    """`has_picture`: what keeps a list row's picture from replacing one already kept."""
    repo = ProfileRepository(conn)
    repo.get_or_create("pictured")
    repo.get_or_create("bare")
    repo.get_or_create("emptied")
    conn.execute("UPDATE social_profiles SET profile_pic_path = 'pictures/a.jpg' WHERE username = 'pictured'")
    conn.execute("UPDATE social_profiles SET profile_pic_path = '' WHERE username = 'emptied'")

    assert (repo.has_picture("pictured"), repo.has_picture("bare"), repo.has_picture("emptied"),
            repo.has_picture("missing")) == (True, False, False, False)
