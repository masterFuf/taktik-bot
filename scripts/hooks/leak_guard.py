"""Leak guard run by the pre-commit, pre-merge-commit and commit-msg hooks of this public repository.

It refuses a commit that would publish:

- a guarded word (handle of a real account, first name of the owner, serial of a real phone): the
  digests of `tests/unit/test_no_personal_handles.py` plus a local, untracked denylist;
- a clock time within office hours written in an added line or in the commit message;
- an author or committer date on a weekday within office hours.

Only added lines of the staged diff are read. While a merge is concluded (MERGE_HEAD present), a line
or a file name counts only if it is new against HEAD and against every merged commit: what a parent
already carries is published there. The commit dates are checked the same way for a merge.

The denylist is looked up, in this order and all merged: `$TAKTIK_LEAK_DENYLIST`,
`<worktree>/.leak-denylist`, `<git common dir>/leak-denylist`. One entry per line, `#` starts a
comment, an entry is either a plain value or `sha256:<hex>`.

Usage (from the hooks): `leak_guard.py pre-commit` or `leak_guard.py commit-msg <message file>`.
"""

from __future__ import annotations

import datetime as dt
import email.utils
import importlib.util
import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Iterable, Mapping, Optional

H8_GUARD = "tests/unit/test_no_personal_handles.py"
DENYLIST_FILE = ".leak-denylist"
DENYLIST_ENV = "TAKTIK_LEAK_DENYLIST"

OFFICE_FIRST_HOUR = 8
OFFICE_END_HOUR = 18
# Anonymized captures replace every clock with noon (scripts/anonymize_dump.py).
ANONYMIZED_CLOCK = (12, 0)
SYSTEM_CLOCK_ID = "com.android.systemui:id/clock"

_CLOCK = re.compile(
    r"(?:(?<=T)|(?<![\w.:+\[-]))"
    r"(?P<hour>[01]?\d|2[0-3])"
    r"(?:(?::(?P<minute>[0-5]\d)(?::[0-5]\d)?)|(?:\s?h\s?(?P<french_minute>[0-5]\d)))"
    r"(?!\d)"
    r"(?P<pm>\s?[pP]\.?[mM]\b)?"
)
_EPOCH_DATE = re.compile(r"^@?(?P<epoch>\d{9,})(?:\s+(?P<offset>[+-]\d{4}))?$")
_ISO_DATE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})[T ](?P<time>\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?)"
    r"\s*(?P<offset>Z|[+-]\d{2}:?\d{2})?$"
)
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class Leak:
    where: str
    what: str
    fix: str


@dataclass(frozen=True)
class AddedLine:
    path: str
    number: int
    text: str


@dataclass(frozen=True)
class Denylist:
    digests: frozenset
    guard: ModuleType

    def hits(self, text: str) -> list:
        lowered = text.lower()
        words = set(self.guard._WORD.findall(lowered)) | set(self.guard._SERIAL_WORD.findall(lowered))
        return sorted(word for word in words if self.guard._digest(word) in self.digests)


