"""Unit tests for sent DM duplicate-prevention repository."""

from taktik.core.database.repositories.messaging import SentDMRepository


def test_recorded_dm_is_detected_per_platform(conn):
    repo = SentDMRepository(conn)

    assert repo.check_already_sent(1, "TargetUser", platform="instagram") is False

    repo.record(
        account_id=1,
        recipient="TargetUser",
        message="hello",
        success=True,
        platform="instagram",
    )

    assert repo.check_already_sent(1, "targetuser", platform="instagram") is True
    assert repo.check_already_sent(1, "targetuser", platform="tiktok") is False


def test_record_updates_existing_dm_marker(conn):
    repo = SentDMRepository(conn)

    repo.record(1, "targetuser", "first", True, platform="instagram")
    repo.record(1, "targetuser", "second", False, error_message="blocked", platform="instagram")

    rows = repo.query("SELECT * FROM sent_dms")

    assert len(rows) == 1
    assert rows[0]["success"] == 0
    assert rows[0]["error_message"] == "blocked"
