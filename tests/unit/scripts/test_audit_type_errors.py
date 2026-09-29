"""The type-error gate: pyright's errors per file never go back up, and the gate is never green by absence.

The reading of pyright's report is tested on a report written here; pyright itself runs in the gate's
self-test (a throwaway tree, the engine's own configuration), played below when pyright is installed.
"""

import sys
from pathlib import Path

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_type_errors as audit  # noqa: E402

ROOT = Path("C:/engine") if sys.platform == "win32" else Path("/engine")


def _diagnostic(path, message, rule="reportAttributeAccessIssue", severity="error", line=4):
    return {"file": str(ROOT / path), "severity": severity, "message": message, "rule": rule,
            "range": {"start": {"line": line, "character": 0}, "end": {"line": line, "character": 1}}}


def _report(*diagnostics, analysed=3):
    return {"version": audit.PYRIGHT_VERSION, "summary": {"filesAnalyzed": analysed},
            "generalDiagnostics": list(diagnostics)}


def test_errors_are_counted_per_file_and_warnings_are_not():
    report = _report(
        _diagnostic("taktik/a.py", 'Cannot access attribute "x" for class "A"'),
        _diagnostic("taktik/a.py", 'Argument of type "str" cannot be assigned', rule="reportArgumentType"),
        _diagnostic("bridges/b.py", '"y" is possibly unbound', rule="reportPossiblyUnbound"),
        _diagnostic("taktik/a.py", '"z" is specified in __all__', severity="warning"),
    )
    reading = audit.read_report(report, ROOT)
    assert reading.counts == {"taktik/a.py": 2, "bridges/b.py": 1}
    assert reading.environment == []
    assert reading.rules == {"reportAttributeAccessIssue": 1, "reportArgumentType": 1, "reportPossiblyUnbound": 1}


def test_a_relative_import_that_does_not_resolve_is_an_error_of_the_code():
    report = _report(_diagnostic("taktik/a.py", 'Import "...atomic.navigation" could not be resolved',
                                 rule="reportMissingImports"))
    reading = audit.read_report(report, ROOT)
    assert reading.counts == {"taktik/a.py": 1}
    assert reading.environment == []


def test_an_absolute_import_that_does_not_resolve_is_an_incomplete_environment_not_a_count():
    report = _report(_diagnostic("taktik/a.py", 'Import "uiautomator2" could not be resolved',
                                 rule="reportMissingImports", line=9))
    reading = audit.read_report(report, ROOT)
    assert reading.counts == {}
    assert reading.environment == ['taktik/a.py:10 Import "uiautomator2" could not be resolved']


def test_a_report_that_analysed_nothing_is_red():
    reading = audit.read_report(_report(analysed=0), ROOT)
    assert reading.failures() and "analysed no file" in reading.failures()[0]


def test_without_pyright_the_gate_is_red_and_says_how_to_get_it(monkeypatch, capsys):
    monkeypatch.setattr(audit, "find_pyright", lambda: None)
    assert audit.main([]) == 1
    out = capsys.readouterr().out
    assert "pyright not found" in out
    assert f"pip install pyright=={audit.PYRIGHT_VERSION}" in out


def test_another_version_of_pyright_is_red(monkeypatch, capsys):
    monkeypatch.setattr(audit, "find_pyright", lambda: "pyright")
    monkeypatch.setattr(audit, "pyright_version", lambda executable: "1.1.300")
    assert audit.main([]) == 1
    assert f"pyright 1.1.300 found, the gate counts with {audit.PYRIGHT_VERSION}" in capsys.readouterr().out


def test_the_gate_judges_the_counts_against_its_baseline(monkeypatch, tmp_path, capsys):
    baseline = tmp_path / "baseline.json"
    baseline.write_text('{"taktik/a.py": 2}', encoding="utf-8")
    monkeypatch.setattr(audit, "BASELINE", baseline)
    monkeypatch.setattr(audit, "find_pyright", lambda: "pyright")
    monkeypatch.setattr(audit, "pyright_version", lambda executable: audit.PYRIGHT_VERSION)

    def with_errors(count):
        report = _report(*[_diagnostic("taktik/a.py", f"error {n}") for n in range(count)])
        monkeypatch.setattr(audit, "run_pyright", lambda executable, root: audit.read_report(report, ROOT))
        return audit.main([])

    assert with_errors(3) == 1  # a new error
    assert "taktik/a.py: 3 type error(s), baseline 2" in capsys.readouterr().out
    assert with_errors(1) == 1  # a decrease not recorded
    assert "Lower the baseline: python scripts/audits/audit_type_errors.py --update-baseline" in capsys.readouterr().out
    assert with_errors(2) == 0  # the baseline up to date

    # The counts match, but a module did not resolve: the counts themselves are in doubt.
    report = _report(_diagnostic("taktik/a.py", "error 0"), _diagnostic("taktik/a.py", "error 1"),
                     _diagnostic("taktik/b.py", 'Import "loguru" could not be resolved', rule="reportMissingImports"))
    monkeypatch.setattr(audit, "run_pyright", lambda executable, root: audit.read_report(report, ROOT))
    assert audit.main([]) == 1
    assert 'taktik/b.py:5 Import "loguru" could not be resolved' in capsys.readouterr().out


def test_pyright_on_a_throwaway_tree_turns_the_gate_red_when_it_should():
    if audit.find_pyright() is None:
        pytest.skip(f"pyright not installed: {audit.INSTALL}")
    assert audit.self_test() == 0