def load_h8_guard(core: pathlib.Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("taktik_h8_guard", core / H8_GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def denylist_paths(core: pathlib.Path, environ: Mapping[str, str], common_dir: Optional[pathlib.Path]) -> list:
    paths = []
    if environ.get(DENYLIST_ENV):
        paths.append(pathlib.Path(environ[DENYLIST_ENV]))
    paths.append(core / DENYLIST_FILE)
    if common_dir is not None:
        paths.append(common_dir / DENYLIST_FILE.lstrip("."))
    return paths


def load_denylist(core: pathlib.Path, paths: Iterable[pathlib.Path]) -> Denylist:
    guard = load_h8_guard(core)
    digests = set(guard._IN_TESTS) | set(guard._EVERYWHERE) | set(guard._DEVICE_SERIALS)
    for path in paths:
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            entry = raw.split("#", 1)[0].strip()
            if entry.lower().startswith("sha256:"):
                digests.add(entry[len("sha256:"):].strip().lower())
            elif entry:
                digests.add(guard._digest(entry.lower()))
    return Denylist(frozenset(digests), guard)


def parse_added_lines(diff: str) -> list:
    added, path, number = [], None, 0
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].rstrip("\t")
            path = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
        elif line.startswith("@@"):
            match = _HUNK.match(line)
            number = int(match.group("start")) if match else 0
        elif line.startswith("+") and path is not None:
            added.append(AddedLine(path, number, line[1:]))
            number += 1
    return added


def _is_anonymized_clock(path: str, text: str, hour: int, minute: int) -> bool:
    if (hour, minute) != ANONYMIZED_CLOCK:
        return False
    parts = pathlib.PurePosixPath(path).parts
    return SYSTEM_CLOCK_ID in text or ("tests" in parts and "fixtures" in parts)


def office_clock_times(path: str, text: str) -> list:
    found = []
    for match in _CLOCK.finditer(text):
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or match.group("french_minute"))
        if match.group("pm") and hour < 12:
            hour += 12
        if OFFICE_FIRST_HOUR <= hour < OFFICE_END_HOUR and not _is_anonymized_clock(path, text, hour, minute):
            found.append(match.group(0).strip())
    return found


def scan_lines(lines: Iterable[AddedLine], denylist: Denylist) -> list:
    leaks = []
    for line in lines:
        where = f"{line.path}:{line.number}"
        for word in denylist.hits(line.text):
            leaks.append(Leak(where, f"guarded word `{word}` (real handle, first name or phone serial)",
                              "replace it with an invented value (handle `demo_creator`, serial `emulator-5554`)"))
        for clock in office_clock_times(line.path, line.text):
            leaks.append(Leak(where, f"clock time `{clock}` within office hours",
                              "keep the date alone, or write an hour outside 8-18 h "
                              "(anonymized captures use noon, in tests/**/fixtures only)"))
    return leaks


def scan_paths(paths: Iterable[str], denylist: Denylist) -> list:
    leaks = []
    for path in paths:
        if pathlib.PurePosixPath(path).name == DENYLIST_FILE:
            leaks.append(Leak(path, "the local denylist is staged", f"unstage it: git rm --cached {path}"))
        for word in denylist.hits(path):
            leaks.append(Leak(path, f"guarded word `{word}` in a file name", "rename the file"))
    return leaks


def parse_git_date(value: str) -> dt.datetime:
    text = value.strip()
    epoch = _EPOCH_DATE.match(text)
    if epoch:
        offset = epoch.group("offset") or "+0000"
        sign = -1 if offset[0] == "-" else 1
        zone = dt.timezone(sign * dt.timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5])))
        return dt.datetime.fromtimestamp(int(epoch.group("epoch")), zone)
    iso = _ISO_DATE.match(text)
    if iso:
        offset = iso.group("offset") or ""
        if offset == "Z":
            offset = "+00:00"
        elif offset and ":" not in offset:
            offset = f"{offset[:3]}:{offset[3:]}"
        moment = dt.datetime.fromisoformat(f"{iso.group('date')}T{iso.group('time')}{offset}")
        return moment if moment.tzinfo else moment.astimezone()
    try:
        moment = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        moment = None
    if moment is None:
        raise ValueError(f"unreadable date: {value!r}")
    return moment if moment.tzinfo else moment.astimezone()


def is_office_hours(moment: dt.datetime) -> bool:
    return moment.weekday() < 5 and OFFICE_FIRST_HOUR <= moment.hour < OFFICE_END_HOUR


def commit_date_leaks(environ: Mapping[str, str], now: dt.datetime, local_zone: Optional[dt.tzinfo] = None) -> list:
    leaks = []
    for label, variable in (("author", "GIT_AUTHOR_DATE"), ("committer", "GIT_COMMITTER_DATE")):
        raw = environ.get(variable)
        try:
            moment = parse_git_date(raw) if raw else now
        except ValueError as error:
            leaks.append(Leak(variable, str(error), "write it as ISO 8601, with its offset"))
            continue
        local = moment.astimezone(local_zone) if local_zone else moment.astimezone()
        if is_office_hours(moment) or is_office_hours(local):
            leaks.append(Leak(f"{label} date", f"{local:%a %Y-%m-%d %H:%M %z} is a weekday within office hours",
                              _redate_hint(local)))
    return leaks


