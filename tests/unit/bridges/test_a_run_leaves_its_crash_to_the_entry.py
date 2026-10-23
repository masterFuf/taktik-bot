"""A bridge whose run has nothing to add to an exception lets it rise to `run_bridge_main`.

The entry says it once, in the bridge's own error shape (`CRASH`, "Bridge crashed: ..."), with the
traceback on stderr, and exits 1. The TikTok unfollow bridge caught it first and wrote "Startup
error: ..." in the same shape with the same exit: a second way to say the same crash
(`scripts/audits/audit_bridge_error_lines.py` lists the handlers of that kind that remain).
"""

from __future__ import annotations

import pytest

from bridges.common.entrypoint import CRASH, DEFAULT_MESSAGES

CRASHED = DEFAULT_MESSAGES[CRASH].format(error="")


@pytest.mark.parametrize("bridge, config, cause", [
    # The payload's `config` is no object: the run fails on its first line, before any phone.
    pytest.param("tiktok_unfollow_bridge", {"device_id": "gate-phone", "config": "not an object"},
                 "TypeError: 'str' object does not support item assignment", id="tiktok-unfollow"),
])
def test_the_entry_says_the_crash_of_the_run(tmp_path, run_bridge_process, bridge, config, cause):
    proc, errors = run_bridge_process(bridge, config)

    stderr = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 1, stderr[-3000:]
    assert [error["error"] for error in errors] == [CRASHED + cause.split(": ", 1)[1]], stderr[-3000:]
    assert "Bridge crashed" in stderr and cause in stderr
    assert not (tmp_path / "taktik-data.db").exists()


@pytest.mark.parametrize("raised, said", [
    pytest.param(RuntimeError("the router broke"), {"error": CRASHED + "the router broke"}, id="crash"),
    pytest.param(ModuleNotFoundError("No module named 'gate'", name="gate"),
                 {"error": "ModuleNotFoundError: No module named 'gate'", "error_code": "PYTHON_IMPORT_ERROR"},
                 id="import"),
])
def test_the_tiktok_dispatcher_leaves_a_crash_to_the_entry_and_still_stops_tiktok(
        tmp_path, monkeypatch, raised, said):
    """The dispatcher wrote "Workflow error: ..." beside the entry's CRASH line, same shape, same exit,
    and said an import as the entry does. Run in the process: its cleanup stops TikTok over adb,
    which a test does not reach."""
    import sys

    from bridges.common import bridge_base, entrypoint
    from bridges.tiktok.automation import dispatcher

    config_path = tmp_path / "config.json"
    config_path.write_text('{"workflowType": "followers", "deviceId": "gate-phone"}', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["tiktok_bridge", str(config_path)])
    lines = []
    for ipc in (entrypoint._ipc, bridge_base._ipc):
        monkeypatch.setattr(ipc, "send", lambda msg_type, **data: lines.append({"type": msg_type, **data}))
    stopped = []
    monkeypatch.setattr(dispatcher, "reset_network_if_enabled", lambda config, device_id: True)
    monkeypatch.setattr(dispatcher, "force_stop_tiktok", stopped.append)

    def broken_router(config):
        raise raised

    monkeypatch.setattr(dispatcher, "dispatch_tiktok_workflow", broken_router)

    with pytest.raises(SystemExit) as exit_:
        entrypoint.run_bridge_main(dispatcher.TikTokDispatcherBridge, usage="tiktok_bridge <config_path>")

    assert exit_.value.code == 1
    errors = [line for line in lines if line["type"] == "error"]
    assert [{key: error[key] for key in said} for error in errors] == [said]
    assert stopped == ["gate-phone"]
