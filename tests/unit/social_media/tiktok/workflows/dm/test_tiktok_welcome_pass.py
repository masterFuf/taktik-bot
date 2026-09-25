"""The glue between the welcome decision and the production DM send.

Everything the device would do is faked. What is checked here is the wiring the phones cannot
check for us: that the anti-duplicate guard is really the one the outreach workflow consults,
that an unanswerable guard sends nothing at all, that a failed send leaves no marker behind, and
that a host which does not send welcome DMs sends none.
"""

from types import SimpleNamespace

import pytest

import taktik.core.database.messaging as messaging
import taktik.core.database.tiktok_dm as tiktok_dm
import taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach as outreach_module
from taktik.core.social_media.tiktok.actions.business.workflows.dm import welcome_pass
from taktik.core.social_media.tiktok.services.welcome.decision import WelcomePolicy


class _FakeOutreach:
    instances = []

    def __init__(self, device_id, **kwargs):
        self.device_id = device_id
        self.kwargs = kwargs
        self.connected = False
        self.run_args = None
        _FakeOutreach.instances.append(self)

    def connect(self):
        self.connected = True
        return True

    def run(self, recipients, messages, **kwargs):
        self.run_args = (recipients, messages, kwargs)
        return {"success": True, "dms_sent": len(recipients), "dms_success": len(recipients),
                "dms_failed": 0}


class _Notifier:
    def __init__(self):
        self.calls = []

    def status(self, *args):
        self.calls.append(("status", args))

    def log(self, *args):
        self.calls.append(("log", args))


def _policy(**overrides) -> WelcomePolicy:
    base = {"enabled": True, "welcome_dm": True, "messages": ("Bienvenue !",),
            "max_dms": 5, "delay_min": 30, "delay_max": 70}
    base.update(overrides)
    return WelcomePolicy(**base)


@pytest.fixture
def fake_outreach(monkeypatch):
    _FakeOutreach.instances = []
    monkeypatch.setattr(outreach_module, "TikTokDMOutreachWorkflow", _FakeOutreach)
    return _FakeOutreach


def _welcome(handles, policy=None, *, manager=None, send_welcome_dms=True, hooked=None):
    started = SimpleNamespace(device=object(), bot_username="acting_account", manager=manager or object())
    return welcome_pass._welcome_decided(
        handles, policy or _policy(), started=started, device_id="device-1", notifier=_Notifier(),
        outreach_notifier=None, workflow_hook=hooked, send_welcome_dms=send_welcome_dms,
    )


def test_a_guard_that_cannot_answer_sends_no_welcome_at_all(monkeypatch, fake_outreach):
    """An outreach with no working duplicate protection is worse than no outreach.

    Would have caught the pass falling back on "nobody has been contacted" the way
    `SentDMService.check_already_sent` does, and welcoming the same people on every run.
    """
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: 7)

    def boom(_account_id, _handle):
        raise RuntimeError("no such table: sent_dms")

    monkeypatch.setattr(tiktok_dm, "sent_dm_already_recorded", boom)
    monkeypatch.setattr(tiktok_dm, "thread_carries_our_message", boom)

    outcome = _welcome(["creator"])

    assert fake_outreach.instances == []
    assert outcome["sent"] is False
    assert outcome["skipped"] == {"creator": "guard_unavailable"}


def test_the_outreach_only_ever_sees_the_recipients_the_guard_cleared(monkeypatch, fake_outreach):
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: 7)
    monkeypatch.setattr(tiktok_dm, "sent_dm_already_recorded", lambda account_id, handle: handle == "known")
    monkeypatch.setattr(tiktok_dm, "thread_carries_our_message", lambda account_id, handle: False)
    manager = object()
    hooked = []

    _welcome(["@Fresh", "known"], manager=manager, hooked=hooked.append)

    outreach = fake_outreach.instances[0]
    recipients, messages, kwargs = outreach.run_args
    assert recipients == ["fresh"]
    assert messages == ["Bienvenue !"]
    assert kwargs["account_id"] == 7
    assert kwargs["max_dms"] == 5
    assert kwargs["session_id"] == "device-1"
    assert (kwargs["delay_min"], kwargs["delay_max"]) == (30, 70)
    # The session the startup opened is reused rather than reconnected, and the host can stop it.
    assert outreach.kwargs["manager_factory"](device_id="device-1") is manager
    assert hooked == [outreach]