def _redate_hint(moment: dt.datetime) -> str:
    night = moment.replace(hour=OFFICE_FIRST_HOUR - 1, minute=moment.minute).isoformat(timespec="seconds")
    return (f"set both dates on an hour outside 8-18 h or on a weekend, e.g. "
            f"GIT_AUTHOR_DATE={night} GIT_COMMITTER_DATE={night} git commit ...")


def check_message(text: str, denylist: Denylist) -> list:
    lines = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.startswith("# ") and ">8" in line:
            break
        if not line.startswith("#"):
            lines.append(AddedLine("commit message", number, line))
    return scan_lines(lines, denylist)


def _git(core: pathlib.Path, *args: str) -> str:
    result = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=core, check=True,
                            capture_output=True)
    return result.stdout.decode("utf-8", errors="replace")


def _common_dir(core: pathlib.Path) -> pathlib.Path:
    return (core / _git(core, "rev-parse", "--git-common-dir").strip()).resolve()


def merge_heads(core: pathlib.Path) -> list:
    """The commits being merged (several for an octopus), none outside a merge."""
    path = core / _git(core, "rev-parse", "--git-path", "MERGE_HEAD").strip()
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").split()


def _staged_added_lines(core: pathlib.Path, base: Optional[str] = None) -> list:
    against = [base] if base else []
    return parse_added_lines(_git(core, "diff", "--cached", "--no-color", "--no-ext-diff", "--unified=0",
                                  "--diff-filter=ACMR", *against))


def _staged_paths(core: pathlib.Path, base: Optional[str] = None) -> list:
    against = [base] if base else []
    return _git(core, "diff", "--cached", "--name-only", "--diff-filter=ACMR", *against).splitlines()


def check_staged(core: pathlib.Path, denylist: Denylist, environ: Mapping[str, str], now: dt.datetime,
                 local_zone: Optional[dt.tzinfo] = None) -> list:
    lines, paths = _staged_added_lines(core), _staged_paths(core)
    # A merge publishes only what no parent already carries: the lines written while resolving it.
    for head in merge_heads(core):
        new_lines = {(line.path, line.number) for line in _staged_added_lines(core, head)}
        new_paths = set(_staged_paths(core, head))
        lines = [line for line in lines if (line.path, line.number) in new_lines]
        paths = [path for path in paths if path in new_paths]
    return scan_paths(paths, denylist) + scan_lines(lines, denylist) + commit_date_leaks(environ, now, local_zone)


def report(leaks: list) -> str:
    lines = ["leak guard: commit refused, this repository is public."]
    for leak in leaks:
        lines.append(f"  - {leak.where}: {leak.what}\n    fix: {leak.fix}")
    return "\n".join(lines)


def main(argv: list) -> int:
    hook = argv[0] if argv else "pre-commit"
    core = pathlib.Path(_git(pathlib.Path.cwd(), "rev-parse", "--show-toplevel").strip())
    if not (core / H8_GUARD).is_file():
        print(f"leak guard: {H8_GUARD} missing, commit refused (merge the branch that adds it).", file=sys.stderr)
        return 1
    paths = denylist_paths(core, os.environ, _common_dir(core))
    if not any(path.is_file() for path in paths):
        print(f"leak guard: no local denylist ({DENYLIST_FILE}), only the digests of {H8_GUARD} are checked.",
              file=sys.stderr)
    denylist = load_denylist(core, paths)
    if hook == "commit-msg":
        message = pathlib.Path(argv[1]).read_text(encoding="utf-8", errors="replace")
        leaks = check_message(message, denylist)
    else:
        leaks = check_staged(core, denylist, os.environ, dt.datetime.now().astimezone())
    if leaks:
        print(report(leaks), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
