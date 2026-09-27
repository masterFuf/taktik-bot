"""The duplicated-lines gate: a copy turns it red, what is not code is left out, a count never goes back up.

The fake trees live in the gate itself (`self_test_cases`), so the rules and their proofs stay together.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_duplicates as audit  # noqa: E402
import ratchet  # noqa: E402

CASES = audit.self_test_cases()


@pytest.mark.parametrize("name", CASES)
def test_each_fake_tree_is_judged_as_expected(name):
    tree, expected = CASES[name]
    counts, unreadable = audit.judge(tree)
    assert unreadable == []
    assert (expected in counts) if expected else counts == {}


def _helper(name: str) -> str:
    body = "".join(f"    total = total + value_{n} * {n}\n" for n in range(audit.WINDOW))
    return f"def {name}(total):\n{body}    return total\n"


def test_a_copy_is_reported_at_its_full_length_with_its_places():
    files = {"a.py": audit.python_lines(_helper("helper")),
             "b.py": audit.python_lines("x = 1\n\n" + _helper("other"))}
    copies = audit.Detector(files).copies()
    # The eight body lines and the return: the `def` lines differ.
    assert copies == [audit.Copy(audit.WINDOW + 1, (("a.py", 2, 10), ("b.py", 4, 12)))]


def test_the_count_of_a_file_is_its_significant_lines_under_a_copy():
    counts, _ = audit.judge({"a.py": _helper("helper"), "b.py": "x = 1\n" + _helper("other")})
    assert counts == {"a.py": audit.WINDOW + 1, "b.py": audit.WINDOW + 1}


def _gate(tmp_path, tree, *argv):
    source = tmp_path / "src"
    source.mkdir(exist_ok=True)
    for path in source.iterdir():
        path.unlink()
    for path, text in tree.items():
        (source / path).write_text(text, encoding="utf-8")
    baseline = tmp_path / "baseline.json"
    code = audit.main(["--root", str(tmp_path), "--scan", "src", "--baseline", str(baseline),
                       "--command", "npm run duplicates", *argv])
    return code, json.loads(baseline.read_text()) if baseline.exists() else None


def test_another_tree_with_its_own_baseline(tmp_path, capsys):
    copied = {"a.ts": "x = 1\n" + _helper("helper"), "b.ts": _helper("helper")}
    # The def line, the eight body lines and the return.
    assert _gate(tmp_path, copied, "--update-baseline") == (0, {"src/a.ts": 10, "src/b.ts": 10})
    assert _gate(tmp_path, copied)[0] == 0
    # A third copy: a file absent from the baseline.
    assert _gate(tmp_path, {**copied, "c.ts": _helper("helper")})[0] == 1
    assert "src/c.ts: 10 duplicated line(s), file absent from the baseline" in capsys.readouterr().out
    # One copy removed: the decrease must be recorded.
    assert _gate(tmp_path, {"a.ts": copied["a.ts"]})[0] == 1
    assert "Lower the baseline: npm run duplicates --update-baseline" in capsys.readouterr().out
    assert _gate(tmp_path, {"a.ts": copied["a.ts"]}, "--update-baseline") == (0, {})


def test_an_unreadable_file_is_named_and_turns_the_gate_red(tmp_path, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "bad.py").write_bytes(b"x = '\xff\xfe'\n")
    code = audit.main(["--root", str(tmp_path), "--scan", "src", "--baseline", str(tmp_path / "b.json")])
    assert code == 1
    assert "src/bad.py: unreadable" in capsys.readouterr().out


def test_the_engine_matches_its_baseline():
    files, unreadable = audit.read_tree(audit.ROOT, audit.SCAN_ROOTS)
    failures, stale = ratchet.compare(audit.Detector(files).counts(), ratchet.load_baseline(audit.BASELINE),
                                      audit.NOUN)
    assert unreadable == []
    assert failures == []
    assert stale == []
