from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService


class _FakeDbService:
    def __init__(self):
        self.interaction_calls = []
        self.filtered_calls = []
        self.processed_calls = []
        self.processed_result = False
        self.filtered_result = False
        self.interaction_results = []
        self.filter_reason_result = None
        self.processed_record = {'processed': False}

    def record_interaction(self, **kwargs):
        self.interaction_calls.append(kwargs)
        if self.interaction_results:
            return self.interaction_results.pop(0)
        return True

    def is_profile_processed(self, **kwargs):
        return self.processed_result

    def mark_profile_as_processed(self, **kwargs):
        self.processed_calls.append(kwargs)
        return True

    def record_filtered_profile(self, **kwargs):
        self.filtered_calls.append(kwargs)
        return True

    def is_profile_filtered(self, username, account_id):
        return self.filtered_result

    def get_filter_reason(self, username, account_id):
        return self.filter_reason_result

    def check_profile_processed(self, account_id, username, hours_limit=24):
        return self.processed_record


def test_record_individual_actions_delegates_and_counts(monkeypatch):
    fake_db = _FakeDbService()
    fake_db.interaction_results = [True, False, True]

    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    ok = InstagramWorkflowStateService.record_individual_actions(
        username="target",
        action_type="LIKE",
        count=3,
        account_id=7,
        session_id=12,
    )

    assert ok is True
    assert len(fake_db.interaction_calls) == 3
    assert fake_db.interaction_calls[0]["account_id"] == 7
    assert fake_db.interaction_calls[0]["session_id"] == 12
    assert fake_db.interaction_calls[0]["interaction_type"] == "LIKE"


def test_record_individual_actions_requires_account_id():
    ok = InstagramWorkflowStateService.record_individual_actions(
        username="target",
        action_type="FOLLOW",
        count=1,
        account_id=None,
    )

    assert ok is False


def test_mark_profile_as_processed_delegates(monkeypatch):
    fake_db = _FakeDbService()
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    ok = InstagramWorkflowStateService.mark_profile_as_processed(
        username="target",
        source="followers",
        account_id=5,
        session_id=9,
    )

    assert ok is True
    assert fake_db.processed_calls == [
        {
            "account_id": 5,
            "username": "target",
            "notes": "followers",
            "session_id": 9,
        }
    ]


def test_record_filtered_profile_delegates(monkeypatch):
    fake_db = _FakeDbService()
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    ok = InstagramWorkflowStateService.record_filtered_profile(
        username="target",
        reason="too_small",
        source_type="FOLLOWERS",
        source_name="@source",
        account_id=4,
        session_id=11,
    )

    assert ok is True
    assert fake_db.filtered_calls == [
        {
            "account_id": 4,
            "username": "target",
            "reason": "too_small",
            "source_type": "FOLLOWERS",
            "source_name": "@source",
            "session_id": 11,
        }
    ]


def test_is_profile_skippable_returns_processed_reason(monkeypatch):
    fake_db = _FakeDbService()
    fake_db.processed_result = True
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    assert InstagramWorkflowStateService.is_profile_skippable("target", account_id=3) == (
        True,
        "already_processed",
    )


def test_is_profile_skippable_returns_filtered_reason(monkeypatch):
    fake_db = _FakeDbService()
    fake_db.filtered_result = True
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    assert InstagramWorkflowStateService.is_profile_skippable("target", account_id=3) == (
        True,
        "already_filtered",
    )


def test_is_profile_skippable_returns_false_when_unknown(monkeypatch):
    fake_db = _FakeDbService()
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    assert InstagramWorkflowStateService.is_profile_skippable("target", account_id=3) == (
        False,
        "",
    )


def test_get_skip_detail_already_filtered_returns_stored_reason(monkeypatch):
    fake_db = _FakeDbService()
    fake_db.filter_reason_result = "not enough posts"
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    assert (
        InstagramWorkflowStateService.get_skip_detail("target", 3, "already_filtered")
        == "not enough posts"
    )


def test_get_skip_detail_already_processed_returns_day_count(monkeypatch):
    from datetime import datetime, timedelta

    fake_db = _FakeDbService()
    last = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    fake_db.processed_record = {"processed": True, "last_interaction": last}
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    assert (
        InstagramWorkflowStateService.get_skip_detail("target", 3, "already_processed") == "7"
    )


def test_get_skip_detail_none_without_account(monkeypatch):
    fake_db = _FakeDbService()
    monkeypatch.setattr(InstagramWorkflowStateService, "_db", staticmethod(lambda: fake_db))

    assert InstagramWorkflowStateService.get_skip_detail("target", None, "already_filtered") is None
