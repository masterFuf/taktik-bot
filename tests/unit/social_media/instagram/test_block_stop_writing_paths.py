"""Every Instagram writing path looks for the block after its gesture, the same way.

The look existed after a like, a follow, a comment or a story like of the engagement workflows
(`_stop_if_action_blocked`) and after an unfollow. The cold DM, the inbox reply and the
notification taps had none: a refused send was counted as sent, written to `sent_dms`, and the run
went on to the next recipient. Here each of them meets a screen where Instagram refuses, through
the one look (`look_for_action_block` on `ProblematicPageDetector.is_action_blocked`).
"""

from types import SimpleNamespace

from taktik.core.shared.diagnostics import run_halt


class _Refusing:
    """The production detector's contract: seeing the dialog sets the run's latch."""

    def __init__(self, *_args):
        pass

    def is_action_blocked(self):
        run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page (words)")
        return True


# --- cold DM ------------------------------------------------------------------------------------


def _cold_dm_workflow(monkeypatch):
    from taktik.core.social_media.instagram.workflows.cold_dm import workflow as module

    monkeypatch.setattr(module, "ProblematicPageDetector", _Refusing)
    workflow = module.ColdDMWorkflow.__new__(module.ColdDMWorkflow)
    workflow.device = object()
    workflow.navigate_to_search = lambda: True
    workflow.search_user = lambda recipient: True
    workflow.open_dm_from_profile = lambda policy=None: True
    workflow.sent = []
    workflow.send_message = lambda message: workflow.sent.append(message) or True
    return module, workflow


def test_a_refused_cold_dm_is_not_a_sent_dm(monkeypatch):
    module, workflow = _cold_dm_workflow(monkeypatch)

    result = workflow.reach_and_send("demo_recipient", lambda: "hello")

    assert result["outcome"] == module.ACTION_BLOCKED
    assert result["send_result"] is False


def test_a_cold_dm_run_stopped_by_a_block_says_so():
    from taktik.core.social_media.instagram.workflows.cold_dm.results import build_cold_dm_summary

    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page (words)")
    counters = SimpleNamespace(dms_sent=1, dms_success=1, dms_failed=1, private_profiles=0)

    assert build_cold_dm_summary(counters)["stop_reason"] == "action_blocked"


# --- DM inbox reply -----------------------------------------------------------------------------


def test_a_refused_inbox_reply_is_not_recorded_and_stays_on_screen(monkeypatch):
    from taktik.core.social_media.instagram.workflows.dm_inbox import agent_handler as module

    monkeypatch.setattr(module, "ProblematicPageDetector", _Refusing)
    monkeypatch.setattr(module, "ensure_dm_inbox", lambda runtime: True)
    recorded, went_back = [], []
    monkeypatch.setattr(module, "record_reply", lambda *args: recorded.append(args))
    monkeypatch.setattr(module, "return_to_inbox", lambda runtime: went_back.append(True))
    runtime = SimpleNamespace(device=object(), open_conversation=lambda username: True,
                              send_message=lambda message: True)

    result = module._send(runtime, "demo_friend", "hello")

    assert result["success"] is False and result["stop_reason"] == "action_blocked"
    assert recorded == [] and went_back == []


# --- notification taps --------------------------------------------------------------------------


def test_a_refused_notification_tap_says_why_nothing_was_done(monkeypatch):
    from taktik.core.social_media.instagram.workflows.management.notifications import (
        notifications_workflow as module,
    )

    monkeypatch.setattr(module, "ProblematicPageDetector", _Refusing)
    workflow = module.NotificationsEngagementWorkflow.__new__(module.NotificationsEngagementWorkflow)
    workflow.device = object()
    told = []
    workflow._notify = lambda action, status, message, **extra: told.append((action, status))
    result = {"success": True}

    assert workflow._refused("like", "demo_friend", result) is True
    assert result["success"] is False and result["stop_reason"] == "action_blocked"
    assert told == [("like", "failed")]
