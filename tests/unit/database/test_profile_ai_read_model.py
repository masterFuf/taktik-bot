"""The AI read model must return real values on BOTH base shapes.

Regression cover for a silent failure that ran for months: the read model asked sqlite_master
for a *table* named `profile_ai_enrichments`. On a desktop base that name is a *view*, so the
guard answered no and every AI column resolved to a literal NULL. Nothing raised, no test
failed — 40k stored qualifications simply read back as "never classified" and every profile
was re-sent to the vision model on every pass.

The existing `test_profile_qualification_view` covers migrations and raw view reads; that is
what let the bug through. These tests exercise the READ MODEL itself, on both shapes.
"""
import sqlite3

import pytest

from taktik.core.database.profile_qualification import ProfileQualification
from taktik.core.database.repositories.instagram.profile_ai_read_model import (
    _exists,
    profile_ai_read_model,
)

_QUALIFICATION_DDL = """
    CREATE TABLE profile_qualification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL DEFAULT 'instagram',
        profile_id INTEGER,
        username TEXT NOT NULL,
        has_ai INTEGER NOT NULL DEFAULT 0,
        has_taxonomy INTEGER NOT NULL DEFAULT 0,
        ai_niche TEXT, ai_specific_niche TEXT, ai_profession TEXT, ai_profession_tags TEXT,
        location_city TEXT, analysis_json TEXT,
        UNIQUE(platform, username)
    )
"""

_ENRICHMENTS_DDL = """
    CREATE TABLE profile_ai_enrichments (
        enrichment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL DEFAULT 'instagram',
        profile_id INTEGER,
        username TEXT NOT NULL,
        ai_niche TEXT, ai_specific_niche TEXT, ai_profession TEXT, ai_profession_tags TEXT,
        location_city TEXT, analysis_json TEXT,
        updated_at TEXT
    )
"""


def _profiles(cur: sqlite3.Cursor) -> None:
    """`instagram_profiles` as the front leaves it: a view over `social_profiles`."""
    cur.execute(
        """
        CREATE TABLE social_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL, legacy_profile_id INTEGER, username TEXT NOT NULL,
            display_name TEXT, biography TEXT, is_business INTEGER DEFAULT 0,
            location_city TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE VIEW instagram_profiles AS SELECT
            legacy_profile_id AS profile_id, username, display_name AS full_name,
            biography, is_business, location_city
        FROM social_profiles WHERE platform = 'instagram'
        """
    )
    cur.executemany(
        "INSERT INTO social_profiles (platform, legacy_profile_id, username, display_name) "
        "VALUES ('instagram', ?, ?, ?)",
        [(10, "coach_marie", "Marie"), (11, "unknown_guy", "Guy")],
    )


def _read(conn: sqlite3.Connection, username: str) -> dict:
    """Run the read model exactly the way `find_profiles_with_latest_qualification` does."""
    ai = profile_ai_read_model(conn, "p")
    row = conn.execute(
        f"""
        SELECT p.username, p.full_name,
               {ai["niche"]} AS niche_category, {ai["sub_niche"]} AS niche,
               {ai["profession"]} AS profession, {ai["profession_tags"]} AS profession_tags,
               {ai["city"]} AS cities, {ai["analysis"]} AS analysis_json
        FROM instagram_profiles p
        {ai["join"]}
        WHERE p.username = ?
        """,
        (username,),
    ).fetchone()
    return dict(row) if row else {}


@pytest.fixture
def conn():
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    yield con
    con.close()


@pytest.fixture
def desktop(conn):
    """Desktop shape: `profile_qualification` is the table, the enrichment name is a VIEW."""
    cur = conn.cursor()
    _profiles(cur)
    cur.execute(_QUALIFICATION_DDL)
    cur.execute(
        "CREATE VIEW profile_ai_enrichments AS "
        "SELECT id AS enrichment_id, platform, profile_id, username, ai_niche, ai_specific_niche, "
        "ai_profession, ai_profession_tags, location_city, analysis_json "
        "FROM profile_qualification WHERE has_ai = 1"
    )
    conn.commit()
    return conn


@pytest.fixture
def standalone(conn):
    """Standalone shape: the open-source bot never unified, so the table is real."""
    cur = conn.cursor()
    _profiles(cur)
    cur.execute(_ENRICHMENTS_DDL)
    conn.commit()
    return conn


def test_a_view_counts_as_present(conn):
    """The exact rule the original bug broke: a store is readable whether it is a table OR a view.

    Reverting `_exists` to `type='table'` fails here. The read model itself is now immune by
    construction — its primary branch targets `profile_qualification`, which is a real table on
    a desktop base — but the rule is what protects every future reader of a compat view.
    """
    cur = conn.cursor()
    cur.execute("CREATE TABLE backing (id INTEGER PRIMARY KEY, ai_niche TEXT)")
    cur.execute("CREATE VIEW compat AS SELECT id, ai_niche FROM backing")
    conn.commit()

    assert _exists(conn, "backing") is True
    assert _exists(conn, "compat") is True, "a compat view is queryable — it is not 'absent'"
    assert _exists(conn, "nothing_here") is False


def test_desktop_shape_returns_the_stored_classification(desktop):
    """The bug: this used to come back all-NULL because the name is a view, not a table."""
    desktop.execute(
        "INSERT INTO profile_qualification "
        "(platform, profile_id, username, has_ai, ai_niche, ai_specific_niche, ai_profession) "
        "VALUES ('instagram', 10, 'coach_marie', 1, 'Beauty & Wellness', 'Naturopathy', 'Naturopath')"
    )
    desktop.commit()

    row = _read(desktop, "coach_marie")
    assert row["niche_category"] == "Beauty & Wellness"
    assert row["niche"] == "Naturopathy"
    assert row["profession"] == "Naturopath"
    assert ProfileQualification._is_classified(row) is True


