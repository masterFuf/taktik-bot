"""One unfollow config, one run: the desktop bridge and the CLI start TikTok the same way and act as
the same account.

The CLI's handler ran the workflow on the connected device without starting TikTok: no clean
restart, no language, and no account read on the phone. With no acting account, the workflow can
neither date a follow (the minimum age keeps every row, `follow_date_unknown`) nor write a
confirmed unfollow to the database.
"""
import dataclasses

UNFOLLOW_ID = "tiktok.standalone.tiktok_unfollow"


def _run_both(rig, payload, set_phone=lambda: None):
    """The bridge gets the app's stdin payload; the CLI gets its `config`, as a terminal user
    writes it."""
    set_phone()
    bridge_exit = rig.run_unfollow_bridge(payload)
    bridge = {"exit": bridge_exit, "calls": list(rig.calls),
              "configs": [dataclasses.asdict(config) for config in rig.built_configs]}
    rig.forget_run()

    set_phone()
    result = rig.run_cli(payload["config"], workflow_id=UNFOLLOW_ID)
    cli = {"exit": result.exit_code, "calls": list(rig.calls),
           "configs": [dataclasses.asdict(config) for config in rig.built_configs],
           "result": rig.cli_results[-1] if rig.cli_results else None, "output": result.output}
    return bridge, cli


def test_a_cli_unfollow_starts_tiktok_like_the_bridge(rig, unfollow_payload):
    bridge, cli = _run_both(rig, unfollow_payload())

    assert cli["exit"] == bridge["exit"] == 0, cli["output"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert "detect_language" in cli["calls"]
    assert cli["calls"] == bridge["calls"]


def test_a_cli_unfollow_acts_as_the_account_read_on_the_phone(rig, unfollow_payload):
    bridge, cli = _run_both(rig, unfollow_payload("scheduler_node"))

    assert cli["exit"] == 0, cli["output"]
    assert cli["configs"] == bridge["configs"]
    assert cli["configs"][0]["bot_username"] == "acting_account"
    assert cli["configs"][0]["min_follow_age_days"] == 3
    # The confirmed unfollow is written: it has an account to be filed under.
    assert cli["result"]["stats"]["recorded"] == 1


def test_an_account_the_phone_does_not_show_leaves_both_paths_without_one(rig, unfollow_payload):
    def set_phone():
        rig.own_username = None

    bridge, cli = _run_both(rig, unfollow_payload(), set_phone=set_phone)

    assert cli["calls"] == bridge["calls"]
    assert cli["configs"] == bridge["configs"]
    assert cli["configs"][0]["bot_username"] is None
