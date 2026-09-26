"""One notifications config, one pass: the desktop bridge and the CLI do the same thing with it.

The CLI had no id for this workflow (`tiktok.automation.notifications` was unknown), and the pass
itself lived in the bridge: the new-followers scan, the rows it records, the Activity read, the
hellos and the suggested follows were the desktop's alone.
"""

_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}
WORKFLOW_ID = "tiktok.automation.notifications"


def _bridge_stats(rig):
    results = [event for kind, event in rig.events if kind == "notifications_result"]
    assert results, "the bridge reported no result"
    return results[-1]["stats"]


def _run_both(rig, payload, set_phone):
    set_phone()
    bridge_exit = rig.run_bridge(payload)
    bridge = {
        "exit": bridge_exit,
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
        "db_writes": list(rig.db_writes),
        "stats": _bridge_stats(rig),
    }
    rig.forget_run()

    set_phone()
    result = rig.run_cli(payload, workflow_id=WORKFLOW_ID)
    cli = {
        "exit": result.exit_code,
        "calls": list(rig.calls),
        "db_writes": list(rig.db_writes),
        "stats": rig.cli_results[-1]["stats"] if rig.cli_results else None,
        "output": result.output,
    }
    return bridge, cli


def test_the_cli_runs_the_pass_the_bridge_runs(rig, notifications_payload):
    bridge, cli = _run_both(rig, notifications_payload(), rig.show_notifications)

    assert cli["exit"] == 0, cli["output"]
    assert cli["calls"] == bridge["calls"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert cli["stats"] == bridge["stats"]
    assert cli["stats"]["new_followers_recorded"] == 2


def test_the_cli_records_the_new_followers_under_the_same_account(rig, notifications_payload):
    bridge, cli = _run_both(rig, notifications_payload(), rig.show_notifications)

    assert cli["db_writes"] == bridge["db_writes"]
    assert cli["db_writes"][0] == {"account": "acting_account"}
    assert [item["username"] for item in cli["db_writes"][1]["items"]] == ["fan_one", "fan_two"]


def test_every_step_runs_the_same_from_both_paths(rig, notifications_payload):
    def set_phone():
        rig.show_notifications()
        rig.hello_candidates = ["Ana", "Bob", "Cid"]
        rig.suggestion_reads = [[], [{"name": "Suggested A"}]]
        rig.profile_handles.update({"Ana": "ana.handle", "Bob": "bob.handle", "Suggested A": "suggested_a"})

    payload = notifications_payload(maxHellos=2, maxSuggestedFollows=1)
    bridge, cli = _run_both(rig, payload, set_phone)

    assert cli["exit"] == 0, cli["output"]
    assert cli["calls"] == bridge["calls"]
    assert (cli["stats"]["hello_sent"], cli["stats"]["suggested_followed"]) == (2, 1)
    assert cli["stats"] == bridge["stats"]
    assert cli["db_writes"] == bridge["db_writes"]
    assert {"follow": {"account_id": 42, "username": "suggested_a"}} in cli["db_writes"]
    assert {"hello": {"account_id": 42, "recipient": "bob.handle"}} in cli["db_writes"]


def test_a_failed_step_fails_the_run_on_both_paths(rig, notifications_payload):
    def set_phone():
        rig.show_notifications()
        rig.activity_fails = True

    bridge, cli = _run_both(rig, notifications_payload(), set_phone)

    assert bridge["exit"] == 1
    assert cli["exit"] == 1
    assert cli["calls"] == bridge["calls"]
