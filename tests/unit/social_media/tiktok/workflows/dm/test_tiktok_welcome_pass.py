"""The glue between the welcome decision and the production DM send.

Everything the device would do is faked. What is checked here is the wiring the phones cannot
check for us: that the anti-duplicate guard is really the one the outreach workflow consults,
that an unanswerable guard sends nothing at all, that a failed send leaves no marker behind, and
that a host which does not send welcome DMs sends none.
"""

import sqlite3
from types import SimpleNamespace

import pytest

import taktik.core.database.messaging as messaging
import taktik.core.database.tiktok_dm as tiktok_dm
import taktik.core.social_media.tiktok.workflows.dm.outreach as outreach_module
from taktik.core.social_media.tiktok.workflows.dm import welcome_pass
from taktik.core.database.local.schemas.messaging import (
    create_messaging_indexes,
    create_messaging_tables,
)
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
    monkeypatch.setattr(tiktok_dm, "who_has_written_to", boom)

    outcome = _welcome(["creator"])

    assert fake_outreach.instances == []
    assert outcome["sent"] is False
    assert outcome["skipped"] == {"creator": "guard_unavailable"}


def test_the_outreach_only_ever_sees_the_recipients_the_guard_cleared(monkeypatch, fake_outreach):
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: 7)
    monkeypatch.setattr(tiktok_dm, "sent_dm_already_recorded", lambda account_id, handle: handle == "known")
    monkeypatch.setattr(tiktok_dm, "who_has_written_to", lambda account_id, names: messaging.NOBODY_HAS_WRITTEN)
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
    monkeypatch.setattr(tiktok_dm, "who_has_written_to", lambda account_id, names: messaging.NOBODY_HAS_WRITTEN)

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


def test_a_welcome_to_every_follower_without_follow_back_builds_no_ai_service(monkeypatch, fake_outreach):
    """Product decision of 2026-09-27: no AI call, no cost, no AI licence when only the message is
    asked for; the qualification serves the follow-back alone.

    Would have caught the pass building the AI service (so demanding a key, and paying a call per
    follower) for a welcome that never reads a verdict, then giving up without a key.
    """
    import taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions as dm_actions_module

    class _Profiles:
        """Opens a follower's row; the profile shows the handle."""

        def __init__(self, device):
            self.device = device

        def open_new_follower_profile(self, shown_name):
            return shown_name.lower().replace(" ", "_")

    monkeypatch.setattr(dm_actions_module, "DMActions", _Profiles)
    recorded = []
    monkeypatch.setattr(welcome_pass, "_record_followers_as_notifications",
                        lambda account, followers, handles: recorded.append(dict(handles)))
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: 7)
    monkeypatch.setattr(tiktok_dm, "sent_dm_already_recorded", lambda account_id, handle: False)
    monkeypatch.setattr(tiktok_dm, "who_has_written_to", lambda account_id, names: messaging.NOBODY_HAS_WRITTEN)
    asked = []

    outcome = welcome_pass.run_welcome_pass(
        [{"username": "fan_one"}, {"username": "Fan Two"}], _policy(dm_requires_follow_back=False),
        workflow=SimpleNamespace(follow_back_users=lambda handles: pytest.fail("followed back")),
        started=SimpleNamespace(device=object(), bot_username="acting_account", manager=object()),
        device_id="device-1", ai_config={"enabled": False}, language="fr", notifier=_Notifier(),
        qualifier_factory=lambda ai_config, language: asked.append(ai_config),
    )

    assert asked == []
    assert outcome["summary"] == {"reasons": {"welcome_every_follower": 2}, "follow_back": 0, "welcome_dm": 2}
    assert fake_outreach.instances[0].run_args[0] == ["fan_one", "fan_two"]
    assert outcome["welcome_dm"]["sent"] is True
    # The attribution's raw material is still written: it needs the handles, not the AI.
    assert recorded == [{"fan_one": "fan_one", "Fan Two": "fan_two"}]


# ---------------------------------------------------------------------------
# Someone who already wrote to us (product decision): no welcome
# ---------------------------------------------------------------------------


class _Lines:
    """The outreach notifier: the lines the desktop reads (`dm_result`, `stats`...)."""

    def __init__(self):
        self.lines = []

    def send(self, event_type, **payload):
        self.lines.append((event_type, payload))


