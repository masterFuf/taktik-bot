"""One DM command, one path: the desktop bridge and the CLI read and reply the same way.

The CLI had no DM handler: `taktik management dm inbox` and `read-all` had readers of their own
(no restart for the first, no record of what was read, none of the inbox triage), and `dm send`
went through `DMOutreachWorkflow` (a profile visit, then the Message button), recording nothing. The
DM bridge's runtime is now in the core, and the handlers `instagram.engagement.dm_read` and
`instagram.engagement.dm_send` run it through the same launcher as the bridge.
"""
from instagram_dm_rig import CLONE, dm_command

_HOST_ONLY = ("connect",)


def _steps(calls):
    return [call for call in calls if call not in _HOST_ONLY]


def _run_both(rig, spec, workflow_id, *, screen="home"):
    rig.phone.screen = screen
    code = rig.run_bridge(spec)
    assert code == 0, rig.stdout_lines
    bridge = {"steps": _steps(rig.calls), "db": list(rig.db), "final": rig.stdout_lines[-1]}
    rig.reset()

    rig.phone.screen = screen
    payload = {key: value for key, value in spec.items() if key not in ("deviceId",)}
    result = rig.run_cli(workflow_id, payload)
    assert result.exit_code == 0, result.output
    cli = {"steps": _steps(rig.calls), "db": list(rig.db), "result": rig.cli_results[-1]}
    return bridge, cli


def test_the_cli_reads_the_inbox_like_the_bridge(igd_rig):
    bridge, cli = _run_both(igd_rig, dm_command("read"), "instagram.engagement.dm_read")

    assert cli["steps"] == bridge["steps"]
    assert cli["db"] == bridge["db"] and cli["db"]
    assert cli["result"] == bridge["final"]
    assert [c["username"] for c in cli["result"]["conversations"]] == ["bob", "carol", "dave"]


def test_the_cli_reads_the_requests_folder_like_the_bridge(igd_rig):
    bridge, cli = _run_both(igd_rig, dm_command("read_requests"), "instagram.engagement.dm_read")

    assert cli["steps"] == bridge["steps"]
    assert cli["result"] == bridge["final"]
    assert cli["result"]["is_requests"] is True


def test_the_cli_replies_in_the_conversation_and_records_it(igd_rig):
    spec = dm_command("send", username="dave", message="Yes, from ten")
    bridge, cli = _run_both(igd_rig, spec, "instagram.engagement.dm_send", screen="inbox")

    assert cli["steps"] == bridge["steps"]
    assert cli["db"] == bridge["db"] == [{"write": "sent", "platform": "instagram", "account_id": 7,
                                          "partner_username": "dave", "text": "Yes, from ten",
                                          "partner_profile_id": 104}]
    assert cli["result"] == bridge["final"]


def test_the_cli_restarts_a_clone_like_the_bridge(igd_rig):
    bridge, cli = _run_both(igd_rig, dm_command("read", packageName=CLONE), "instagram.engagement.dm_read")

    assert cli["steps"] == bridge["steps"]
    assert f"stop {CLONE}" in cli["steps"] and f"launch {CLONE}" in cli["steps"]


def test_a_cli_reply_to_a_conversation_it_cannot_find_fails(igd_rig):
    igd_rig.phone.screen = "inbox"
    result = igd_rig.run_cli("instagram.engagement.dm_send", {"username": "nobody", "message": "Hi"})

    assert result.exit_code == 1
    assert "Cannot find conversation with nobody" in result.output
    assert igd_rig.db == []
