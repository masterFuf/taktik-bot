"""The leak guard refuses what the public repository must never carry, and nothing else.

Every guarded value here is invented and comes from a denylist written in the test. Clock times are
built by `_clock` so that this file does not carry one itself.
"""

import datetime as dt
import shutil
import subprocess
import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/hooks"))

import leak_guard  # noqa: E402

PARIS_SUMMER = dt.timezone(dt.timedelta(hours=2))
SATURDAY, MONDAY = dt.date(2026, 9, 26), dt.date(2026, 9, 28)
HANDLE, SERIAL = "demo.owner_handle", "ZZ9FAKESERIAL01"


def _clock(hour, minute):
    return f"{hour}" + ":" + f"{minute:02d}"


def _at(day, hour, minute=0):
    return dt.datetime.combine(day, dt.time(hour, minute), PARIS_SUMMER)


@pytest.fixture
def denylist(tmp_path):
    path = tmp_path / "denylist"
    path.write_text(f"# invented values\n{HANDLE}\n{SERIAL}  # a phone\n", encoding="utf-8")
    return leak_guard.load_denylist(CORE, [path])


def _scan(denylist, path, text):
    return leak_guard.scan_lines([leak_guard.AddedLine(path, 1, text)], denylist)


def test_a_denylisted_handle_is_refused(denylist):
    leaks = _scan(denylist, "taktik/example.py", f'OWNER = "@{HANDLE}"  # real account')
    assert [leak.where for leak in leaks] == ["taktik/example.py:1"]


def test_a_phone_serial_is_refused_even_inside_a_name(denylist):
    assert _scan(denylist, "tests/unit/test_x.py", f'CONFIG = "config_{SERIAL.lower()}.json"')
    assert leak_guard.scan_paths([f"config_{SERIAL}.json"], denylist)


def test_a_denylist_entry_can_be_a_digest(tmp_path):
    path = tmp_path / "denylist"
    guard = leak_guard.load_h8_guard(CORE)
    path.write_text(f"sha256:{guard._digest(HANDLE)}\n", encoding="utf-8")
    assert _scan(leak_guard.load_denylist(CORE, [path]), "README.md", f"by {HANDLE}")


def test_the_h8_digests_are_guarded_without_a_local_denylist(tmp_path):
    guard = leak_guard.load_h8_guard(CORE)
    digests = leak_guard.load_denylist(CORE, [tmp_path / "missing"]).digests
    assert set(guard._IN_TESTS) | set(guard._DEVICE_SERIALS) <= digests


def test_placeholders_versions_and_dates_pass(denylist):
    text = 'device = "emulator-5554"  # Instagram 410.0.0.53.71, captured 2026-09-28'
    assert _scan(denylist, "taktik/example.py", text) == []


def test_an_office_clock_time_is_refused(denylist):
    assert _scan(denylist, "tests/unit/test_dm.py", f'"timestamp": "{_clock(10, 29)}"')
    assert _scan(denylist, "taktik/example.py", f"# captured 2026-04-22T{_clock(16, 38)}")
    assert _scan(denylist, "taktik/example.py", f"# Jun 12, {_clock(3, 15)} PM")
    assert _scan(denylist, "taktik/example.py", f"# vu a {10}h{15}")


def test_night_clock_times_and_slices_pass(denylist):
    assert _scan(denylist, "taktik/example.py", f'label = "{_clock(21, 30)}"  # or {_clock(3, 0)} AM') == []
    assert _scan(denylist, "taktik/example.py", f"rows = items[{_clock(10, 15)}]") == []
    assert _scan(denylist, "taktik/example.py", "host = '127.0.0.1:5037'") == []


def test_the_anonymized_clock_of_a_fixture_passes(denylist):
    node = f'<node text="{_clock(12, 0)}" resource-id="{leak_guard.SYSTEM_CLOCK_ID}" />'
    assert _scan(denylist, "tests/unit/social_media/instagram/fixtures/ig410_feed.xml", node) == []
    other = f'<node text="{_clock(12, 0)}" resource-id="com.instagram.android:id/row" />'
    assert _scan(denylist, "tests/unit/social_media/tiktok/fixtures/tt_feed.xml", other) == []


