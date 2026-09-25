"""`run_bridge_main` also serves the bridges that receive their payload as one JSON line on stdin."""
import io
import json
import sys

import pytest

from bridges.common.runtime import entrypoint
from bridges.common.runtime.ipc import IPC


class _Bridge:
    seen = []

    def __init__(self, config):
        _Bridge.seen.append(config)

    def run(self):
        return 0


@pytest.fixture
def events(monkeypatch):
    sent = []
    monkeypatch.setattr(IPC, "send", lambda _self, kind, **payload: sent.append((kind, payload)))
    _Bridge.seen = []
    return sent


def _run(monkeypatch, stdin_text, **kwargs):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    monkeypatch.setattr(sys, "argv", ["bridge"])
    with pytest.raises(SystemExit) as exit_info:
        entrypoint.run_bridge_main(_Bridge, config_source="stdin", **kwargs)
    return exit_info.value.code


def test_one_json_line_on_stdin_is_the_config(monkeypatch, events):
    code = _run(monkeypatch, json.dumps({"device_id": "emulator-5554", "config": {"max_unfollows": 3}}) + "\n")

    assert code == 0
    assert _Bridge.seen == [{"device_id": "emulator-5554", "config": {"max_unfollows": 3}}]
    assert events == []


def test_an_empty_stdin_is_an_error_event(monkeypatch, events):
    assert _run(monkeypatch, "") == 1
    assert events == [("error", {"error": "No config received from stdin"})]
    assert _Bridge.seen == []


def test_a_malformed_line_is_an_error_event(monkeypatch, events):
    assert _run(monkeypatch, "{not json\n") == 1
    assert events[0][0] == "error"
    assert events[0][1]["error"].startswith("Invalid JSON config:")


def test_an_unknown_source_is_a_programming_error(monkeypatch):
    with pytest.raises(ValueError):
        entrypoint.run_bridge_main(_Bridge, config_source="env")
