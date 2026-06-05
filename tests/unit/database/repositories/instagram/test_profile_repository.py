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


def test_profile_ai_enrichment_ignores_legacy_profile_fields(conn):
    repo = ProfileRepository(conn)
    profile_id, _ = repo.get_or_create(
        "enriched_creator",
        full_name="Legacy Name",
        biography="Bio",
    )

    for column, definition in (
        ("ai_niche", "TEXT"),
        ("ai_specific_niche", "TEXT"),
        ("ai_profession", "TEXT"),
        ("ai_profession_tags", "TEXT"),
    ):
        conn.execute(f"ALTER TABLE instagram_profiles ADD COLUMN {column} {definition}")

    conn.execute(
        """
        UPDATE instagram_profiles
        SET ai_niche = 'legacy_niche',
            ai_specific_niche = 'legacy_sub',
            ai_profession = 'legacy_profession',
            ai_profession_tags = '["legacy"]',
            location_city = 'Legacy City'
        WHERE profile_id = ?
        """,
        (profile_id,),
    )
    legacy_only_profile_id, _ = repo.get_or_create(
        "legacy_only_creator",
        full_name="Legacy Only",
        biography="Bio",
    )
    conn.execute(
        """
        UPDATE instagram_profiles
        SET ai_niche = 'legacy_only_niche',
            ai_specific_niche = 'legacy_only_sub',
            ai_profession = 'legacy_only_profession',
            ai_profession_tags = '["legacy_only"]',
            location_city = 'Legacy Only City'
        WHERE profile_id = ?
        """,
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
