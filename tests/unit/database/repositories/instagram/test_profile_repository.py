"""Unit tests for the Instagram profile repository."""

from taktik.core.database.repositories.instagram.profile.profile_repository import ProfileRepository


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


def test_get_known_usernames_returns_limited_set(conn):
    repo = ProfileRepository(conn)
    for username in ("a", "b", "c"):
        repo.get_or_create(username)

    assert repo.get_known_usernames(limit=2) <= {"a", "b", "c"}
    assert len(repo.get_known_usernames(limit=2)) == 2
    assert repo.get_known_usernames(days=7, limit=10) == {"a", "b", "c"}
