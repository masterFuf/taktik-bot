"""The swallowed-error ratchet counts broad handlers that say nothing, and never goes back up."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_swallowed_errors as audit  # noqa: E402


def _count(source: str) -> int:
    return len(audit.scan_source(source))


@pytest.mark.parametrize("source", [
    "try:\n    f()\nexcept Exception:\n    pass",
    "try:\n    f()\nexcept:\n    pass",
    "try:\n    f()\nexcept BaseException:\n    pass",
    "try:\n    f()\nexcept (ValueError, Exception):\n    pass",
    "for x in y:\n    try:\n        f()\n    except Exception:\n        continue",
    "def g():\n    try:\n        return f()\n    except Exception:\n        return None",
    # A default value dressed as a measure says nothing either.
    "def g():\n    try:\n        return f()\n    except Exception:\n        return 0",
    # A bound exception never read is still swallowed.
    "try:\n    f()\nexcept Exception as exc:\n    pass",
    # Logging inside a nested function does not report this handler.
    "try:\n    f()\nexcept Exception:\n    def later():\n        logger.error('x')",
    # A method named like a log level on something that is not a logger.
    "try:\n    f()\nexcept Exception:\n    dialog.info()",
])
def test_a_broad_handler_that_says_nothing_is_counted(source):
    assert _count(source) == 1


@pytest.mark.parametrize("source", [
    "try:\n    f()\nexcept Exception:\n    logger.warning('f failed')",
    "try:\n    f()\nexcept Exception:\n    self.logger.debug('f failed')",
    "try:\n    f()\nexcept Exception:\n    logging.exception('f failed')",
    "try:\n    f()\nexcept Exception:\n    warnings.warn('f failed')",
    "try:\n    f()\nexcept Exception:\n    print('f failed', file=sys.stderr)",
    "try:\n    f()\nexcept Exception:\n    traceback.print_exc()",
    "try:\n    f()\nexcept Exception:\n    _log('error', 'f failed')",
    "try:\n    f()\nexcept Exception:\n    notifier.error('f failed')",
    "try:\n    f()\nexcept Exception:\n    raise",
    "try:\n    f()\nexcept Exception as exc:\n    raise RuntimeError('f') from exc",
    "try:\n    f()\nexcept Exception:\n    if x:\n        logger.error('f failed')",
    # The error is carried on: the marked failure value.
    "def g():\n    try:\n        f()\n    except Exception as exc:\n        return {'success': False, 'error': str(exc)}",
    # A targeted exception is a decision, admitted even with pass.
    "try:\n    f()\nexcept ValueError:\n    pass",
    "try:\n    f()\nexcept (KeyError, IndexError):\n    pass",
])
def test_a_handler_that_reports_or_is_targeted_is_not_counted(source):
    assert _count(source) == 0


def test_the_line_of_the_handler_is_reported():
    findings = audit.scan_source("x = 1\ntry:\n    f()\nexcept Exception:\n    pass\n", "a.py")
    assert findings == [audit.Finding("a.py", 4)]


def test_a_file_above_its_count_is_red():
    failures, stale = audit.compare({"a.py": 3}, {"a.py": 2})
    assert failures == ["a.py: 3 swallowed error(s), baseline 2"]
    assert stale == []


def test_a_new_file_that_swallows_is_red():
    failures, _ = audit.compare({"a.py": 2, "b.py": 1}, {"a.py": 2})
    assert failures == ["b.py: 1 swallowed error(s), file absent from the baseline"]


def test_a_decrease_not_recorded_in_the_baseline_is_red():
    failures, stale = audit.compare({"a.py": 1}, {"a.py": 2, "gone.py": 4})
    assert failures == []
    assert stale == ["a.py: baseline 2, actual 1", "gone.py: baseline 4, actual 0"]


def test_an_exact_baseline_is_green():
    assert audit.compare({"a.py": 2}, {"a.py": 2}) == ([], [])


def _run(monkeypatch, tmp_path, actual, baseline, *argv):
    path = tmp_path / "baseline.json"
    if baseline is not None:
        path.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(audit, "BASELINE", path)
    monkeypatch.setattr(audit, "scan_repository", lambda: dict(actual))
    code = audit.main(list(argv))
    return code, json.loads(path.read_text()) if path.exists() else None


def test_the_gate_exits_red_on_an_increase_and_green_when_exact(monkeypatch, tmp_path):
    assert _run(monkeypatch, tmp_path, {"a.py": 3}, {"a.py": 2})[0] == 1
    assert _run(monkeypatch, tmp_path, {"a.py": 1}, {"a.py": 2})[0] == 1
    assert _run(monkeypatch, tmp_path, {"a.py": 2}, {"a.py": 2})[0] == 0


def test_update_baseline_records_a_decrease(monkeypatch, tmp_path):
    code, baseline = _run(monkeypatch, tmp_path, {"a.py": 1}, {"a.py": 2, "gone.py": 4},
                          "--update-baseline")
    assert code == 0
    assert baseline == {"a.py": 1}


def test_update_baseline_refuses_an_increase(monkeypatch, tmp_path):
    code, baseline = _run(monkeypatch, tmp_path, {"a.py": 3, "b.py": 1}, {"a.py": 2},
                          "--update-baseline")
    assert code == 1
    assert baseline == {"a.py": 2}


def test_the_repository_matches_its_baseline():
    failures, stale = audit.compare(audit.scan_repository(), audit.load_baseline())
    assert failures == []
    assert stale == []
