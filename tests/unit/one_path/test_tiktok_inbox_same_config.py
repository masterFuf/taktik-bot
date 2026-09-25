"""One inbox config, one run: the desktop bridge and the CLI do the same thing with it.

The CLI's handler drove the same DM workflow but never started TikTok, and its new-followers flow
only read the list: the AI welcome pass (qualify each follower, record them for the attribution,
follow back) lived in the bridge alone.

One gap is kept on purpose, pending Kevin's decision: the CLI does not send the welcome DM the
pass decided on. It reports the recipients instead.
"""
import dataclasses

import pytest

_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}
_WELCOME_DM_CALLS = ("outreach_", "welcome_")


def _run_both(rig, payload, set_phone, workflow_id, env=None):
    set_phone()
    bridge_exit = rig.run_bridge(payload)
    bridge = {
        "exit": bridge_exit,
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
        "db_writes": list(rig.db_writes),
        "events": list(rig.events),
    }
    rig.forget_run()

    set_phone()
    result = rig.run_cli(payload, workflow_id=workflow_id, env=env)
    cli = {
        "exit": result.exit_code,
        "calls": list(rig.calls),
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
        "db_writes": list(rig.db_writes),
        "result": rig.cli_results[-1] if rig.cli_results else None,
        "output": result.output,
    }
    return bridge, cli


FLOWS = (
    ("new_followers", "scrape", "tiktok.automation.new_followers"),
    ("new_followers", "follow_back", "tiktok.automation.new_followers"),
    ("dm_unreplied", "scrape", "tiktok.automation.dm_unreplied"),
    ("dm_requests", "scrape", "tiktok.automation.dm_requests"),
    ("dm_requests", "execute", "tiktok.automation.dm_requests"),
    ("dm_activity", "scrape", "tiktok.automation.dm_activity"),
)


@pytest.mark.parametrize("workflow_type,mode,workflow_id", FLOWS)
def test_every_inbox_flow_starts_tiktok_and_runs_the_same_from_both_paths(
    rig, inbox_payload, workflow_type, mode, workflow_id
):
    def set_phone():
        rig.show_notifications()
        rig.show_inbox_lists()

    bridge, cli = _run_both(rig, inbox_payload(workflow_type, mode=mode), set_phone, workflow_id)

    assert bridge["exit"] == 0
    assert cli["exit"] == 0, cli["output"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert cli["calls"] == bridge["calls"]
    assert cli["configs"] == bridge["configs"]


def _welcome_payload(inbox_payload, welcome_ai):
    return inbox_payload("new_followers", ai=welcome_ai())


def test_the_cli_runs_the_welcome_pass_up_to_the_dm(rig, inbox_payload, welcome_ai):
    rig.install_dm_database()
    bridge, cli = _run_both(rig, _welcome_payload(inbox_payload, welcome_ai), rig.show_welcome_verdicts,
                            "tiktok.automation.new_followers")

    assert cli["exit"] == 0, cli["output"]
    # Same profiles opened, same AI questions, same follow-backs; the DM stays on the desktop.
    assert "follow_back ['fan_one', 'fan_two']" in cli["calls"]
    assert cli["calls"] == [call for call in bridge["calls"] if not call.startswith(_WELCOME_DM_CALLS)]
    assert "welcome_dm fan_one" in bridge["calls"]


def test_the_cli_records_the_new_followers_for_the_attribution(rig, inbox_payload, welcome_ai):
    rig.install_dm_database()
    bridge, cli = _run_both(rig, _welcome_payload(inbox_payload, welcome_ai), rig.show_welcome_verdicts,
                            "tiktok.automation.new_followers")

    notifications = [write for write in cli["db_writes"] if "items" in write]
    assert [item["username"] for item in notifications[0]["items"]] == ["fan_one", "fan_two"]
    # The bridge goes on to record the welcome DM it sent; the CLI sent none.
    assert cli["db_writes"] == bridge["db_writes"][:len(cli["db_writes"])]
    assert not [write for write in cli["db_writes"] if "sent_dm" in write or "dm_sent_message" in write]


def test_the_cli_says_which_welcome_dms_it_did_not_send(rig, inbox_payload, welcome_ai):
    rig.install_dm_database()
    _bridge, cli = _run_both(rig, _welcome_payload(inbox_payload, welcome_ai), rig.show_welcome_verdicts,
                             "tiktok.automation.new_followers")

    welcome = cli["result"]["welcome"]
    assert welcome["summary"]["welcome_dm"] == 2
    assert welcome["welcome_dm"]["sent"] is False
    assert welcome["welcome_dm"]["recipients"] == ["fan_one", "fan_two"]


def test_the_cli_takes_the_ai_key_from_the_environment(rig, inbox_payload, welcome_ai):
    """The desktop puts the key in the payload; a terminal run brings it in OPENROUTER_API_KEY."""
    rig.install_dm_database()
    rig.show_welcome_verdicts()
    payload = _welcome_payload(inbox_payload, welcome_ai)
    payload["ai"].pop("openrouterApiKey")

    result = rig.run_cli(payload, workflow_id="tiktok.automation.new_followers",
                         env={"OPENROUTER_API_KEY": "test-openrouter-key"})

    assert result.exit_code == 0, result.output
    assert rig.ai_services == [{"api_key": "test-openrouter-key", "has_ipc": False}]
    assert "ai_classify fan_one" in rig.calls
