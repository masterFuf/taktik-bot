"""The DM entries of the Instagram menu run the DM Responses page's launchers.

The "DM Auto-Reply" entry built `DMAutoReplyWorkflow`, a CLI-only engine the app never ran (its
own inbox reader, its own sender, AI written in the bot), and "View DM Inbox" tapped the DM tab by
itself. Both now go through `instagram.engagement.dm_read` and `instagram.engagement.dm_send`, with
the payloads the page gives the DM bridge.
"""
from instagram_dm_rig import DEVICE_ID, INSTAGRAM, dm_command


def _conversation(username, messages, *, can_reply=True, inbox_username=None):
    return {"username": username, "inbox_username": inbox_username or username, "can_reply": can_reply,
            "messages": [{"text": text, "is_sent": sent} for text, sent in messages]}


class _Recorder:
    """The launcher, as the menu calls it: what it was asked, and a read that found three threads."""

    def __init__(self, send_result=None):
        self.calls = []
        self.send_result = send_result or {"success": True}

    def __call__(self, device_manager, device_id, workflow_id, payload):
        self.calls.append((workflow_id, dict(payload)))
        if workflow_id.endswith("dm_read"):
            return {"type": "result", "success": True, "conversations": [
                _conversation("Dave D.", [("Are you open?", False)], inbox_username="dave"),
                _conversation("erin", [("Thanks!", True)]),
                _conversation("frank", [("Hello", False)], can_reply=False),
            ]}
        return dict(self.send_result)


def test_a_reply_goes_to_the_thread_handle_with_the_page_payloads():
    from taktik.cli.common import dm_menu

    run = _Recorder()
    outcome = dm_menu.reply_to_inbox(None, DEVICE_ID, 5, ask=lambda _q: " Yes, from ten ",
                                     show=lambda _l: None, run=run)

    assert run.calls == [
        ("instagram.engagement.dm_read", dm_command("read")),
        ("instagram.engagement.dm_send", dm_command("send", username="dave", message="Yes, from ten")),
    ]
    assert outcome["sent"] == [{"username": "dave", "success": True, "error": None}]


def test_an_empty_answer_sends_nothing():
    from taktik.cli.common import dm_menu

    run = _Recorder()
    dm_menu.reply_to_inbox(None, DEVICE_ID, 5, ask=lambda _q: "", show=lambda _l: None, run=run)

    assert [workflow_id for workflow_id, _payload in run.calls] == ["instagram.engagement.dm_read"]


def test_a_refused_message_stops_the_replies():
    from taktik.cli.common import dm_menu

    run = _Recorder(send_result={"success": False, "stop_reason": "action_blocked"})
    run_read = run.__call__

    def two_waiting(device_manager, device_id, workflow_id, payload):
        result = run_read(device_manager, device_id, workflow_id, payload)
        if workflow_id.endswith("dm_read"):
            result["conversations"].append(_conversation("gina", [("Hi", False)]))
        return result

    outcome = dm_menu.reply_to_inbox(None, DEVICE_ID, 5, ask=lambda _q: "Hi", show=lambda _l: None,
                                     run=two_waiting)

    assert [s["username"] for s in outcome["sent"]] == ["dave"]


def test_the_menu_reads_and_replies_through_the_dm_handlers(igd_rig):
    from taktik.cli.common import dm_menu

    igd_rig.device_manager.device = igd_rig.phone
    outcome = dm_menu.reply_to_inbox(igd_rig.device_manager, DEVICE_ID, 5, ask=lambda _q: "Yes",
                                     show=lambda _l: None)

    assert outcome["read"]["success"] is True
    assert igd_rig.calls.index(f"stop {INSTAGRAM}") < igd_rig.calls.index("navigate_to_dm_inbox")
    replied = [s["username"] for s in outcome["sent"]]
    assert replied and all(s["success"] for s in outcome["sent"])
    assert ["send_message Yes" for _ in replied] == [c for c in igd_rig.calls if c.startswith("send_message")]
    assert [row["partner_username"] for row in igd_rig.db if row["write"] == "sent"] == replied
