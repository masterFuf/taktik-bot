"""The `welcome_dm` verb of the notifications batch (welcome-dm-spec.md, lot 1).

A welcome DM is the only batch verb that writes to someone privately, and the only one
that leaves the activity feed. Four things must therefore hold, and none of them is
visible by reading a happy path:

- the DMs run LAST, whatever order the caller sent, so the cheap taps land first;
- a recipient already messaged (any flow) or already in conversation is never written to
  a second time;
- nothing is recorded under an unresolved account -- that is the case where the same
  message would be re-sent at every scan;
- a FAILED send leaves no duplicate marker, so a retry stays possible.

And one decided by the product: someone who wrote to us first is not welcomed (they get an answer
to their message, not "Bienvenue !").
"""

import sqlite3

import pytest

import taktik.core.social_media.instagram.workflows.notifications.commands as commands
import taktik.core.social_media.instagram.workflows.notifications.welcome_dm as welcome_dm


class _Workflow:
    def __init__(self):
        self.calls = []

    def like_comment(self, username):
        self.calls.append(("like", username))
        return {"success": True}

    def follow_back(self, username):
        self.calls.append(("follow_back", username))
        return {"success": True}


class _Bridge:
    def __init__(self):
        self.device = object()
        self.workflow = _Workflow()

    def connect(self):
        return True

    def restart_instagram(self):
        pass

    device_id = "device-1"


@pytest.fixture
def harness(monkeypatch):
    """A batch runtime with every device gesture and every DB write intercepted."""
    bridge = _Bridge()
    sent = []
    recorded = []
    audit = []

    monkeypatch.setattr(commands, "NotificationsEngagementWorkflow", lambda *a, **k: bridge.workflow)
    monkeypatch.setattr(commands, "load_actioned_hashes", lambda *a, **k: set())
    monkeypatch.setattr(commands, "batch_identity_hash", lambda *a, **k: None)
    monkeypatch.setattr(commands, "count_actions_today", lambda *a, **k: 0)
    monkeypatch.setattr(commands, "resolve_account_id", lambda *a, **k: 7)
    monkeypatch.setattr(commands, "wait_before_next_off_screen_action", lambda **k: None)
    monkeypatch.setattr(
        commands, "record_notification_action",
        lambda account, **kwargs: audit.append((kwargs.get("action"), kwargs.get("actor_username"),
                                                kwargs.get("success"), kwargs.get("content"))))
    monkeypatch.setattr(
        commands, "record_welcome_dm",
        lambda account_id, recipient, message: recorded.append((account_id, recipient, message)))

    def _send(device, recipient, text):
        sent.append((recipient, text))
        return {"success": True}

    monkeypatch.setattr(commands, "send_welcome_dm", _send)
    monkeypatch.setattr(commands, "welcome_dm_skip_reason", lambda *a, **k: None)

    host = commands.NotificationsHost(connect=lambda restart: bridge, emit=lambda payload: None)
    return {"bridge": bridge, "host": host, "sent": sent, "recorded": recorded, "audit": audit}


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_screen_leaving_verbs_are_moved_to_the_end_order_preserved():
    ordered = welcome_dm.order_batch_actions([
        {"action": "welcome_dm", "username": "a"},
        {"action": "like", "username": "b"},
        {"action": "welcome_dm", "username": "c"},
        {"action": "follow_actor", "username": "e"},
        {"action": "follow_back", "username": "d"},
    ])

    # Taps first (in the order given), then the profile walks: a follow is one tap on a page
    # we open anyway, a DM walks on from there.
    assert [(e["action"], e["username"]) for e in ordered] == [
        ("like", "b"), ("follow_back", "d"),
        ("follow_actor", "e"),
        ("welcome_dm", "a"), ("welcome_dm", "c"),
    ]


