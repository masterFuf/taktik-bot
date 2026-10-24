"""A bridge whose run has nothing to add to an exception lets it rise to `run_bridge_main`.

The entry says it once, on the contract's `error` line (`CRASH`, "Bridge crashed: ...", the code
`UNHANDLED_EXCEPTION` and the traceback, on the line and on stderr), and exits 1. The TikTok unfollow bridge caught it first and wrote "Startup
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
    # The code and the traceback the launcher's crash hooks would give the same exception.
    assert errors[0].get("error_code") == "UNHANDLED_EXCEPTION", errors
    assert errors[0].get("traceback", "").rstrip().endswith(cause), errors
    assert "Bridge crashed" in stderr and cause in stderr
    assert not (tmp_path / "taktik-data.db").exists()
