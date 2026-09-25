"""One cold-DM config, one run: the desktop bridge and the CLI message the same people the same way
and leave the same marks in the database.

The CLI's handler was registered without a duplicate guard nor a recorder, so every run from the
terminal could message the same people again, and none of its DMs protected a later run. It also
ignored the AI mode: an AI payload carries no static message, and the handler refused it.
"""
from loguru import logger

OUTREACH_ID = "tiktok.standalone.tiktok_dm_outreach"
AI_KEY = "test-cli-openrouter-key"


def _sends(calls):
    return [call for call in calls if call.startswith("send_text")]


def _run_both(rig, payload, env=None, set_phone=lambda: None):
    """The same payload down the bridge, then down the CLI, each on its own empty database."""
    bridge_db = rig.use_real_sent_dms()
    rig.use_real_outreach()
    set_phone()
    bridge_exit = rig.run_outreach_bridge(payload)
    bridge = {"exit": bridge_exit, "calls": list(rig.calls), "rows": rig.sent_dm_rows(bridge_db),
              "ai": [service["api_key"] for service in rig.ai_services]}
    rig.forget_run()

    cli_db = rig.tmp_path / "cli_cold_dm.db"
    cli_db.write_bytes(b"")
    rig.monkeypatch.setenv("TAKTIK_DB_PATH", str(cli_db))
    set_phone()
    result = rig.run_cli(payload, env=env, workflow_id=OUTREACH_ID)
    cli = {"exit": result.exit_code, "calls": list(rig.calls), "rows": rig.sent_dm_rows(cli_db),
           "ai": [service["api_key"] for service in rig.ai_services], "output": result.output}
    return bridge, cli


def test_a_second_cli_run_does_not_message_the_same_people_again(rig, outreach_payload):
    database = rig.use_real_sent_dms()
    rig.use_real_outreach()
    payload = outreach_payload()

    first = rig.run_cli(payload, workflow_id=OUTREACH_ID)
    assert first.exit_code == 0, first.output
    assert [call.split(" ")[1] for call in _sends(rig.calls)] == ["fan_one", "fan_two", "fan_three"]
    rig.forget_run()

    second = rig.run_cli(payload, workflow_id=OUTREACH_ID)

    assert second.exit_code == 0, second.output
    assert _sends(rig.calls) == []
    # Filtered before the restart: the phone is not even brought to a clean state.
    assert "stop tiktok" not in rig.calls
    assert [(row["account_id"], row["recipient_username"], row["platform"], row["success"])
            for row in rig.sent_dm_rows(database)] == [
        (3, "fan_one", "tiktok", 1), (3, "fan_two", "tiktok", 1), (3, "fan_three", "tiktok", 1)]


def test_the_cli_leaves_the_rows_the_bridge_leaves(rig, outreach_payload):
    def set_phone():
        rig.privacy_blocked = {"fan_three"}

    bridge, cli = _run_both(rig, outreach_payload(), set_phone=set_phone)

    assert cli["exit"] == bridge["exit"] == 0, cli["output"]
    assert cli["calls"] == bridge["calls"]
    assert cli["rows"] == bridge["rows"]
    # The privacy-blocked recipient is marked too, as the app marks it: not tried again.
    assert [(row["recipient_username"], row["success"]) for row in cli["rows"]] == [
        ("fan_one", 1), ("fan_two", 1), ("fan_three", 0)]


def test_an_ai_run_writes_one_message_per_recipient_from_both_paths(rig, outreach_payload):
    payload = outreach_payload("ai", recipients=["fan_one", "fan_two"], openrouterApiKey=AI_KEY)
    bridge, cli = _run_both(rig, payload)

    assert cli["exit"] == bridge["exit"] == 0, cli["output"]
    assert cli["calls"] == bridge["calls"]
    assert _sends(cli["calls"]) == ["send_text fan_one 'Salut fan_one, on court ensemble ?'",
                                    "send_text fan_two 'Salut fan_two, on court ensemble ?'"]
    assert cli["ai"] == bridge["ai"] == [AI_KEY, AI_KEY]
    assert cli["rows"] == bridge["rows"]


def test_the_cli_takes_the_openrouter_key_from_the_environment(rig, outreach_payload):
    rig.use_real_sent_dms()
    rig.use_real_outreach()
    payload = outreach_payload("ai", recipients=["fan_one"])
    payload.pop("openrouterApiKey")

    result = rig.run_cli(payload, env={"OPENROUTER_API_KEY": AI_KEY}, workflow_id=OUTREACH_ID)

    assert result.exit_code == 0, result.output
    assert [service["api_key"] for service in rig.ai_services] == [AI_KEY]
    assert _sends(rig.calls) == ["send_text fan_one 'Salut fan_one, on court ensemble ?'"]


def test_without_a_key_both_paths_stop_the_same_way_and_the_cli_says_why(rig, outreach_payload):
    payload = outreach_payload("ai")
    payload.pop("openrouterApiKey")
    warnings = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        bridge, cli = _run_both(rig, payload)
    finally:
        logger.remove(sink)

    assert bridge["exit"] == 1
    assert cli["exit"] == 1
    assert cli["calls"] == bridge["calls"]
    assert _sends(cli["calls"]) == []
    assert cli["rows"] == bridge["rows"] == []
    assert any("OPENROUTER_API_KEY" in line for line in warnings)