@pytest.fixture
def dm_record(tmp_path, monkeypatch):
    """A real conversation record, written by the production writers of the DM read."""
    import taktik.core.database as database

    path = tmp_path / "taktik.db"
    connection = sqlite3.connect(path)
    create_messaging_tables(connection.cursor())
    create_messaging_indexes(connection.cursor())
    connection.commit()
    connection.close()
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))
    monkeypatch.setattr(database, "configure_db_service", lambda: None)
    monkeypatch.setattr(tiktok_dm, "_partner_profile_id", lambda handle: None)
    return tiktok_dm


@pytest.fixture
def followers_page(monkeypatch):
    """Each row opens a profile whose handle is the shown name, lowercased, spaces as `_`."""
    import taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions as dm_actions_module

    class _Profiles:
        def __init__(self, device):
            self.device = device

        def open_new_follower_profile(self, shown_name):
            return shown_name.lower().replace(" ", "_")

    monkeypatch.setattr(dm_actions_module, "DMActions", _Profiles)
    monkeypatch.setattr(welcome_pass, "_record_followers_as_notifications", lambda *args: None)
    monkeypatch.setattr(tiktok_dm, "resolve_account_id", lambda username: 7)


def _welcome_every_follower(followers, lines):
    return welcome_pass.run_welcome_pass(
        [{"username": name} for name in followers], _policy(dm_requires_follow_back=False),
        workflow=SimpleNamespace(follow_back_users=lambda handles: pytest.fail("followed back")),
        started=SimpleNamespace(device=object(), bot_username="acting_account", manager=object()),
        device_id="device-1", ai_config={"enabled": False}, language="fr", notifier=_Notifier(),
        qualifier_factory=None, outreach_notifier=lines,
    )


def test_a_follower_whose_message_is_on_record_is_not_welcomed(dm_record, followers_page, fake_outreach):
    """The TikTok DM read filed the thread under the header's DISPLAY NAME, with their message
    only. The lock used to ask by handle alone whether WE had written: it found nothing, and
    "Bienvenue !" went to someone whose message was waiting for an answer.
    """
    dm_record.record_conversations(
        7, [{"name": "Fan Two", "messages": [{"text": "salut, j'adore tes videos", "is_sent": False}]}]
    )
    lines = _Lines()

    outcome = _welcome_every_follower(["fan_one", "Fan Two"], lines)

    assert fake_outreach.instances[0].run_args[0] == ["fan_one"]
    assert outcome["welcome_dm"]["skipped"] == {"fan_two": "wrote_to_us"}


def test_a_thread_filed_under_the_handle_is_found_too(dm_record, followers_page, fake_outreach):
    """A header that shows the handle files the thread under it."""
    dm_record.record_conversations(7, [{"name": "fan_one", "messages": [{"text": "coucou"}]}])

    outcome = _welcome_every_follower(["fan_one", "Fan Two"], _Lines())

    assert fake_outreach.instances[0].run_args[0] == ["fan_two"]
    assert outcome["welcome_dm"]["skipped"] == {"fan_one": "wrote_to_us"}


def test_every_follower_the_lock_leaves_out_is_reported_with_its_reason(dm_record, followers_page,
                                                                        fake_outreach):
    """The operator reads why, on the page: one `dm_result` per follower left out, skipped (never a
    failure), with its reason. They come after the send's own lines: the page takes each `stats`
    line as the reference for the send's counters, and these must add to it, not be reset by it.
    """
    dm_record.record_conversations(7, [{"name": "Fan Two", "messages": [{"text": "coucou"}]}])
    dm_record.record_welcome_dm(7, "fan_three", "Bienvenue !", True)
    lines = _Lines()

    _welcome_every_follower(["fan_one", "Fan Two", "Fan Three"], lines)

    skipped = [payload for kind, payload in lines.lines if kind == "dm_result" and payload.get("skipped")]
    assert [(line["username"], line["reason"], line["success"]) for line in skipped] == [
        ("fan_two", "wrote_to_us", False), ("fan_three", "already_dmed", False),
    ]
    assert all(line["error"] for line in skipped)
