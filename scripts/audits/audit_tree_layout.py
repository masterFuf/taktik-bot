"""Layout of the engine's tree: a folder of the table holds only the sub-folders and files it lists.

`LAYOUT` is the table of contents of the tree, written once: for a folder, the sub-folders it may hold
and the files it may hold directly, with its owner. A framework fixes its folders (`src/Controller`,
`src/Command`...) so that everyone knows where to look before opening a file; the table does the same
and this gate keeps the tree to it (AGENTS.md, section Structure). A new folder is documented in
AGENTS.md first, then added here. The families of `taktik/core` stay listed once, in `CORE_FAMILIES` of
`audit_import_layers.py`: when the table gains `taktik/core`, it reads that set, it never copies it.

Today the table holds `scripts/`, filed by usage: `audits/` (the gates, their libraries and ratchets),
`generate/` (write a tracked file), `build/` (the packaged launcher), `repairs/` (one-off repairs of the
operator's base), `lab/` (screen corpus, replay, anonymization, measures), `dev/` (tools for a phone
on the desk), `eval/` (AI model replays), `hooks/` (the commit hooks and their installer). At its root,
the public install commands only (`install.ps1`, `install.sh`): no `.py`.

The gate is red when:

- a folder of the table holds a sub-folder or a file it does not list (a `.py` at the root of
  `scripts/`: file it in its usage folder);
- an entry of the table no longer exists (a listed sub-folder without a file, a listed file gone): the
  table says what is there, drop the entry;
- git ignores a listed sub-folder: a file added there would vanish from `git status` (the unanchored
  `build/` of the `.gitignore` did it to `scripts/build/`).

Files are read on disk the way the counting gates read them (`ratchet.source_files`, `__pycache__` and
`node_modules` left out), so what a checkout holds besides the repository is seen too: a private script
left at the root of `scripts/` turns the gate red there.

    python scripts/audits/audit_tree_layout.py              # green / red
    python scripts/audits/audit_tree_layout.py --self-test  # each kind of misplaced entry turns it red
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from ratchet import relative, source_files

CORE = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Folder:
    """What a folder of the tree holds directly, and who owns it."""

    folders: frozenset[str]
    files: frozenset[str]
    owner: str


LAYOUT: dict[str, Folder] = {
    "scripts": Folder(
        folders=frozenset({"audits", "build", "dev", "eval", "generate", "hooks", "lab", "repairs"}),
        files=frozenset({"install.ps1", "install.sh"}),
        owner="the tooling, filed by usage; at the root, the public install commands only",
    ),
}

IgnoreCheck = Callable[[str], bool]


def tree_paths(root: Path = CORE, layout: Mapping[str, Folder] = LAYOUT) -> list[str]:
    """Every file under the folders of the table, relative to the root and written with `/`."""
    return [relative(file, root) for file in source_files(root, sorted(layout), suffixes=("",))]


#: One line of `git check-ignore -v`: `<source>:<line>:<pattern><TAB><path>`; the source may hold a drive letter.
CHECK_IGNORE_LINE = re.compile(r"^(?P<source>.*):(?P<line>\d+):(?P<pattern>[^\t]*)\t")


def git_ignores(path: str, root: Path = CORE) -> bool:
    """Would git ignore a new file at `path`? A rule that re-includes it (`!x`) is no ignore."""
    result = subprocess.run(["git", "-C", str(root), "check-ignore", "-v", "--no-index", path],
                            capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git check-ignore failed on {path}: {result.stderr.strip()}")
    matched = CHECK_IGNORE_LINE.match(result.stdout)
    return result.returncode == 0 and matched is not None and not matched.group("pattern").startswith("!")


def check(paths: Sequence[str], is_ignored: IgnoreCheck = git_ignores,
          layout: Mapping[str, Folder] = LAYOUT) -> list[str]:
    errors: list[str] = []
    for folder, allowed in sorted(layout.items()):
        prefix = f"{folder}/"
        held_folders: set[str] = set()
        held_files: set[str] = set()
        for path in paths:
            if path.startswith(prefix):
                name, _, rest = path[len(prefix):].partition("/")
                (held_folders if rest else held_files).add(name)
        for name in sorted(held_folders - allowed.folders):
            errors.append(f"{prefix}{name}/: a folder `{folder}/` does not list. Document its usage in AGENTS.md "
                          f"(Structure), then add it to LAYOUT in this gate.")
        for name in sorted(held_files - allowed.files):
            if name.endswith(".py"):
                errors.append(f"{prefix}{name}: no .py at the root of `{folder}/`, file it in its usage folder "
                              f"({', '.join(sorted(allowed.folders))}).")
            else:
                errors.append(f"{prefix}{name}: a file `{folder}/` does not list. Move it, or list it in LAYOUT "
                              f"with the reason it stays there.")
        for name in sorted(allowed.folders - held_folders):
            errors.append(f"{prefix}{name}/: listed in LAYOUT but holds no file, drop the entry.")
        for name in sorted(allowed.files - held_files):
            errors.append(f"{prefix}{name}: listed in LAYOUT but gone, drop the entry.")
        for name in sorted(allowed.folders):
            if is_ignored(f"{prefix}{name}/new_file.py"):
                errors.append(f"{prefix}{name}/: git ignores it, a file added there would vanish from git status. "
                              f"Anchor or narrow the .gitignore rule (`git check-ignore -v {prefix}{name}/x.py`).")
    return errors


def self_test_cases(paths: Sequence[str]) -> dict[str, dict]:
    """Each fake must turn the gate red by its rule; the real tree, unchanged, must not."""
    def fake(extra: Iterable[str] = (), without: str = "", ignored: str = "") -> list[str]:
        return [p for p in paths if not (without and p.startswith(without))] + list(extra)

    return {
        "a .py at the root of scripts/": {"paths": fake(["scripts/stray_tool.py"]), "expect": "no .py at the root"},
        "another file at the root of scripts/": {"paths": fake(["scripts/notes.txt"]),
                                                 "expect": "a file `scripts/` does not list"},
        "a folder scripts/ does not list": {"paths": fake(["scripts/misc/tool.py"]),
                                            "expect": "a folder `scripts/` does not list"},
        "a listed folder left empty": {"paths": fake(without="scripts/lab/"), "expect": "holds no file"},
        "a listed file gone": {"paths": fake(without="scripts/install.sh"), "expect": "but gone"},
        "a listed folder git ignores": {"paths": fake(), "expect": "git ignores it",
                                        "is_ignored": lambda path: path.startswith("scripts/build/")},
    }


def caught(case: dict) -> bool:
    is_ignored = case.get("is_ignored", lambda _path: False)
    return any(case["expect"] in error for error in check(case["paths"], is_ignored))


def self_test() -> int:
    paths = tree_paths()
    cases = self_test_cases(paths)
    missed = [name for name, case in cases.items() if not caught(case)]
    control = check(paths)
    if missed or control:
        for name in missed:
            print(f"Self-test FAILED, not caught: {name}")
        for error in control:
            print(f"Self-test FAILED, the real tree is red: {error}")
        return 1
    print(f"Tree layout self-test OK ({len(cases)} fakes caught, the real tree green)")
    return 0


def main() -> int:
    paths = tree_paths()
    errors = check(paths)
    if errors:
        print(f"Tree layout: {len(errors)} finding(s). The table is LAYOUT in this gate; AGENTS.md (Structure) "
              f"says what each folder is for.")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"Tree layout OK ({len(LAYOUT)} folder(s) of the table, {len(paths)} files, every one in its place)")
    return 0


if __name__ == "__main__":
    raise SystemExit(self_test() if "--self-test" in sys.argv else main())
