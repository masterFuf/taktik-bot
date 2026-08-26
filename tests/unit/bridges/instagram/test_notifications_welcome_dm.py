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
"""

import pytest

import bridges.instagram.engagement.runtime.notifications.commands as commands
import bridges.instagram.engagement.runtime.notifications.welcome_dm as welcome_dm


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

    def build_workflow(self):
        return self.workflow


@pytest.fixture
def harness(monkeypatch):
    """A batch runtime with every device gesture and every DB write intercepted."""
    bridge = _Bridge()
    sent = []
    recorded = []
    audit = []

    monkeypatch.setattr(commands, "NotificationsBridge", lambda *a, **k: bridge)
    monkeypatch.setattr(commands, "emit_notif_json", lambda *a, **k: None)
    monkeypatch.setattr(commands, "load_actioned_hashes", lambda *a, **k: set())
    monkeypatch.setattr(commands, "batch_identity_hash", lambda *a, **k: None)
    monkeypatch.setattr(commands, "count_actions_today", lambda *a, **k: 0)
    monkeypatch.setattr(commands, "resolve_account_id", lambda *a, **k: 7)
    monkeypatch.setattr(commands, "wait_before_next_welcome_dm", lambda **k: None)
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

    return {"bridge": bridge, "sent": sent, "recorded": recorded, "audit": audit}


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

def test_welcome_dms_are_moved_to_the_end_order_preserved():
    ordered = welcome_dm.order_batch_actions([
        {"action": "welcome_dm", "username": "a"},
        {"action": "like", "username": "b"},
        {"action": "welcome_dm", "username": "c"},
        {"action": "follow_back", "username": "d"},
    ])

    assert [(e["action"], e["username"]) for e in ordered] == [
        ("like", "b"), ("follow_back", "d"), ("welcome_dm", "a"), ("welcome_dm", "c"),
    ]


def test_batch_runs_taps_before_any_dm(harness):
    commands.cmd_batch("device-1", [
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

    commands.cmd_batch("device-1", [
        {"action": "welcome_dm", "username": "newbie", "text": "hey"},
    ], account_username="me")

    assert harness["sent"] == []       # no gesture
    assert harness["recorded"] == []   # and no marker written either


def test_daily_cap_stops_the_dms_and_reports_them_as_skipped(harness, monkeypatch):
    monkeypatch.setattr(commands, "count_actions_today", lambda *a, **k: 2)

    commands.cmd_batch("device-1", [
        {"action": "welcome_dm", "username": "a", "text": "hey"},
        {"action": "welcome_dm", "username": "b", "text": "hey"},
    ], account_username="me", welcome_dm_daily_cap=2)

    assert harness["sent"] == []


def test_the_cap_counts_what_this_batch_lands(harness):
    commands.cmd_batch("device-1", [
        {"action": "welcome_dm", "username": "a", "text": "hey"},
        {"action": "welcome_dm", "username": "b", "text": "hey"},
        {"action": "welcome_dm", "username": "c", "text": "hey"},
    ], account_username="me", welcome_dm_daily_cap=2)

    # Two sent, the third refused by the cap this very batch advanced.
    assert [r for r, _ in harness["sent"]] == ["a", "b"]


def test_no_cap_flag_means_no_cap(harness):
    commands.cmd_batch("device-1", [
        {"action": "welcome_dm", "username": "a", "text": "hey"},
        {"action": "welcome_dm", "username": "b", "text": "hey"},
    ], account_username="me")

    assert len(harness["sent"]) == 2


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------

def test_a_sent_dm_is_recorded_with_its_body(harness):
    commands.cmd_batch("device-1", [
        {"action": "welcome_dm", "username": "newbie", "text": "welcome aboard"},
    ], account_username="me")

    assert harness["recorded"] == [(7, "newbie", "welcome aboard")]
    # The audit row carries the message, like a reply does -- a bare "action welcome_dm"
    # placeholder would make the trail useless.
    assert harness["audit"] == [("welcome_dm", "newbie", True, "welcome aboard")]


def test_a_failed_send_leaves_no_duplicate_marker(harness, monkeypatch):
    monkeypatch.setattr(commands, "send_welcome_dm",
                        lambda *a, **k: {"success": False, "error": "private profile"})

    commands.cmd_batch("device-1", [
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
