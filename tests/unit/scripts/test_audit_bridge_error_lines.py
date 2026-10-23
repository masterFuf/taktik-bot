"""The bridge error-line ratchet names each broad handler that words its own `error` line, and never
goes back up."""

import json
import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_bridge_error_lines as audit  # noqa: E402
import ratchet  # noqa: E402


def _keys(source: str):
    return [finding.key for finding in audit.scan_source(source, "b.py")]


@pytest.mark.parametrize("source", [
    "try:\n    f()\nexcept Exception as e:\n    send_error(f'Startup error: {e}')",
    "try:\n    f()\nexcept:\n    send_error('boom')",
    "try:\n    f()\nexcept (ValueError, Exception) as e:\n    send_error(str(e))",
    "try:\n    f()\nexcept Exception as e:\n    _ipc.error(f'Init failed: {e}')",
    "try:\n    f()\nexcept Exception as e:\n    self.ipc.error(str(e), error_code='X')",
    "try:\n    f()\nexcept Exception as e:\n    ipc.send('error', error=str(e))",
    "try:\n    f()\nexcept Exception as e:\n    send_message('error', error=str(e))",
    "try:\n    f()\nexcept Exception as e:\n    emit({'type': 'error', 'message': str(e)})",
    "try:\n    f()\nexcept Exception as e:\n    print(json.dumps({'type': 'error', 'error': str(e)}))",
    # A log line beside it does not make it shared.
    "try:\n    f()\nexcept Exception as e:\n    logger.exception('x')\n    send_error(str(e))",
])
def test_a_broad_handler_that_words_its_own_line_is_counted(source):
    assert _keys(source) == ["b.py::<module>"]


@pytest.mark.parametrize("source", [
    # The shared functions and the bridge's emitter.
    "try:\n    f()\nexcept Exception as e:\n    send_import_error(e)",
    "try:\n    f()\nexcept Exception as e:\n    _ipc.send('error', **exception_event(type(e), e, e.__traceback__))",
    "try:\n    f()\nexcept Exception as e:\n    send_instagram_workflow_error(e)",
    "try:\n    f()\nexcept Exception as e:\n    emit_dm_error(str(e))",
    "try:\n    f()\nexcept Exception as e:\n    report(CRASH, e)",
    # A log is not a line for the app.
    "try:\n    f()\nexcept Exception as e:\n    logger.error(f'failed: {e}')",
    "try:\n    f()\nexcept Exception:\n    raise",
    # Another line type.
    "try:\n    f()\nexcept Exception as e:\n    ipc.send('status', status='error')",
    # A targeted handler is the import gate's business, not this one's.
    "try:\n    f()\nexcept ValueError as e:\n    send_error(str(e))",
    # Emitting from a nested function is not this handler's line.
    "try:\n    f()\nexcept Exception as e:\n    def later():\n        send_error(str(e))",
])
def test_a_handler_that_goes_through_a_shared_function_is_not_counted(source):
    assert _keys(source) == []


def test_the_handler_is_named_by_its_file_and_its_function():
    source = (
        "class Bridge:\n"
        "    def run(self):\n"
        "        try:\n            f()\n        except Exception as e:\n            send_error(str(e))\n"
        "        try:\n            g()\n        except Exception as e:\n            send_error(str(e))\n"
        "def run_workflow():\n"
        "    def step():\n"
        "        try:\n            f()\n        except Exception as e:\n            send_error(str(e))\n"
    )
    assert _keys(source) == ["b.py::Bridge.run", "b.py::Bridge.run", "b.py::run_workflow.step"]


def _bridge_tree(root, body: str):
    """The counts of a tree whose one bridge file is `body`, read from disk like the real one."""
    (root / "bridges").mkdir(parents=True)
    (root / "bridges" / "unfollow.py").write_text(body, encoding="utf-8")
    return audit.scan_repository(root)


def test_a_handler_added_to_a_bridge_turns_the_gate_red(monkeypatch, tmp_path, capsys):
    clean = "def run():\n    try:\n        f()\n    except ImportError as e:\n        send_import_error(e)\n"
    added = clean + "    except Exception as e:\n        send_error(f'Startup error: {e}')\n"
    before = _bridge_tree(tmp_path / "before", clean)
    after = _bridge_tree(tmp_path / "after", added)
    baseline = tmp_path / "baseline.json"
    baseline.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(audit, "BASELINE", baseline)

    monkeypatch.setattr(audit, "scan_repository", lambda: before)
    assert audit.main([]) == 0

    monkeypatch.setattr(audit, "scan_repository", lambda: after)
    assert audit.main([]) == 1
    assert "bridges/unfollow.py::run: 1 handler(s) wording its own error line" in capsys.readouterr().out


def _run(monkeypatch, tmp_path, actual, baseline, *argv):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(audit, "BASELINE", path)
    monkeypatch.setattr(audit, "scan_repository", lambda: dict(actual))
    return audit.main(list(argv)), json.loads(path.read_text())


def test_the_list_only_goes_down(monkeypatch, tmp_path):
    key = "bridges/a.py::run"
    assert _run(monkeypatch, tmp_path, {key: 2}, {key: 1})[0] == 1
    assert _run(monkeypatch, tmp_path, {}, {key: 1})[0] == 1
    assert _run(monkeypatch, tmp_path, {key: 1}, {key: 1})[0] == 0
    assert _run(monkeypatch, tmp_path, {}, {key: 1}, "--update-baseline") == (0, {})
    assert _run(monkeypatch, tmp_path, {key: 2}, {key: 1}, "--update-baseline") == (1, {key: 1})


def test_the_bridges_match_their_list():
    failures, stale = ratchet.compare(audit.scan_repository(), ratchet.load_baseline(audit.BASELINE),
                                      "handler(s)", "function")
    assert failures == []
    assert stale == []
