"""The two gestures of the TikTok notifications pass are filed like every other follow and DM.

A suggested follow is a FOLLOW interaction: it counts in the day's `total_follows` (the figure the
daily follow quota reads) and the unfollow sees it as the bot's. A wave is a `sent_dms` marker:
the welcome DM and the cold DM then know this person was already written to. Real schema,
temporary base.
"""

import pytest

import taktik.core.database.tiktok_follow_graph as graph_module
from taktik.core.database.messaging import SentDMService
from taktik.core.database.tiktok_dm import record_say_hello
from taktik.core.database.tiktok_follow_graph import TikTokFollowGraphService


@pytest.fixture
def base(db, tmp_db_path, monkeypatch):
    monkeypatch.setattr(graph_module, "get_local_database", lambda: db)
    monkeypatch.setenv("TAKTIK_DB_PATH", tmp_db_path)
    account_id, _ = db.get_or_create_tiktok_account("moncompte")
    return db, account_id


def test_a_confirmed_follow_is_filed_counted_and_seen_by_the_unfollow(base):
    db, account_id = base

    assert TikTokFollowGraphService.record_follow("suggested_one", account_id) is True

    row = db._connection.execute(
        "SELECT COUNT(*) FROM interactions i JOIN social_profiles p ON p.legacy_profile_id = i.profile_id "
        "AND p.platform = i.platform WHERE i.platform = 'tiktok' AND i.account_id = ? "
        "AND i.interaction_type = 'FOLLOW' AND i.success = 1 AND p.username = 'suggested_one'",
        (account_id,),
    ).fetchone()
    assert row[0] == 1
    assert db.get_tiktok_daily_stats(account_id, days=1)[0]["total_follows"] == 1
    assert TikTokFollowGraphService.has_bot_follow_record("suggested_one", account_id) is True
    assert TikTokFollowGraphService.get_follow_age_days("suggested_one", account_id) == 0


def test_no_follow_is_filed_without_an_account_or_a_handle(base):
    _, account_id = base
    assert TikTokFollowGraphService.record_follow("", account_id) is False
    assert TikTokFollowGraphService.record_follow("suggested_one", 0) is False


def test_a_wave_leaves_the_already_written_marker(base):
    _, account_id = base

    assert record_say_hello(account_id, "@Friend.One") is True

    assert SentDMService.check_already_sent(account_id, "friend.one", platform="tiktok") is True
    assert SentDMService.check_already_sent(account_id, "friend.one", platform="instagram") is False


def test_a_wave_keeps_the_marker_of_an_earlier_dm(base):
    db, account_id = base
    SentDMService.record(account_id, "friend.one", "Hello there", True, platform="tiktok")
    before = db._connection.execute(
        "SELECT message_hash FROM sent_dms WHERE recipient_username = 'friend.one'"
    ).fetchone()[0]

    assert record_say_hello(account_id, "friend.one") is False

    after = db._connection.execute(
        "SELECT message_hash FROM sent_dms WHERE recipient_username = 'friend.one'"
    ).fetchone()[0]
    assert after == before is not None


@pytest.mark.parametrize("name", ["Friend One", "", "   "])
def test_a_wave_is_never_filed_under_a_display_name(base, name):
    _, account_id = base

    assert record_say_hello(account_id, name) is False
    assert record_say_hello(None, "friend.one") is False
    assert SentDMService.check_already_sent(account_id, name.strip().lower(), platform="tiktok") is False
    assert SentDMService.check_already_sent(account_id, "friend.one", platform="tiktok") is False
