"""The profile writers refuse a pseudo that cannot be a handle, before reading or writing anything.

A button label read as a pseudo became a profile ("Send message"), and every later write under the
same label updated that row with the data of whichever profile was on screen. Run against the
real schema on a temporary file; every pseudo here is invented.
"""

import pytest

from taktik.core.database.repositories._base.handle_guard import InvalidHandleError
from taktik.core.database.repositories.instagram.profile import ProfileRepository
from taktik.core.database.repositories.tiktok.tiktok_repository import TikTokRepository


def _profiles(conn, platform):
    return [row["username"] for row in conn.execute(
        "SELECT username FROM social_profiles WHERE platform = ? ORDER BY id", (platform,))]


@pytest.mark.parametrize("pseudo", [
    "Send message", "Envoyer un message", "lina.photo   ", "atelier_vend\x1c\x10e",
    "podcastetcritiquesdédiésauxcinémas", "",
])
def test_instagram_writer_refuses_a_non_handle(conn, pseudo):
    with pytest.raises(InvalidHandleError):
        ProfileRepository(conn).get_or_create(pseudo, full_name="Atelier Nord")

    assert _profiles(conn, "instagram") == []


def test_instagram_writer_still_files_a_handle(conn):
    profile_id, created = ProfileRepository(conn).get_or_create("lina.photo", full_name="Lina")

    assert created is True and profile_id is not None
    assert _profiles(conn, "instagram") == ["lina.photo"]


def test_a_label_stored_earlier_is_not_updated_through_the_writer(conn):
    conn.execute(
        "INSERT INTO social_profiles (platform, legacy_profile_id, username, display_name) "
        "VALUES ('instagram', 1, 'Send message', 'Atelier Nord')"
    )
    conn.commit()

    with pytest.raises(InvalidHandleError):
        ProfileRepository(conn).get_or_create("Send message", full_name="Boulangerie Sud")

    row = conn.execute("SELECT display_name FROM social_profiles WHERE username = 'Send message'").fetchone()
    assert row["display_name"] == "Atelier Nord"


def test_tiktok_writer_refuses_a_display_name(conn):
    repo = TikTokRepository(conn)

    with pytest.raises(InvalidHandleError):
        repo.get_or_create_profile("‍إستي ✰", followers_count=588)
    with pytest.raises(InvalidHandleError):
        repo.save_scraped_profile(1, {"username": "Lina B", "display_name": "Lina B"})

    assert _profiles(conn, "tiktok") == []
    assert repo.get_or_create_profile(".lina.b")[1] is True


def test_an_interaction_under_a_label_is_not_recorded(db):
    account_id, _ = db.get_or_create_account("operator.account")

    assert db.record_interaction(account_id, "Envoyer un message", "LIKE") is False
    assert db.record_filtered_profile(account_id, "Send message", "private", "target", "x") is False

    conn = db._get_connection()
    assert _profiles(conn, "instagram") == []
    assert conn.execute("SELECT COUNT(*) FROM interactions").fetchone()[0] == 0
