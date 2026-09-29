"""The per-file ratchet shared by the counting gates: a count never goes back up, a decrease is recorded."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "audits"))

import ratchet  # noqa: E402

NOUN = "defect(s)"


def _ratchet(path):
    return ratchet.Ratchet(label="Defects", noun=NOUN, remedy="Fix it.",
                           command="python scripts/audit_x.py", baseline=path)


def test_a_file_above_its_count_is_red():
    failures, stale = ratchet.compare({"a.py": 3}, {"a.py": 2}, NOUN)
    assert failures == ["a.py: 3 defect(s), baseline 2"]
    assert stale == []


def test_a_new_file_with_the_defect_is_red():
    failures, _ = ratchet.compare({"a.py": 2, "b.py": 1}, {"a.py": 2}, NOUN)
    assert failures == ["b.py: 1 defect(s), file absent from the baseline"]


def test_a_decrease_not_recorded_in_the_baseline_is_red():
    failures, stale = ratchet.compare({"a.py": 1}, {"a.py": 2, "gone.py": 4}, NOUN)
    assert failures == []
    assert stale == ["a.py: baseline 2, actual 1", "gone.py: baseline 4, actual 0"]


def test_an_exact_baseline_is_green():
    assert ratchet.compare({"a.py": 2}, {"a.py": 2}, NOUN) == ([], [])


def _enforce(tmp_path, actual, baseline, update=False, other=()):
    path = tmp_path / "baseline.json"
    if baseline is not None:
        path.write_text(json.dumps(baseline), encoding="utf-8")
    code = ratchet.enforce(actual, _ratchet(path), update=update, other_failures=other)
    return code, json.loads(path.read_text()) if path.exists() else None


def test_the_verdict_is_red_on_a_rise_or_an_unrecorded_decrease_and_green_when_exact(tmp_path):
    assert _enforce(tmp_path, {"a.py": 3}, {"a.py": 2})[0] == 1
    assert _enforce(tmp_path, {"a.py": 1}, {"a.py": 2})[0] == 1
    assert _enforce(tmp_path, {"a.py": 2}, {"a.py": 2})[0] == 0


def test_a_finding_outside_the_count_is_red_and_blocks_the_update(tmp_path, capsys):
    assert _enforce(tmp_path, {"a.py": 2}, {"a.py": 2}, other=["b.py: unreadable"])[0] == 1
    assert "FAIL: b.py: unreadable" in capsys.readouterr().out
    code, baseline = _enforce(tmp_path, {"a.py": 1}, {"a.py": 2}, update=True, other=["b.py: unreadable"])
    assert (code, baseline) == (1, {"a.py": 2})


def test_update_records_a_decrease(tmp_path):
    assert _enforce(tmp_path, {"a.py": 1}, {"a.py": 2, "gone.py": 4}, update=True) == (0, {"a.py": 1})


def test_update_refuses_a_rise(tmp_path):
    assert _enforce(tmp_path, {"a.py": 3, "b.py": 1}, {"a.py": 2}, update=True) == (1, {"a.py": 2})


def test_update_freezes_the_state_only_when_there_is_no_baseline(tmp_path):
    assert _enforce(tmp_path, {"a.py": 3}, None, update=True) == (0, {"a.py": 3})


def test_the_files_read_skip_caches_and_dependencies(tmp_path):
    for name in ("pkg/a.py", "pkg/__pycache__/a.py", "pkg/node_modules/x/b.py", "pkg/c.txt"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("x = 1\n", encoding="utf-8")
    files = ratchet.source_files(tmp_path, ("pkg",), (".py",))
    assert [ratchet.relative(f, tmp_path) for f in files] == ["pkg/a.py"]


def test_a_missing_folder_or_an_unreadable_file_is_named(tmp_path):
    with pytest.raises(ratchet.UnreadableSource, match="nowhere"):
        ratchet.source_files(tmp_path, ("nowhere",), (".py",))
    bad = tmp_path / "bad.py"
    bad.write_bytes(b"x = '\xff\xfe\xfa'\n")
    with pytest.raises(ratchet.UnreadableSource, match="bad.py: unreadable"):
        ratchet.read_source(bad, tmp_path)
