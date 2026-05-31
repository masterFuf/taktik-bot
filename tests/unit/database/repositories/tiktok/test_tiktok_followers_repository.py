from taktik.core.database.repositories.tiktok.followers import TikTokFollowersRepository


class _FakeDb:
    def __init__(self):
        self.calls = []

    def get_or_create_tiktok_account(self, username):
        self.calls.append(("get_or_create_tiktok_account", username))
        return 42, {"username": username}

    def create_tiktok_session(self, **kwargs):
        self.calls.append(("create_tiktok_session", kwargs))
        return 99

    def end_tiktok_session(self, **kwargs):
        self.calls.append(("end_tiktok_session", kwargs))

    def check_tiktok_recent_interaction(self, username, account_id, hours):
        self.calls.append(("check_tiktok_recent_interaction", username, account_id, hours))
        return username == "known_recent"

    def has_tiktok_interaction(self, account_id, username):
        self.calls.append(("has_tiktok_interaction", account_id, username))
        return username == "known_any"

    def count_tiktok_interactions_for_target(self, account_id, target, hours):
        self.calls.append(("count_tiktok_interactions_for_target", account_id, target, hours))
        return 7

    def get_or_create_tiktok_profile(self, profile_data):
        self.calls.append(("get_or_create_tiktok_profile", profile_data))

    def record_tiktok_interaction(self, **kwargs):
        self.calls.append(("record_tiktok_interaction", kwargs))


def test_create_session_wraps_account_and_session_creation():
    db = _FakeDb()
    repository = TikTokFollowersRepository(db=db)

    session_ref = repository.create_session(
        bot_username="bot",
        target="target",
        config_used={"max": 10},
    )

    assert session_ref.account_id == 42
    assert session_ref.session_id == 99
    assert db.calls[0] == ("get_or_create_tiktok_account", "bot")
    assert db.calls[1][0] == "create_tiktok_session"
    assert db.calls[1][1]["workflow_type"] == "FOLLOWERS"


def test_repository_noops_without_account_context():
    db = _FakeDb()
    repository = TikTokFollowersRepository(db=db)

    assert not repository.has_recent_interaction(account_id=None, username="known_recent")
    assert not repository.has_interaction(account_id=None, username="known_any")
    assert repository.count_recent_target_interactions(account_id=None, target="target") == 0
    assert not repository.save_profile(account_id=None, profile_data={"username": "u"})
    repository.record_interaction(
        account_id=None,
        target_username="u",
        interaction_type="LIKE",
        session_id=1,
    )
    repository.end_session(
        account_id=None,
        session_id=1,
        status="COMPLETED",
        error_message=None,
        stats={},
    )

    assert db.calls == []


def test_repository_wraps_interaction_queries_and_writes():
    db = _FakeDb()
    repository = TikTokFollowersRepository(db=db)

    assert repository.has_recent_interaction(account_id=1, username="known_recent")
    assert repository.has_interaction(account_id=1, username="known_any")
    assert repository.count_recent_target_interactions(account_id=1, target="target") == 7
    assert repository.save_profile(account_id=1, profile_data={"username": "u"})
    repository.record_interaction(
        account_id=1,
        target_username="u",
        interaction_type="LIKE",
        session_id=2,
    )
    repository.end_session(
        account_id=1,
        session_id=2,
        status="COMPLETED",
        error_message=None,
        stats={"likes": 1},
    )

    assert ("check_tiktok_recent_interaction", "known_recent", 1, 168) in db.calls
    assert ("has_tiktok_interaction", 1, "known_any") in db.calls
    assert ("count_tiktok_interactions_for_target", 1, "target", 168) in db.calls
    assert db.calls[-2][0] == "record_tiktok_interaction"
    assert db.calls[-1][0] == "end_tiktok_session"
