"""One DM config, one run: the desktop bridge and the CLI read and send the same way, and write the
same rows.

The CLI's handler read and sent without starting TikTok (no clean restart, no language, no account)
and wrote nothing. After a read from the terminal the conversations were not in the database, and
after a send the bot could no longer tell its own messages from the other person's on the next read.
"""
import dataclasses

_BRIDGE_PROCESS_ONLY = {"force_stop tiktok"}


def _run_both(rig, payload, set_phone, workflow_id):
    set_phone()
    bridge_exit = rig.run_bridge(payload)
    bridge = {
        "exit": bridge_exit,
        "calls": [call for call in rig.calls if call not in _BRIDGE_PROCESS_ONLY],
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
        "db_writes": list(rig.db_writes),
    }
    rig.forget_run()

    set_phone()
    result = rig.run_cli(payload, workflow_id=workflow_id)
    cli = {
        "exit": result.exit_code,
        "calls": list(rig.calls),
        "configs": [dataclasses.asdict(config) for config in rig.built_configs],
        "db_writes": list(rig.db_writes),
        "result": rig.cli_results[-1] if rig.cli_results else None,
        "output": result.output,
    }
    return bridge, cli


def test_a_cli_read_starts_tiktok_like_the_bridge(rig, dm_read_payload):
    rig.install_dm_database()
    bridge, cli = _run_both(rig, dm_read_payload(), rig.show_dm_inbox, "tiktok.automation.dm_read")

    assert cli["exit"] == 0, cli["output"]
    assert cli["calls"][:3] == ["manager emulator-5554", "restart", "wait_app_surface"]
    assert cli["calls"] == bridge["calls"]
    assert cli["configs"] == bridge["configs"]


def test_a_cli_read_records_the_conversations_under_the_same_account(rig, dm_read_payload):
    rig.install_dm_database()
    bridge, cli = _run_both(rig, dm_read_payload(), rig.show_dm_inbox, "tiktok.automation.dm_read")

    assert cli["db_writes"] == bridge["db_writes"]
    assert cli["db_writes"][0] == {"account": "acting_account"}
    threads = [write["dm_conversation"] for write in cli["db_writes"] if "dm_conversation" in write]
    assert [thread["partner_username"] for thread in threads] == ["fan_one", "Fan Two"]
    # The bubble the reader could not attribute is ours: we recorded it when we sent it.
    assert threads[0]["messages"][-1]["direction"] == "sent"


def test_a_cli_send_records_what_actually_left(rig, dm_send_payload):
    rig.install_dm_database()

    def set_phone():
        rig.dm_send_failures = {"Fan Two"}

    bridge, cli = _run_both(rig, dm_send_payload(), set_phone, "tiktok.automation.dm_send")

    assert cli["exit"] == 0, cli["output"]
    assert cli["calls"] == bridge["calls"]
    assert cli["configs"] == bridge["configs"]
    assert cli["db_writes"] == bridge["db_writes"]
    sent = [write["dm_sent_message"] for write in cli["db_writes"] if "dm_sent_message" in write]
    assert [(row["partner_username"], row["text"]) for row in sent] == [("fan_one", "Merci beaucoup !")]
    assert cli["result"]["sent_count"] == 1


def test_the_cli_types_the_message_the_page_sent(rig, dm_send_payload):
    """The page sends an AI reply as the model wrote it; the bridge types it as is."""
    rig.install_dm_database()
    bridge, cli = _run_both(rig, dm_send_payload(), lambda: None, "tiktok.automation.dm_send")

    assert "send_message Fan Two 'Avec plaisir, à bientôt\\n'" in bridge["calls"]
    assert cli["calls"] == bridge["calls"]


def test_without_a_readable_account_neither_path_writes(rig, dm_read_payload):
    rig.install_dm_database()

    def set_phone():
        rig.show_dm_inbox()
        rig.own_username = None

    bridge, cli = _run_both(rig, dm_read_payload(), set_phone, "tiktok.automation.dm_read")

    assert bridge["db_writes"] == []
    assert cli["db_writes"] == []
    assert cli["calls"] == bridge["calls"]
