"""A Cold DM run that fails says so: its final line, its exit code and its trace.

The bridge's last catch logged with `exc_info=True`, which loguru does not know: it formatted the
message with that keyword, and an error whose text holds braces (an HTTP body) raised KeyError out
of the logging call. The final `cold_dm_result` line was never printed, and the run left through
the bridge's entry as « Bridge crashed: '"error"' », the real error hidden behind a KeyError.
"""

import json

import pytest
from loguru import logger

from bridges.instagram.cold_dm import commands
from taktik.core.social_media.instagram.workflows.cold_dm import agent_handler


class ApiDown(RuntimeError):
    """The failure the Cold DM workflow meets."""


def test_a_failure_with_braces_in_its_text_prints_its_result_and_its_trace(monkeypatch, capsys):
    def failing(*args, **kwargs):
        raise ApiDown('HTTP 500: {"error": "busy"}')

    monkeypatch.setattr(agent_handler, "run_instagram_cold_dm", failing)
    kept = []
    sink = logger.add(lambda message: kept.append(message.record), level="ERROR")
    try:
        with pytest.raises(SystemExit) as exited:
            commands.run_cold_dm({"deviceId": "emulator-5554"})
    finally:
        logger.remove(sink)

    assert exited.value.code == 1
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    results = [line for line in lines if line.get("type") == "cold_dm_result"]
    assert results == [{"type": "cold_dm_result", "success": False, "error": 'HTTP 500: {"error": "busy"}'}]
    assert any(record["exception"] is not None and record["exception"].type is ApiDown for record in kept), \
        [record["message"] for record in kept]