def test_noon_outside_a_fixture_is_refused(denylist):
    assert _scan(denylist, "taktik/example.py", f'"{_clock(12, 0)}"')


def test_a_weekday_office_date_is_refused():
    leaks = leak_guard.commit_date_leaks({}, _at(MONDAY, 10), PARIS_SUMMER)
    assert [leak.where for leak in leaks] == ["author date", "committer date"]
    assert "GIT_AUTHOR_DATE" in leaks[0].fix and "GIT_COMMITTER_DATE" in leaks[0].fix


def test_saturday_office_hour_passes():
    assert leak_guard.commit_date_leaks({}, _at(SATURDAY, 10), PARIS_SUMMER) == []


def test_monday_night_passes():
    assert leak_guard.commit_date_leaks({}, _at(MONDAY, 3), PARIS_SUMMER) == []


def test_the_commit_dates_come_from_git_environment():
    night = int(_at(MONDAY, 3).timestamp())
    office = int(_at(MONDAY, 10).timestamp())
    environ = {"GIT_AUTHOR_DATE": f"@{night} +0200", "GIT_COMMITTER_DATE": f"@{office} +0200"}
    leaks = leak_guard.commit_date_leaks(environ, _at(SATURDAY, 3), PARIS_SUMMER)
    assert [leak.where for leak in leaks] == ["committer date"]


def test_git_date_formats_are_read():
    expected = _at(MONDAY, 3, 15)
    for value in (f"@{int(expected.timestamp())} +0200", f"2026-09-28T0{_clock(3, 15)}:00+02:00",
                  f"2026-09-28 0{_clock(3, 15)} +0200", f"Mon, 28 Sep 2026 0{_clock(3, 15)}:00 +0200"):
        assert leak_guard.parse_git_date(value) == expected, value