def test_batch_runs_taps_before_any_dm(harness):
    commands.cmd_batch(harness["host"], [
        {"action": "welcome_dm", "username": "newbie", "text": "hey"},
        {"action": "like", "username": "commenter"},
    ], account_username="me")

    # The like landed on the activity feed the scan left on screen; the DM walked away
    # from it only once nothing else needed that screen.
    assert harness["bridge"].workflow.calls == [("like", "commenter")]
    assert harness["sent"] == [("newbie", "hey")]


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("reason", ["no_account", "already_dmed", "conversation_exists"])
def test_a_guarded_recipient_is_never_written_to(harness, monkeypatch, reason):
    monkeypatch.setattr(commands, "welcome_dm_skip_reason", lambda *a, **k: reason)

    commands.cmd_batch(harness["host"], [
        {"action": "welcome_dm", "username": "newbie", "text": "hey"},
    ], account_username="me")

    assert harness["sent"] == []       # no gesture
    assert harness["recorded"] == []   # and no marker written either


def test_daily_cap_stops_the_dms_and_reports_them_as_skipped(harness, monkeypatch):
    monkeypatch.setattr(commands, "count_actions_today", lambda *a, **k: 2)

    commands.cmd_batch(harness["host"], [
        {"action": "welcome_dm", "username": "a", "text": "hey"},
        {"action": "welcome_dm", "username": "b", "text": "hey"},
    ], account_username="me", welcome_dm_daily_cap=2)

    assert harness["sent"] == []


def test_the_cap_counts_what_this_batch_lands(harness):
    commands.cmd_batch(harness["host"], [
        {"action": "welcome_dm", "username": "a", "text": "hey"},
        {"action": "welcome_dm", "username": "b", "text": "hey"},
        {"action": "welcome_dm", "username": "c", "text": "hey"},
    ], account_username="me", welcome_dm_daily_cap=2)

    # Two sent, the third refused by the cap this very batch advanced.
    assert [r for r, _ in harness["sent"]] == ["a", "b"]


def test_no_cap_flag_means_no_cap(harness):
    commands.cmd_batch(harness["host"], [
        {"action": "welcome_dm", "username": "a", "text": "hey"},
        {"action": "welcome_dm", "username": "b", "text": "hey"},
    ], account_username="me")

    assert len(harness["sent"]) == 2


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------

def test_a_sent_dm_is_recorded_with_its_body(harness):
    commands.cmd_batch(harness["host"], [
        {"action": "welcome_dm", "username": "newbie", "text": "welcome aboard"},
    ], account_username="me")

    assert harness["recorded"] == [(7, "newbie", "welcome aboard")]
    # The audit row carries the message, like a reply does -- a bare "action welcome_dm"
    # placeholder would make the trail useless.
    assert harness["audit"] == [("welcome_dm", "newbie", True, "welcome aboard")]


def test_a_failed_send_leaves_no_duplicate_marker(harness, monkeypatch):
    monkeypatch.setattr(commands, "send_welcome_dm",
                        lambda *a, **k: {"success": False, "error": "private profile"})

    commands.cmd_batch(harness["host"], [
        {"action": "welcome_dm", "username": "newbie", "text": "hey"},
    ], account_username="me")

    # Nothing in sent_dms: `check_already_sent` does not filter on success, so a marker
    # written here would lock this person out of every later attempt.
    assert harness["recorded"] == []
    # The failure itself IS recorded, in the audit trail.
    assert harness["audit"] == [("welcome_dm", "newbie", False, "hey")]


def test_an_empty_message_is_refused_before_any_navigation(monkeypatch):
    navigated = []
    monkeypatch.setattr(welcome_dm, "_return_home", lambda device: navigated.append("home"))

    result = welcome_dm.send_welcome_dm(object(), "newbie", "   ")

    assert result["success"] is False
    assert navigated == []


# ---------------------------------------------------------------------------
# Someone who already wrote to us (product decision): no welcome
# ---------------------------------------------------------------------------

@pytest.fixture
def dm_record(tmp_path, monkeypatch):
    """A real conversation record, written by the production writers."""
    from taktik.core.database.local.schemas.messaging import (
        create_messaging_indexes,
        create_messaging_tables,
    )

    path = tmp_path / "taktik.db"
    connection = sqlite3.connect(path)
    create_messaging_tables(connection.cursor())
    create_messaging_indexes(connection.cursor())
    connection.commit()
    connection.close()
    monkeypatch.setenv("TAKTIK_DB_PATH", str(path))

    from taktik.core.database.messaging import DmConversationService
    return DmConversationService


