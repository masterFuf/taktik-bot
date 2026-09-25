"""Profiles stored under a pseudo that is no handle are MARKED unreachable, never deleted.

The forms are the ones found in a real base (a button label, a handle followed by spaces, control
characters, a biography squeezed into one word, a TikTok display name). Run against the real
schema on a temporary file; every pseudo here is invented.
"""

import pytest

from taktik.core.database.repositories.social_profiles import InvalidHandleRepository

INSTAGRAM_PHANTOMS = (
    "Send message",
    "lina.photo      ",
    "atelier_vend\x1c\x10e",
    "podcastetcritiquesdédiésauxcinémasdisponiblesurtouteslesplateformes",
)
TIKTOK_PHANTOM = "‍إستي ✰"
HANDLES = (("instagram", "lina.photo"), ("instagram", "x" * 30), ("instagram", "Atelier_Nord"),
           ("tiktok", ".lina.b"), ("tiktok", "axel...moi"))


def _stored(conn, platform, username, legacy_id):
    conn.execute(
        "INSERT INTO social_profiles (platform, legacy_profile_id, username, updated_at) "
        "VALUES (?, ?, ?, '2026-01-01 00:00:00')",
        (platform, legacy_id, username),
    )


@pytest.fixture
def base(conn):
    legacy_id = 0
    for username in INSTAGRAM_PHANTOMS:
        legacy_id += 1
        _stored(conn, "instagram", username, legacy_id)
    _stored(conn, "tiktok", TIKTOK_PHANTOM, 1)
    for platform, username in HANDLES:
        legacy_id += 1
        _stored(conn, platform, username, legacy_id)
    # Created by the desktop app; the bot schema has none.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS profile_qualification (id INTEGER PRIMARY KEY, platform TEXT, "
        "profile_id INTEGER, username TEXT, ai_classification TEXT)"
    )
    conn.execute(
        "INSERT INTO profile_qualification (platform, profile_id, username, ai_classification) "
        "VALUES ('instagram', 1, 'Send message', 'a restaurant')"
    )
    conn.execute(
        "INSERT INTO scraped_profiles (platform, scraping_id, profile_id) VALUES ('tiktok', 79, 1)"
    )
    conn.commit()
    return conn


def _row(conn, platform, username):
    return conn.execute(
        "SELECT unreachable_at, unreachable_count, updated_at FROM social_profiles "
        "WHERE platform = ? AND username = ?",
        (platform, username),
    ).fetchone()


def test_the_plan_finds_every_form_and_writes_nothing(base):
    plan = InvalidHandleRepository(base).plan()

    found = [(profile.platform, profile.stored) for profile in plan.profiles]
    assert found == [("instagram", u) for u in INSTAGRAM_PHANTOMS] + [("tiktok", TIKTOK_PHANTOM)]
    assert plan.has_work is True
    assert all(_row(base, p, u)["unreachable_at"] is None for p, u in found)


def test_what_points_at_a_phantom_is_counted(base):
    by_name = {profile.stored: dict(profile.references)
               for profile in InvalidHandleRepository(base).plan().profiles}

    assert by_name["Send message"] == {
        "profile_qualification.profile_id": 1,
        "profile_qualification.username": 1,
    }
    assert by_name[TIKTOK_PHANTOM] == {"scraped_profiles.profile_id": 1}
    assert by_name["lina.photo      "] == {}


def test_apply_marks_the_phantoms_and_keeps_every_row(base):
    done = InvalidHandleRepository(base).apply()

    assert len(done.to_mark) == 5
    for profile in done.profiles:
        row = _row(base, profile.platform, profile.stored)
        assert row is not None, "a phantom is marked, never deleted"
        assert row["unreachable_at"] is not None
        assert row["unreachable_count"] == 1
        assert row["updated_at"] > "2026-01-01 00:00:00", "the mark must travel through the sync"
    for platform, username in HANDLES:
        assert _row(base, platform, username)["unreachable_at"] is None
    assert base.execute("SELECT COUNT(*) FROM profile_qualification").fetchone()[0] == 1
    assert base.execute("SELECT COUNT(*) FROM scraped_profiles").fetchone()[0] == 1


def test_a_second_run_changes_nothing(base):
    repo = InvalidHandleRepository(base)
    repo.apply()

    assert repo.plan().has_work is False
    repo.apply()
    assert _row(base, "instagram", "Send message")["unreachable_count"] == 1


def test_a_failure_midway_leaves_the_base_as_it_was(base, monkeypatch):
    repo = InvalidHandleRepository(base)
    real_plan = repo.plan

    def plan_then_fail():
        plan = real_plan()
        base.execute(
            "UPDATE social_profiles SET unreachable_at = datetime('now') WHERE username = 'Send message'"
        )
        raise RuntimeError("disk full")

    monkeypatch.setattr(repo, "plan", plan_then_fail)
    with pytest.raises(RuntimeError):
        repo.apply()

    assert _row(base, "instagram", "Send message")["unreachable_at"] is None
    assert base.in_transaction is False


def test_nothing_stored_under_a_non_handle_means_no_work(conn):
    _stored(conn, "instagram", "lina.photo", 1)
    conn.commit()

    assert InvalidHandleRepository(conn).plan().has_work is False