def test_the_commit_message_is_scanned_above_the_scissors(denylist):
    message = (f"Fix the inbox\n\n# a comment {_clock(10, 0)}\n"
               "# ------------------------ >8 ------------------------\n"
               f"+ diff line {HANDLE}\n")
    assert leak_guard.check_message(message, denylist) == []
    assert leak_guard.check_message(f"Seen by {HANDLE}\n", denylist)


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_the_staged_diff_is_read_end_to_end(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests" / "unit").mkdir(parents=True)
    shutil.copy(CORE / leak_guard.H8_GUARD, repo / leak_guard.H8_GUARD)
    (repo / leak_guard.DENYLIST_FILE).write_text(f"{HANDLE}\n", encoding="utf-8")
    _git(repo, "init", "-q")
    (repo / "notes.txt").write_text("kept\n", encoding="utf-8")
    _git(repo, "add", "notes.txt")
    denylist = leak_guard.load_denylist(repo, [repo / leak_guard.DENYLIST_FILE])

    assert leak_guard.check_staged(repo, denylist, {}, _at(SATURDAY, 10), PARIS_SUMMER) == []

    (repo / "notes.txt").write_text(f"kept\nby {HANDLE}\n", encoding="utf-8")
    _git(repo, "add", "notes.txt", leak_guard.DENYLIST_FILE)
    leaks = leak_guard.check_staged(repo, denylist, {}, _at(SATURDAY, 10), PARIS_SUMMER)
    denylist_file = leak_guard.DENYLIST_FILE
    assert sorted(leak.where for leak in leaks) == [denylist_file, f"{denylist_file}:1", "notes.txt:2"]


def _commit(repo, message):
    _git(repo, "commit", "-q", "--no-verify", "-m", message)


def _publish_on(repo, branch, files):
    _git(repo, "checkout", "-q", "-b", branch, "main")
    for name, content in files.items():
        (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", *files)
    _commit(repo, f"published on {branch}")
    _git(repo, "checkout", "-q", "main")


def _repo_in_a_merge(tmp_path, branches=("other",)):
    """A merge left open (MERGE_HEAD present) whose other parents already published a clock and a guarded name."""
    repo = tmp_path / "repo"
    (repo / "tests" / "unit").mkdir(parents=True)
    shutil.copy(CORE / leak_guard.H8_GUARD, repo / leak_guard.H8_GUARD)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Demo")
    _git(repo, "config", "user.email", "demo@example.invalid")
    (repo / "notes.txt").write_text("kept\n", encoding="utf-8")
    _git(repo, "add", "notes.txt", leak_guard.H8_GUARD)
    _commit(repo, "base")
    published = {
        "other": {"published.py": f'SEEN = "{_clock(10, 29)}"\n', f"notes_{SERIAL}.txt": "kept\n"},
        "third": {"third.py": f'SEEN = "{_clock(15, 10)}"\n'},
    }
    for branch in branches:
        _publish_on(repo, branch, published[branch])
    (repo / "notes.txt").write_text("kept\nmain side\n", encoding="utf-8")
    _git(repo, "add", "notes.txt")
    _commit(repo, "main side")
    _git(repo, "merge", "-q", "--no-ff", "--no-commit", *branches)
    denylist = tmp_path / "denylist"
    denylist.write_text(f"{HANDLE}\n{SERIAL}\n", encoding="utf-8")
    return repo, leak_guard.load_denylist(repo, [denylist])


def test_a_merge_does_not_refuse_what_a_parent_already_published(tmp_path):
    repo, denylist = _repo_in_a_merge(tmp_path)
    assert leak_guard.check_staged(repo, denylist, {}, _at(SATURDAY, 10), PARIS_SUMMER) == []


def test_a_leak_added_while_resolving_a_merge_is_refused(tmp_path):
    repo, denylist = _repo_in_a_merge(tmp_path)
    (repo / "notes.txt").write_text(f"kept\nmain side\nresolved at {_clock(11, 45)}\nby {HANDLE}\n",
                                    encoding="utf-8")
    (repo / "published.py").write_text(f'SEEN = "{_clock(10, 29)}"\nAGAIN = "{_clock(14, 5)}"\n',
                                       encoding="utf-8")
    (repo / f"extra_{SERIAL}.txt").write_text("new\n", encoding="utf-8")
    _git(repo, "add", "notes.txt", "published.py", f"extra_{SERIAL}.txt")
    leaks = leak_guard.check_staged(repo, denylist, {}, _at(SATURDAY, 10), PARIS_SUMMER)
    assert sorted(leak.where for leak in leaks) == [f"extra_{SERIAL}.txt", "notes.txt:3", "notes.txt:4",
                                                    "published.py:2"]


def test_the_date_of_a_merge_is_still_checked(tmp_path):
    repo, denylist = _repo_in_a_merge(tmp_path)
    leaks = leak_guard.check_staged(repo, denylist, {}, _at(MONDAY, 10), PARIS_SUMMER)
    assert [leak.where for leak in leaks] == ["author date", "committer date"]


def test_an_octopus_merge_reads_only_what_no_parent_published(tmp_path):
    repo, denylist = _repo_in_a_merge(tmp_path, branches=("other", "third"))
    assert leak_guard.check_staged(repo, denylist, {}, _at(SATURDAY, 10), PARIS_SUMMER) == []
    (repo / "third.py").write_text(f'SEEN = "{_clock(15, 10)}"\nAGAIN = "{_clock(9, 40)}"\n', encoding="utf-8")
    _git(repo, "add", "third.py")
    leaks = leak_guard.check_staged(repo, denylist, {}, _at(SATURDAY, 10), PARIS_SUMMER)
    assert [leak.where for leak in leaks] == ["third.py:2"]


def test_an_unreadable_merge_head_refuses_the_commit(tmp_path):
    repo, denylist = _repo_in_a_merge(tmp_path)
    (repo / ".git" / "MERGE_HEAD").write_text("not-a-commit\n", encoding="utf-8")
    with pytest.raises(subprocess.CalledProcessError):
        leak_guard.check_staged(repo, denylist, {}, _at(SATURDAY, 10), PARIS_SUMMER)
