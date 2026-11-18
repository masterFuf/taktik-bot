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


@pytest.fixture
def lock_environment(monkeypatch):
    """main() run as in an environment of the lock: these tests judge pyright's report, not the packages."""
    monkeypatch.setattr(audit, "environment_drift", lambda root=audit.ROOT: [])


def test_a_pin_counts_only_where_its_marker_holds_and_a_later_file_wins():
    lock = ("# generated\nadbutils==2.12.0\n    # via uiautomator2\n"
            "colorama==0.4.6 ; sys_platform == 'nobody-runs-this'\nmitmproxy==11.0.2\n")
    media = "# optional\nmitmproxy==12.3.1\n"
    pins = audit.pinned_versions({"requirements.lock": lock, "requirements-media.txt": media})
    assert pins == {"adbutils": ("2.12.0", "requirements.lock:2"),
                    "mitmproxy": ("12.3.1", "requirements-media.txt:2")}


def test_a_line_that_is_not_an_exact_pin_is_refused():
    with pytest.raises(ValueError, match="requirements.lock:1 is not an exact pin"):
        audit.pinned_versions({"requirements.lock": "sqlalchemy>=2.0\n"})


def test_a_package_at_another_version_or_missing_is_a_drift():
    pins = {"adbutils": ("2.12.0", "requirements.lock:3"), "sqlalchemy": ("2.0.55", "requirements.lock:128"),
            "pyyaml": ("6.0.3", "requirements.lock:111")}
    drift = audit.version_drift(pins, {"adbutils": "2.9.3", "pyyaml": "6.0.3", "unpinned": "1.0"})
    assert drift == [f"adbutils==2.12.0 (requirements.lock:3): 2.9.3 installed in {sys.executable}",
                     f"sqlalchemy==2.0.55 (requirements.lock:128): not installed in {sys.executable}"]


def test_a_drift_is_red_and_pyright_is_not_run(monkeypatch, capsys):
    # adbutils 2.9.3 and SQLAlchemy 1.4.54 typed adb.py, orm/engine.py and validate_entities.py with one
    # error each, files absent from the baseline: the gate accused code nobody had touched.
    monkeypatch.setattr(audit, "environment_drift", lambda root=audit.ROOT: ["sqlalchemy==2.0.55: 1.4.54 installed"])

    def pyright_must_not_run():
        raise AssertionError("pyright ran in an environment that is not the lock")

    monkeypatch.setattr(audit, "find_pyright", pyright_must_not_run)
    assert audit.main([]) == 1
    out = capsys.readouterr().out
    assert "FAIL: sqlalchemy==2.0.55: 1.4.54 installed" in out
    assert "pyright not run" in out


def test_the_drift_is_read_from_the_engine_requirement_files(tmp_path):
    (tmp_path / "requirements.lock").write_text("a-package-nobody-installed==1.0\n", encoding="utf-8")
    (tmp_path / "requirements-media.txt").write_text("", encoding="utf-8")
    drift = audit.environment_drift(tmp_path)
    assert drift == [f"a-package-nobody-installed==1.0 (requirements.lock:1): not installed in {sys.executable}"]
    (tmp_path / "requirements-media.txt").unlink()
    assert "requirements-media.txt not found" in audit.environment_drift(tmp_path)[0]


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


def test_without_pyright_the_gate_is_red_and_says_how_to_get_it(monkeypatch, capsys, lock_environment):
    monkeypatch.setattr(audit, "find_pyright", lambda: None)
    assert audit.main([]) == 1
    out = capsys.readouterr().out
    assert "pyright not found" in out
    assert f"pip install pyright=={audit.PYRIGHT_VERSION}" in out


def test_another_version_of_pyright_is_red(monkeypatch, capsys, lock_environment):
    monkeypatch.setattr(audit, "find_pyright", lambda: "pyright")
    monkeypatch.setattr(audit, "pyright_version", lambda executable: "1.1.300")
    assert audit.main([]) == 1
    assert f"pyright 1.1.300 found, the gate counts with {audit.PYRIGHT_VERSION}" in capsys.readouterr().out


def test_the_gate_judges_the_counts_against_its_baseline(monkeypatch, tmp_path, capsys, lock_environment):
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