def _their_message(record, partner="newbie", text="salut, j'adore ton compte"):
    """What the Instagram DM reader records for a conversation where only they have written."""
    record.record_conversation(platform="instagram", account_id=7, partner_username=partner,
                               messages=[{"direction": "received", "text": text}])


def test_someone_who_wrote_to_us_first_is_not_welcomed(dm_record):
    """The lock used to ask only whether WE had written (`has_sent`): a follower whose message was
    waiting for an answer read as a stranger and got the welcome."""
    _their_message(dm_record)

    assert welcome_dm.welcome_dm_skip_reason(7, "newbie") == "wrote_to_us"


def test_a_conversation_we_are_in_is_still_refused_as_before(dm_record):
    _their_message(dm_record)
    dm_record.record_sent_message(platform="instagram", account_id=7, partner_username="newbie",
                                  text="merci !")

    assert welcome_dm.welcome_dm_skip_reason(7, "newbie") == "conversation_exists"


def test_a_stranger_is_still_welcomed(dm_record):
    _their_message(dm_record, partner="someone_else")

    assert welcome_dm.welcome_dm_skip_reason(7, "newbie") is None


def test_a_record_that_cannot_be_read_refuses_the_welcome(tmp_path, monkeypatch):
    """A lock that cannot read answered "never contacted" and the message left: a private message
    on a guess. It now refuses, as the TikTok welcome always did."""
    monkeypatch.setenv("TAKTIK_DB_PATH", str(tmp_path / "missing.db"))

    assert welcome_dm.welcome_dm_skip_reason(7, "newbie") == "guard_unavailable"


def test_the_batch_leaves_out_who_wrote_to_us_and_says_why(harness, monkeypatch, dm_record):
    _their_message(dm_record)
    monkeypatch.setattr(commands, "welcome_dm_skip_reason", welcome_dm.welcome_dm_skip_reason)
    steps = []
    host = commands.NotificationsHost(connect=lambda restart: harness["bridge"], emit=steps.append)

    result = commands.cmd_batch(host, [
        {"action": "welcome_dm", "username": "newbie", "text": "Bienvenue !"},
    ], account_username="me")

    assert harness["sent"] == []
    assert harness["recorded"] == []
    assert result["skipped"] == 1
    assert result["results"][0]["reason"] == "wrote_to_us"
    assert result["results"][0]["message"] == "wrote to us first: no welcome message"
    assert steps[-1]["message"].endswith("wrote to us first: no welcome message")


def test_a_welcome_dm_walks_to_the_recipient_profile_then_writes(monkeypatch):
    """The send itself, down the production road: `send_welcome_dm` -> `send_dm(navigate_to_profile=True)`
    -> the navigation's walk to the profile -> the message -> the look for a block -> home.

    The walk's lazy import aimed at `business/atomic/navigation`, a module that never existed there:
    `send_dm` caught the ImportError and returned False before any gesture, so no welcome DM ever
    left. The phone's steps are recorded at the production classes (only the screens are not read).
    """
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.workflows.dm.messaging import (
        MessagingBusiness,
    )
    from taktik.core.social_media.instagram.ui.detectors.problematic_page import ProblematicPageDetector

    steps = []
    monkeypatch.setattr("time.sleep", lambda *_: None)
    monkeypatch.setattr(NavigationActions, "navigate_to_profile",
                        lambda self, username, **_: steps.append(("profile", username)) or True)
    monkeypatch.setattr(NavigationActions, "navigate_to_home", lambda self: steps.append(("home",)) or True)
    monkeypatch.setattr(MessagingBusiness, "send_dm_from_profile",
                        lambda self, message: steps.append(("write", message)) or True)
    monkeypatch.setattr(ProblematicPageDetector, "is_action_blocked",
                        lambda self: steps.append(("block?",)) or False)

    result = welcome_dm.send_welcome_dm(object(), "newbie", "Bienvenue !")

    assert result == {"success": True, "message": "welcome DM sent to @newbie"}
    assert steps == [("profile", "newbie"), ("write", "Bienvenue !"), ("block?",), ("home",)]
