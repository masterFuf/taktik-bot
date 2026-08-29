"""A TikTok handle must never be answered with an Instagram namesake's niche.

The facade's Instagram query reads `FROM instagram_profiles` and joins `scraped_profiles WHERE
platform = 'instagram'`: it is Instagram-only by construction. Adding "tiktok" to the supported
tuple without giving it its own reader would have served one platform's classification for the
other's profile -- the exact confusion the module header warns about, and the reason this test
uses the SAME username on both platforms.
"""

import sqlite3

import pytest

from taktik.core.database.profile_qualification import ProfileQualification, SUPPORTED_PLATFORMS


SHARED_HANDLE = "marie.dupont"


@pytest.fixture
def qualification_db(tmp_path, monkeypatch):
    """A store holding the same username on both platforms, with different niches."""
    path = tmp_path / "qualification.db"
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE profile_qualification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'instagram',
            username TEXT NOT NULL,
            ai_niche TEXT,
            ai_specific_niche TEXT,
            ai_profession TEXT,
            ai_profession_tags TEXT,
            location_city TEXT,
            analysis_json TEXT
        )
        """
    )
    connection.executemany(
        "INSERT INTO profile_qualification "
        "(platform, username, ai_niche, ai_specific_niche, ai_profession) VALUES (?, ?, ?, ?, ?)",
        [
            ("instagram", SHARED_HANDLE, "Mode", "streetwear", "styliste"),
            ("tiktok", SHARED_HANDLE, "Cuisine", "patisserie", "chef"),
        ],
    )
    connection.commit()
    connection.close()

    class _Profiles:
        def query(self, sql, params=()):
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            try:
                return [dict(row) for row in conn.execute(sql, params)]
            finally:
                conn.close()

    class _Db:
        profiles = _Profiles()

    monkeypatch.setattr(
        "taktik.core.database.local.service.get_local_database", lambda: _Db(), raising=False
    )
    return path


def test_tiktok_is_a_supported_platform_now():
    assert "tiktok" in SUPPORTED_PLATFORMS


def test_a_tiktok_handle_gets_the_tiktok_niche(qualification_db):
    found = ProfileQualification.load_many([SHARED_HANDLE], "tiktok")
    assert found[SHARED_HANDLE]["niche_category"] == "Cuisine"
    assert found[SHARED_HANDLE]["niche"] == "patisserie"


def test_the_instagram_row_is_not_served_to_tiktok(qualification_db):
    """The whole point: the namesake's Mode/streetwear must not travel across platforms."""
    found = ProfileQualification.load_many([SHARED_HANDLE], "tiktok")
    assert found[SHARED_HANDLE]["niche_category"] != "Mode"


def test_the_lookup_is_case_insensitive(qualification_db):
    assert ProfileQualification.load_many([SHARED_HANDLE.upper()], "tiktok")


def test_an_unknown_platform_answers_nothing(qualification_db):
    assert ProfileQualification.load_many([SHARED_HANDLE], "threads") == {}


def test_a_profile_with_no_classification_is_not_reported_as_known(qualification_db):
    """`has_ai` is not the answer: a row must carry a real value to count as classified."""
    connection = sqlite3.connect(qualification_db)
    connection.execute(
        "INSERT INTO profile_qualification (platform, username) VALUES ('tiktok', 'vide.total')"
    )
    connection.commit()
    connection.close()
    assert "vide.total" not in ProfileQualification.load_many(["vide.total"], "tiktok")
