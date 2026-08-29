"""The glue between the welcome decision and the production DM send.

Everything the device would do is faked. What is checked here is the wiring the phones cannot
check for us: that the anti-duplicate guard is really the one the outreach workflow consults,
that an unanswerable guard sends nothing at all, and that a failed send leaves no marker behind.
"""

import bridges.common.persistence.database as bridge_db
import bridges.tiktok.workflows.engagement.new_followers as new_followers
import taktik.core.social_media.tiktok.actions.business.workflows.dm.outreach as outreach_module
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


def _policy(**overrides) -> WelcomePolicy:
    base = {"enabled": True, "welcome_dm": True, "messages": ("Bienvenue !",),
            "max_dms": 5, "delay_min": 30, "delay_max": 70}
    base.update(overrides)
    return WelcomePolicy(**base)


def _silence_stdout(monkeypatch):
    """The bridge's IPC helpers write JSON to stdout; nothing here is testing that contract."""
    for name in ("send_status", "send_log", "set_workflow"):
        monkeypatch.setattr(new_followers, name, lambda *args, **kwargs: None)


def _install_fake_outreach(monkeypatch):
    _FakeOutreach.instances = []
    monkeypatch.setattr(outreach_module, "TikTokDMOutreachWorkflow", _FakeOutreach)


def test_a_guard_that_cannot_answer_sends_no_welcome_at_all(monkeypatch):
    """An outreach with no working duplicate protection is worse than no outreach.

    Would have caught the pass falling back on "nobody has been contacted" the way
    `SentDMService.check_already_sent` does, and welcoming the same people on every run.
    """
    _silence_stdout(monkeypatch)
    _install_fake_outreach(monkeypatch)
    monkeypatch.setattr(new_followers, "resolve_account_id", lambda username: 7)

    def boom(_account_id, _handle):
        raise RuntimeError("no such table: sent_dms")

    monkeypatch.setattr(new_followers, "sent_dm_already_recorded", boom)
    monkeypatch.setattr(new_followers, "thread_carries_our_message", boom)

    new_followers._welcome_decided({"deviceId": "device-1"}, object(), "bot", ["creator"], _policy())

    assert _FakeOutreach.instances == []


def test_the_outreach_only_ever_sees_the_recipients_the_guard_cleared(monkeypatch):
    _silence_stdout(monkeypatch)
    _install_fake_outreach(monkeypatch)
    monkeypatch.setattr(new_followers, "resolve_account_id", lambda username: 7)
    monkeypatch.setattr(
        new_followers, "sent_dm_already_recorded", lambda account_id, handle: handle == "known"
    )
    monkeypatch.setattr(new_followers, "thread_carries_our_message", lambda account_id, handle: False)

    manager = object()
    new_followers._welcome_decided(
        {"deviceId": "device-1"}, manager, "bot", ["@Fresh", "known"], _policy()
    )

    outreach = _FakeOutreach.instances[0]
    recipients, messages, kwargs = outreach.run_args
    assert recipients == ["fresh"]
    assert messages == ["Bienvenue !"]
    assert kwargs["account_id"] == 7
    assert kwargs["max_dms"] == 5
    assert (kwargs["delay_min"], kwargs["delay_max"]) == (30, 70)
    # The device session opened by `tiktok_startup` is reused rather than reconnected.
    assert outreach.kwargs["manager_factory"](device_id="device-1") is manager


def test_the_guard_runs_again_inside_the_workflow_right_before_each_send(monkeypatch):
    """The list was filtered several profile visits earlier; the last word belongs to the check
    that happens where the message actually leaves.

    Would have caught the workflow being handed the default `_never_duplicate` checker.
    """
    _silence_stdout(monkeypatch)
    _install_fake_outreach(monkeypatch)
    monkeypatch.setattr(new_followers, "resolve_account_id", lambda username: 7)
    # A message sent between the filtering and the send — another flow, another run, the same
    # account. The checker must see it, which it only does if it re-reads at call time.
    contacted = set()
    monkeypatch.setattr(
        new_followers, "sent_dm_already_recorded", lambda account_id, handle: handle in contacted
    )
    monkeypatch.setattr(new_followers, "thread_carries_our_message", lambda account_id, handle: False)

    new_followers._welcome_decided({"deviceId": "device-1"}, object(), "bot", ["fresh"], _policy())

    checker = _FakeOutreach.instances[0].kwargs["duplicate_checker"]
    assert checker(7, "fresh", "tiktok") is False

    contacted.add("fresh")
    assert checker(7, "fresh", "tiktok") is True


def test_an_unresolved_account_cancels_the_welcome_instead_of_sending_blind(monkeypatch):
    """Without an account nothing could be RECORDED afterwards, so the same welcome would go out
    again at every run. Would have caught a standalone run DMing the same people daily."""
    _silence_stdout(monkeypatch)
    _install_fake_outreach(monkeypatch)
    monkeypatch.setattr(new_followers, "resolve_account_id", lambda username: None)

    new_followers._welcome_decided({"deviceId": "device-1"}, object(), "bot", ["creator"], _policy())

    assert _FakeOutreach.instances == []


def test_a_policy_without_message_text_sends_nothing(monkeypatch):
    """The bot never composes: the texts come from the app."""
    _silence_stdout(monkeypatch)
    _install_fake_outreach(monkeypatch)
    monkeypatch.setattr(new_followers, "resolve_account_id", lambda username: 7)

    new_followers._welcome_decided(
        {"deviceId": "device-1"}, object(), "bot", ["creator"], _policy(messages=())
    )

    assert _FakeOutreach.instances == []


def test_a_failed_send_leaves_no_duplicate_marker_behind(monkeypatch):
    """`check_already_sent` matches a row whatever its `success` value.

    Would have caught a privacy-blocked or mistyped send locking that recipient out of every
    later attempt — a permanent skip earned by a failure.
    """
    recorded = []
    monkeypatch.setattr(bridge_db.SentDMService, "record",
                        staticmethod(lambda *args, **kwargs: recorded.append(args)))
    monkeypatch.setattr(new_followers, "record_sent", lambda *args: recorded.append(args))

    new_followers._record_welcome_dm(7, "creator", "Bienvenue !", False, "Privacy blocked", "s1")

    assert recorded == []


def test_a_successful_send_writes_both_the_marker_and_the_conversation(monkeypatch):
    """Two writes, like Instagram's welcome DM: the shared duplicate marker AND the thread.

    The TikTok reader cannot see who wrote a bubble, so a later inbox read recognises our own
    message only from the conversation row.
    """
    markers = []
    conversations = []
    monkeypatch.setattr(bridge_db.SentDMService, "record",
                        staticmethod(lambda *args, **kwargs: markers.append((args, kwargs))))
    monkeypatch.setattr(new_followers, "record_sent",
                        lambda *args: conversations.append(args))

    new_followers._record_welcome_dm(7, "creator", "Bienvenue !", True, None, "s1")

    assert markers[0][0][:4] == (7, "creator", "Bienvenue !", True)
    assert markers[0][1]["platform"] == "tiktok"
    assert conversations == [(7, "creator", "Bienvenue !")]
