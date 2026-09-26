"""`run_bridge_main`: the one entry of every bridge, a JSON config file named by the first argument."""
import json
import sys

import pytest

from bridges.common.runtime import entrypoint
from bridges.common.runtime.ipc import IPC


class _Bridge:
    seen = []
    code = 0

    def __init__(self, config):
        _Bridge.seen.append(config)

    def run(self):
        return _Bridge.code


class _Crashing:
    def __init__(self, config):
        pass

    def run(self):
        raise RuntimeError("boom")


@pytest.fixture
def events(monkeypatch):
    sent = []
    monkeypatch.setattr(IPC, "send", lambda _self, kind, **payload: sent.append((kind, payload)))
    _Bridge.seen = []
    _Bridge.code = 0
    return sent


def _run(monkeypatch, argv, factory=_Bridge, **kwargs):
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exit_info:
        entrypoint.run_bridge_main(factory, **kwargs)
    return exit_info.value.code


def _config_file(tmp_path, text):
    path = tmp_path / "config.json"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_the_config_file_is_the_config(monkeypatch, tmp_path, events):
    path = _config_file(tmp_path, json.dumps({"device_id": "emulator-5554", "config": {"max_unfollows": 3}}))
    _Bridge.code = 3

    assert _run(monkeypatch, ["bridge", path]) == 3
    assert _Bridge.seen == [{"device_id": "emulator-5554", "config": {"max_unfollows": 3}}]
    assert events == []
    assert entrypoint.loaded_config_path() == path


def test_a_bom_written_by_electron_is_read(monkeypatch, tmp_path, events):
    path = tmp_path / "config.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"deviceId": "a"}).encode("utf-8"))

    assert _run(monkeypatch, ["bridge", str(path)]) == 0
    assert _Bridge.seen == [{"deviceId": "a"}]


def test_no_file_is_the_usage_line(monkeypatch, events, capsys):
    assert _run(monkeypatch, ["bridge"], usage="x_bridge <config_path>") == 1
    assert json.loads(capsys.readouterr().out) == {"type": "error", "message": "Usage: x_bridge <config_path>"}
    assert _Bridge.seen == [] and events == []


def test_an_unreadable_file_is_an_error_event(monkeypatch, tmp_path, events):
    assert _run(monkeypatch, ["bridge", _config_file(tmp_path, "{not json")]) == 1
    assert events[0][0] == "error"
    assert events[0][1]["error"].startswith("Failed to load config:")
    assert _Bridge.seen == []


def test_a_config_that_is_not_an_object_is_refused(monkeypatch, tmp_path, events):
    assert _run(monkeypatch, ["bridge", _config_file(tmp_path, "[1, 2]")]) == 1
    assert events == [("error", {"error": "Failed to load config: the config must be a JSON object"})]
    assert _Bridge.seen == []


def test_a_bridge_reports_entry_errors_in_its_own_shape(monkeypatch, tmp_path, events):
    reported = []
    report = lambda message, reason: reported.append((reason, message))  # noqa: E731

    assert _run(monkeypatch, ["bridge"], report_error=report, usage="u") == 1
    assert _run(monkeypatch, ["bridge", str(tmp_path / "absent.json")], report_error=report) == 1
    assert _run(monkeypatch, ["bridge", _config_file(tmp_path, "{}")], factory=_Crashing, report_error=report) == 1

    assert [reason for reason, _ in reported] == [entrypoint.MISSING_CONFIG, entrypoint.CONFIG_ERROR, entrypoint.CRASH]
    assert reported[0][1] == "Usage: u"
    assert events == []


def test_without_catch_a_crash_goes_to_the_launcher_hooks(monkeypatch, tmp_path, events):
    monkeypatch.setattr(sys, "argv", ["bridge", _config_file(tmp_path, "{}")])
    with pytest.raises(RuntimeError, match="boom"):
        entrypoint.run_bridge_main(_Crashing, catch_crashes=False)
    assert events == []


def test_there_is_no_other_config_source():
    with pytest.raises(TypeError):
        entrypoint.run_bridge_main(_Bridge, config_source="stdin")
