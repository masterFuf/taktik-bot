"""A per-file ratchet: the count of a defect in each file may only go down. One mechanism for the
counting gates (swallowed errors, type errors, duplicated lines).

A gate counts one kind of defect per file (or per folder: the `.py` files a folder holds, for the
tree gate) and keeps a baseline, a JSON object `{path: count}` frozen the day the gate was laid.
The gate is red when:

* a file exceeds its count;
* a file absent from the baseline has the defect;
* a count in the baseline is higher than reality: lower the baseline in the same change, so that
  it never leaves room for a new defect.

`--update-baseline` rewrites the baseline only when every count goes down or stays (it refuses
any rise); it creates the file, freezing the current state, only when the file does not exist.

A gate reads its files through `source_files` and `read_source`: sorted, `__pycache__` and
`node_modules` left out, a BOM accepted. A file that cannot be read raises `UnreadableSource` with
its path: it is named, never skipped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

SKIPPED_DIRECTORIES = frozenset({"__pycache__", "node_modules"})


class UnreadableSource(Exception):
    """A source file the gate could not read; its message names the file."""


@dataclass(frozen=True)
class Ratchet:
    """What a gate counts and how it speaks about it.

    `label` opens the green line ("Swallowed errors OK (...)"), `noun` names one unit of the count
    ("swallowed error(s)"), `remedy` follows a rise, `command` is how to run the gate, `unit` is what
    the baseline counts per (a file, or a folder).
    """

    label: str
    noun: str
    remedy: str
    command: str
    baseline: Path
    unit: str = "file"


def source_files(root: Path, scan_roots: Iterable[str], suffixes: Iterable[str]) -> List[Path]:
    wanted = tuple(suffixes)
    files: List[Path] = []
    for scan_root in scan_roots:
        base = root / scan_root
        if not base.is_dir():
            raise UnreadableSource(f"{scan_root}: no such folder under {root}")
        for file in base.rglob("*"):
            relative_parts = file.relative_to(root).parts
            if SKIPPED_DIRECTORIES.intersection(relative_parts):
                continue
            if file.is_file() and file.name.endswith(wanted):
                files.append(file)
    return sorted(files)


def read_source(file: Path, root: Path) -> str:
    try:
        return file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise UnreadableSource(f"{relative(file, root)}: unreadable ({type(exc).__name__}: {exc})") from exc


def relative(file: Path, root: Path) -> str:
    return file.relative_to(root).as_posix()


def compare(actual: Mapping[str, int], baseline: Mapping[str, int],
            noun: str, unit: str = "file") -> Tuple[List[str], List[str]]:
    """Return (failures, stale): stale lines are counts the baseline must lower."""
    failures: List[str] = []
    stale: List[str] = []
    for path, count in sorted(actual.items()):
        allowed = baseline.get(path)
        if allowed is None:
            failures.append(f"{path}: {count} {noun}, {unit} absent from the baseline")
        elif count > allowed:
            failures.append(f"{path}: {count} {noun}, baseline {allowed}")
    for path, allowed in sorted(baseline.items()):
        count = actual.get(path, 0)
        if count < allowed:
            stale.append(f"{path}: baseline {allowed}, actual {count}")
    return failures, stale


def load_baseline(path: Path) -> Dict[str, int]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_baseline(counts: Mapping[str, int], path: Path) -> None:
    path.write_text(json.dumps(dict(sorted(counts.items())), indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def enforce(actual: Mapping[str, int], ratchet: Ratchet, update: bool = False,
            other_failures: Sequence[str] = ()) -> int:
    """The verdict of the gate (0 green, 1 red), or the baseline update when `update` is asked.

    `other_failures` are findings outside the count (an unreadable file, a missing tool, an
    incomplete environment): they turn the gate red and block any update of the baseline.
    """
    for line in other_failures:
        print(f"FAIL: {line}")
    total = sum(actual.values())
    baseline = load_baseline(ratchet.baseline)
    failures, stale = compare(actual, baseline, ratchet.noun, ratchet.unit)

    if update:
        if other_failures:
            print("The baseline is not updated while the count itself is in doubt.")
            return 1
        if not ratchet.baseline.exists():
            write_baseline(actual, ratchet.baseline)
            print(f"Baseline created: {total} {ratchet.noun} in {len(actual)} {ratchet.unit}(s).")
            return 0
        if failures:
            for line in failures:
                print(f"REFUSED: {line}")
            print(f"The baseline only goes down: fix the new {ratchet.noun} instead.")
            return 1
        write_baseline(actual, ratchet.baseline)
        print(f"Baseline lowered: {len(stale)} {ratchet.unit}(s) updated, {total} {ratchet.noun} left.")
        return 0

    if not failures and not stale and not other_failures:
        print(f"{ratchet.label} OK ({total} in {len(actual)} {ratchet.unit}(s), none above the baseline)")
        return 0
    for line in failures:
        print(f"FAIL: {line}. {ratchet.remedy}")
    for line in stale:
        print(f"FAIL: {line}. Lower the baseline: {ratchet.command} --update-baseline")
    return 1


def core_zone(path: str) -> str:
    """The zone of a path of the engine: `bridges`, `social_media/<platform>`, `core/<family>`..."""
    parts = path.split("/")
    if parts[0] == "bridges":
        return "bridges"
    if parts[:3] == ["taktik", "core", "social_media"] and len(parts) > 4:
        return f"social_media/{parts[3]}"
    if parts[:2] == ["taktik", "core"] and len(parts) > 3:
        return f"core/{parts[2]}"
    return parts[1] if len(parts) > 2 else parts[0]


def print_listing(actual: Mapping[str, int], noun: str,
                  zone: Callable[[str], str] = core_zone, top: int = 10) -> None:
    zones: Dict[str, int] = {}
    for path, count in actual.items():
        zones[zone(path)] = zones.get(zone(path), 0) + count
    print(f"{sum(actual.values())} {noun} in {len(actual)} file(s).\n")
    print("By zone:")
    for name, count in sorted(zones.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {count:5d}  {name}")
    print("\nHeaviest files:")
    for path, count in sorted(actual.items(), key=lambda kv: (-kv[1], kv[0]))[:top]:
        print(f"  {count:5d}  {path}")
