"""One cold DM config, one engine: the desktop bridge and the CLI must do the same thing.

The CLI had a cold DM engine of its own (`workflows/cold_dm/cold_dm_workflow.py`) and no Agent id:
it read snake_case settings the page never sends, tested private and certified profiles with its
own reads instead of the recipient policy the page's two settings feed (a private profile the
operator allows was skipped, one without a Message button counted as a failure), kept no record of
what was sent (a second run wrote to the same people again) and answered the AI mode with a
placeholder. The bridge's engine is now the only one, in the core, and the CLI runs it.
"""

from instagram_cold_dm_rig import AI_KEY, INSTAGRAM, cold_dm_payload

# The bridge's own connection belongs to its process; the CLI brings a connected device.
_HOST_ONLY = ("connect",)


def _steps(calls):
    return [call for call in calls if call not in _HOST_ONLY]


def _run_both(rig, payload, env=None):
    code = rig.run_bridge(payload)
    assert code == 0, rig.stdout_lines
    bridge = {"steps": _steps(rig.calls), "db": list(rig.db), "sent": list(rig.sent),
              "sessions": list(rig.sessions), "final": rig.stdout_lines[-1]}
    rig.reset()

    result = rig.run_cli(payload, env=env)
    assert result.exit_code == 0, result.output
    cli = {"steps": _steps(rig.calls), "db": list(rig.db), "sent": list(rig.sent),
           "sessions": list(rig.sessions), "result": rig.cli_results[-1]}
    return bridge, cli


def test_the_cli_reaches_the_same_recipients_with_the_same_gestures(igc_rig):
    bridge, cli = _run_both(igc_rig, cold_dm_payload())

    assert cli["steps"] == bridge["steps"]
    assert cli["sent"] == bridge["sent"] == ["open_one"]
    assert cli["result"]["dms_success"] == bridge["final"]["dmsSuccess"] == 1
    assert cli["result"]["private_profiles"] == 1


def test_the_cli_follows_the_recipient_policy_of_the_page(igc_rig):
    igc_rig.users["closed_one"] = {"private": True, "message_button": True}
    bridge, cli = _run_both(igc_rig, cold_dm_payload(skipPrivateAccounts=False))

    assert cli["sent"] == bridge["sent"] == ["open_one", "closed_one"]


def test_the_cli_skips_certified_accounts_when_asked(igc_rig):
    igc_rig.users["open_one"] = {"verified": True}
    bridge, cli = _run_both(igc_rig, cold_dm_payload(skipVerifiedAccounts=True))

    assert cli["sent"] == bridge["sent"] == []
    assert "read_verified" in cli["steps"]


def test_the_cli_records_what_it_sent_and_does_not_send_it_twice(igc_rig):
    bridge, cli = _run_both(igc_rig, cold_dm_payload())

    assert cli["db"] == bridge["db"]
    assert [row["recipient"] for row in cli["db"]] == ["open_one"]

    igc_rig.reset()
    igc_rig.already_dmed = {"open_one", "closed_one"}
    result = igc_rig.run_cli(cold_dm_payload())
    assert result.exit_code == 0, result.output
    assert igc_rig.sent == []


def test_the_cli_files_the_run_as_one_session_like_the_bridge(igc_rig):
    bridge, cli = _run_both(igc_rig, cold_dm_payload())
    # The CLI's invocation adds `device_id` to the stored config; the session itself is the same.
    same = lambda rows: [{k: v for k, v in row.items() if k != "config_keys"} for row in rows]

    assert same(cli["sessions"]) == same(bridge["sessions"])
    assert [row["op"] for row in cli["sessions"]] == ["create", "finalize"]
    assert cli["sessions"][0]["workflow_type"] == "cold_dm"
    assert cli["sessions"][1]["status"] == "COMPLETED"


def test_the_cli_restarts_instagram_before_the_first_dm_like_the_bridge(igc_rig):
    _bridge, cli = _run_both(igc_rig, cold_dm_payload())

    steps = cli["steps"]
    assert steps.index(f"stop {INSTAGRAM}") < steps.index(f"launch {INSTAGRAM}") < steps.index("detect_language")


def test_the_cli_writes_ai_messages_with_the_key_of_the_environment(igc_rig):
    payload = cold_dm_payload(messageMode="ai", aiPrompt="Invite them to the tasting", messages=[],
                              recipients=["open_one"])

    result = igc_rig.run_cli(payload, env={"OPENROUTER_API_KEY": AI_KEY})

    assert result.exit_code == 0, result.output
    assert [call["key"] for call in igc_rig.ai_calls] == [AI_KEY]
    assert igc_rig.typed == ["AI note for open_one"]


def test_without_a_key_a_scripted_ai_run_is_refused_before_the_phone(igc_rig):
    payload = cold_dm_payload(messageMode="ai", aiPrompt="Invite them", messages=[], recipients=["open_one"])

    result = igc_rig.run_cli(payload, env={"OPENROUTER_API_KEY": ""})

    assert result.exit_code == 2, result.output
    assert "OPENROUTER_API_KEY" in result.output
    assert igc_rig.sent == []
    assert igc_rig.ai_calls == []