def test_the_guard_runs_again_inside_the_workflow_right_before_each_send(monkeypatch, fake_outreach):
    """The list was filtered several profile visits earlier; the last word belongs to the check
    that happens where the message actually leaves.

    Would have caught the workflow being handed the default `_never_duplicate` checker.
    """
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: 7)
    # A message sent between the filtering and the send, by another flow of the same account. The
    # checker must see it, which it only does if it re-reads at call time.
    contacted = set()
    monkeypatch.setattr(tiktok_dm, "sent_dm_already_recorded", lambda account_id, handle: handle in contacted)
    monkeypatch.setattr(tiktok_dm, "thread_carries_our_message", lambda account_id, handle: False)

    _welcome(["fresh"])

    checker = fake_outreach.instances[0].kwargs["duplicate_checker"]
    assert checker(7, "fresh", "tiktok") is False

    contacted.add("fresh")
    assert checker(7, "fresh", "tiktok") is True


def test_an_unresolved_account_cancels_the_welcome_instead_of_sending_blind(monkeypatch, fake_outreach):
    """Without an account nothing could be RECORDED afterwards, so the same welcome would go out
    again at every run. Would have caught a standalone run DMing the same people daily."""
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: None)

    outcome = _welcome(["creator"])

    assert fake_outreach.instances == []
    assert outcome["reason"] == "account_unresolved"


def test_a_policy_without_message_text_sends_nothing(monkeypatch, fake_outreach):
    """The bot never composes: the texts come from the app."""
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: 7)

    outcome = _welcome(["creator"], _policy(messages=()))

    assert fake_outreach.instances == []
    assert outcome["reason"] == "no_message"


def test_a_host_that_does_not_send_welcome_dms_sends_none_and_says_to_whom(monkeypatch, fake_outreach):
    """The CLI, until the product decision: the pass decides, nothing leaves, the recipients are
    reported. Nothing is asked of the database either."""
    asked = []
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: asked.append(username) or 7)

    outcome = _welcome(["fan_one", "fan_two"], send_welcome_dms=False)

    assert fake_outreach.instances == []
    assert asked == []
    assert outcome == {"sent": False, "recipients": ["fan_one", "fan_two"], "reason": "not_sent_from_this_host"}


def test_a_failed_send_leaves_no_duplicate_marker_behind(monkeypatch):
    """`check_already_sent` matches a row whatever its `success` value.

    Would have caught a privacy-blocked or mistyped send locking that recipient out of every
    later attempt -- a permanent skip earned by a failure.
    """
    recorded = []
    monkeypatch.setattr(messaging.SentDMService, "record",
                        staticmethod(lambda *args, **kwargs: recorded.append(args)))
    monkeypatch.setattr(tiktok_dm, "record_sent", lambda *args: recorded.append(args))

    tiktok_dm.record_welcome_dm(7, "creator", "Bienvenue !", False, "Privacy blocked", "s1")

    assert recorded == []


def test_a_successful_send_writes_both_the_marker_and_the_conversation(monkeypatch):
    """Two writes, like Instagram's welcome DM: the shared duplicate marker AND the thread.

    The TikTok reader cannot see who wrote a bubble, so a later inbox read recognises our own
    message only from the conversation row.
    """
    markers = []
    conversations = []
    monkeypatch.setattr(messaging.SentDMService, "record",
                        staticmethod(lambda *args, **kwargs: markers.append((args, kwargs))))
    monkeypatch.setattr(tiktok_dm, "record_sent", lambda *args: conversations.append(args))

    tiktok_dm.record_welcome_dm(7, "creator", "Bienvenue !", True, None, "s1")

    assert markers[0][0][:4] == (7, "creator", "Bienvenue !", True)
    assert markers[0][1]["platform"] == "tiktok"
    assert conversations == [(7, "creator", "Bienvenue !")]


def test_without_an_ai_service_the_pass_decides_nothing():
    """No verdict, no decision: falling back to "follow everyone back" would be the run doing
    something nobody asked for."""
    notifier = _Notifier()
    workflow = SimpleNamespace(follow_back_users=lambda handles: pytest.fail("followed back without a verdict"))

    outcome = welcome_pass.run_welcome_pass(
        [{"username": "creator"}], _policy(follow_back=True), workflow=workflow,
        started=SimpleNamespace(device=object(), bot_username="acting_account", manager=None),
        device_id="device-1", ai_config={"enabled": True}, language="fr", notifier=notifier,
        qualifier_factory=lambda ai_config, language: None,
    )

    assert outcome == {"skipped": "no_ai_service"}
    assert ("log", ("warning", "AI welcome pass skipped: no AI service available")) in notifier.calls