def test_standalone_shape_still_reads_its_real_table(standalone):
    standalone.execute(
        "INSERT INTO profile_ai_enrichments "
        "(platform, profile_id, username, ai_niche, ai_specific_niche, updated_at) "
        "VALUES ('instagram', 10, 'coach_marie', 'fitness', 'Yoga', '2026-01-01 00:00:00')"
    )
    standalone.commit()

    row = _read(standalone, "coach_marie")
    assert row["niche_category"] == "fitness"
    assert row["niche"] == "Yoga"


def test_shape_with_neither_store_degrades_to_null_without_raising(conn):
    cur = conn.cursor()
    _profiles(cur)
    conn.commit()

    row = _read(conn, "coach_marie")
    assert row["niche_category"] is None
    assert ProfileQualification._is_classified(row) is False


def test_a_shared_profile_id_never_leaks_another_profile_niche(desktop):
    """636 profile_ids in production carry two rows for two unrelated usernames.

    Joining on profile_id would both duplicate the row and hand `unknown_guy`'s reader the
    niche stored for `coach_marie`. The join key is the table's own UNIQUE (platform, username).
    """
    desktop.executemany(
        "INSERT INTO profile_qualification "
        "(platform, profile_id, username, has_ai, ai_niche) VALUES ('instagram', ?, ?, 1, ?)",
        [(10, "coach_marie", "Beauty & Wellness"), (10, "unknown_guy", None)],
    )
    desktop.commit()

    ai = profile_ai_read_model(desktop, "p")
    rows = desktop.execute(
        f"SELECT p.username, {ai['niche']} AS niche_category "
        f"FROM instagram_profiles p {ai['join']} WHERE p.username = 'unknown_guy'"
    ).fetchall()

    assert len(rows) == 1, "a shared profile_id must not multiply the profile's row"
    assert rows[0]["niche_category"] is None


def test_has_ai_flag_alone_is_not_a_classification(desktop):
    """19 039 production rows carry has_ai=1 with every AI column still NULL."""
    desktop.execute(
        "INSERT INTO profile_qualification (platform, profile_id, username, has_ai) "
        "VALUES ('instagram', 10, 'coach_marie', 1)"
    )
    desktop.commit()

    assert ProfileQualification._is_classified(_read(desktop, "coach_marie")) is False


def test_decode_splits_content_tags_from_profession_tags():
    """`tags` used to be fed the PROFESSION tags, and `summary` fell back to a raw string."""
    decoded = ProfileQualification._decode({
        "username": "coach_marie",
        "profession_tags": '["naturopathy", "coaching"]',
        "analysis_json": '{"tags": ["wellness", "holistic"], "summary": "A naturopath.",'
                         ' "following_insights": [], "gender": "female"}',
    })

    assert decoded["profession_tags"] == ["naturopathy", "coaching"]
    assert decoded["tags"] == ["wellness", "holistic"]
    assert decoded["summary"] == "A naturopath."
    # The model returns [] when it had no following sample — the contract stays a string.
    assert decoded["following_insights"] == ""
    assert decoded["gender"] == "female"
    assert "analysis_json" not in decoded


def test_decode_survives_unusable_json():
    decoded = ProfileQualification._decode({
        "username": "coach_marie",
        "profession_tags": "not json",
        "analysis_json": "{truncated",
    })

    assert decoded["profession_tags"] == []
    assert decoded["tags"] == []
    assert decoded["summary"] == ""


def test_load_returns_none_when_nothing_is_classified(monkeypatch):
    class _Stub:
        @staticmethod
        def get_profiles_by_usernames(usernames):
            return [{"username": "coach_marie", "niche_category": None, "niche": None,
                     "profession": None}]

    monkeypatch.setattr(ProfileQualification, "_db", staticmethod(lambda: _Stub))
    assert ProfileQualification.load("coach_marie") is None


def test_load_is_case_insensitive_on_the_username(monkeypatch):
    class _Stub:
        @staticmethod
        def get_profiles_by_usernames(usernames):
            return [{"username": "Coach_Marie", "niche_category": "Beauty & Wellness",
                     "niche": "Naturopathy", "profession": None}]

    monkeypatch.setattr(ProfileQualification, "_db", staticmethod(lambda: _Stub))
    assert ProfileQualification.load("COACH_MARIE")["niche"] == "Naturopathy"


def test_load_never_raises_when_the_lookup_fails(monkeypatch):
    class _Stub:
        @staticmethod
        def get_profiles_by_usernames(usernames):
            raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(ProfileQualification, "_db", staticmethod(lambda: _Stub))
    assert ProfileQualification.load("coach_marie") is None


def test_unsupported_platform_answers_nothing_rather_than_guessing(monkeypatch):
    """TikTok has no reader yet; it must get an honest empty answer, not Instagram's rows."""
    class _Stub:
        @staticmethod
        def get_profiles_by_usernames(usernames):  # pragma: no cover - must not be called
            raise AssertionError("the Instagram store must not answer for another platform")

    monkeypatch.setattr(ProfileQualification, "_db", staticmethod(lambda: _Stub))
    assert ProfileQualification.load("coach_marie", platform="tiktok") is None
