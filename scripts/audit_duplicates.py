"""Ratchet gate: the number of duplicated lines per file may only go down.

Zero duplication (AGENTS.md, "Anti-derive"): a second way to do the same thing is a design error.
This gate cannot tell a helper copied by hand from a pattern two files share on purpose, so it
does not judge today's copies: it freezes them, file by file, and refuses any new one.

What counts, read on lines, the same way for Python and for TypeScript/JavaScript:

* each line is stripped and its inner blanks collapsed. Left out: an empty line, a comment, a line
  with no letter or digit (``)``, ``});``), an import (every line of it: ``import``, ``from ...
  import (...)``, ``export {...} from``, ``require(...)``), and in Python a string standing alone
  (a docstring). What is left are the file's SIGNIFICANT lines;
* a WINDOW is ``WINDOW`` significant lines in a row. A window is DUPLICATED when the same text
  stands at another place: another file, or the same file without overlap;
* a file's count is the number of its significant lines covered by a duplicated window.

A file whose first lines say ``GENERATED ... do not edit`` is left out: it repeats its source by
construction, and the gate of its generator keeps it in step.

Ratchet (``scripts/ratchet.py``, shared by the counting gates): the baseline maps each file to its
count. The gate is red when a file exceeds its count, when a file absent from the baseline has
duplicated lines, and when a count in the baseline is higher than reality (lower it: the ratchet
never goes back up). A file that cannot be read is named and turns the gate red.

The engine is scanned by default. The desktop app runs the same detector on its own tree, with its
own baseline, through ``--root``, ``--scan``, ``--baseline`` and ``--command``.

Usage:
    python scripts/audit_duplicates.py                    # green / red
    python scripts/audit_duplicates.py --list             # totals, zones, heaviest files, largest copies
    python scripts/audit_duplicates.py --update-baseline  # record decreases only
    python scripts/audit_duplicates.py --self-test        # each kind of copy turns it red
    python scripts/audit_duplicates.py --root DIR --scan a,b --baseline FILE --command "npm run x"
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ratchet import (Ratchet, UnreadableSource, core_zone, enforce, print_listing, read_source,
                     relative, source_files)

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("taktik", "bridges", "scripts")
BASELINE = ROOT / "scripts" / "audit_duplicates_baseline.json"
COMMAND = "python scripts/audit_duplicates.py"

#: Significant lines in a window. Measured on both trees: at 6, the shared shape of a guard clause
#: or of a logging block starts to count; at 10 and more, a copied helper of eight lines passes.
WINDOW = 8

PYTHON = (".py",)
SCRIPT = (".ts", ".tsx", ".js", ".cjs", ".mjs")
SUFFIXES = PYTHON + SCRIPT
GENERATED_MARK = ("GENERATED", "do not edit")
NOUN = "duplicated line(s)"


@dataclass(frozen=True)
class Line:
    number: int
    text: str


@dataclass(frozen=True)
class Copy:
    """One text found at several places: `places` are (path, first line, last line)."""

    length: int
    places: Tuple[Tuple[str, int, int], ...]


def _collapse(raw: str) -> str:
    return " ".join(raw.split())


def _starts_python_import(line: str) -> bool:
    return line.startswith("import ") or (line.startswith("from ") and " import " in line)


def _is_python_string_statement(line: str) -> Optional[str]:
    """The closing quote of a string standing alone on its line (a docstring), else None."""
    unprefixed = line.lstrip("rRbBuUfF")
    if len(line) - len(unprefixed) > 2:
        return None
    for quote in ('"""', "'''"):
        if unprefixed.startswith(quote):
            return quote
    return None


def python_lines(text: str) -> List[Line]:
    kept: List[Line] = []
    closing_quote: Optional[str] = None
    import_close: Optional[str] = None  # ")" for a parenthesised import, "\\" for a continued one
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _collapse(raw)
        if closing_quote:
            if closing_quote in line:
                closing_quote = None
            continue
        if import_close:
            if (import_close == ")" and ")" in line) or (import_close == "\\" and not line.endswith("\\")):
                import_close = None
            continue
        if not line or line.startswith("#"):
            continue
        if _starts_python_import(line):
            if "(" in line and ")" not in line:
                import_close = ")"
            elif line.endswith("\\"):
                import_close = "\\"
            continue
        quote = _is_python_string_statement(line)
        if quote:
            rest = line.lstrip("rRbBuUfF")[3:]
            if quote not in rest:
                closing_quote = quote
            continue
        if any(char.isalnum() for char in line):
            kept.append(Line(number, line))
    return kept


def _script_import_end(line: str) -> Optional[str]:
    """For a line that starts an import or an export list, what closes it ('from' or '}'), else None."""
    if line.startswith(("import ", "import{")):
        return "from"
    if line.startswith("export ") and (" from " in line or line.endswith(" from")):
        return "from"
    if line.startswith(("export {", "export type {", "export *")):
        return "}"
    if line.startswith(("const ", "let ", "var ")) and "require(" in line and "=" in line:
        return ")"
    return None


def _closes_import(line: str, end: str) -> bool:
    if end == "from":
        return ("from '" in line or 'from "' in line
                or line.startswith(("import '", 'import "')))
    return end in line


def script_lines(text: str) -> List[Line]:
    kept: List[Line] = []
    in_comment = False
    import_end: Optional[str] = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _collapse(raw)
        if in_comment:
            in_comment = "*/" not in line
            continue
        if import_end:
            if _closes_import(line, import_end):
                import_end = None
            continue
        if not line or line.startswith("//") or (line.startswith("{/*") and line.endswith("*/}")):
            continue
        if line.startswith("/*"):
            in_comment = "*/" not in line
            continue
        end = _script_import_end(line)
        if end:
            if not _closes_import(line, end):
                import_end = end
            continue
        if any(char.isalnum() for char in line):
            kept.append(Line(number, line))
    return kept


def significant_lines(text: str, path: str) -> List[Line]:
    return python_lines(text) if path.endswith(PYTHON) else script_lines(text)


def is_generated(text: str) -> bool:
    return any(all(mark in line for mark in GENERATED_MARK) for line in text.splitlines()[:3])


def _digest(lines: Sequence[Line]) -> bytes:
    return hashlib.blake2b("\n".join(line.text for line in lines).encode("utf-8"),
                           digest_size=16).digest()


class Detector:
    """The windows of every file, and which of them stand at more than one place."""

    def __init__(self, files: Dict[str, List[Line]], window: int = WINDOW):
        self.files = files
        self.window = window
        self.digests: Dict[str, List[bytes]] = {
            path: [_digest(lines[i:i + window]) for i in range(len(lines) - window + 1)]
            for path, lines in files.items()
        }
        self.places: Dict[bytes, List[Tuple[str, int]]] = defaultdict(list)
        for path, digests in self.digests.items():
            for index, digest in enumerate(digests):
                self.places[digest].append((path, index))

    def _has_partner(self, digest: bytes, path: str, index: int) -> bool:
        return any(other != path or abs(other_index - index) >= self.window
                   for other, other_index in self.places[digest])

    def counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for path, digests in self.digests.items():
            covered = set()
            for index, digest in enumerate(digests):
                if len(self.places[digest]) > 1 and self._has_partner(digest, path, index):
                    covered.update(range(index, index + self.window))
            if covered:
                counts[path] = len(covered)
        return counts

    def copies(self) -> List[Copy]:
        """Each duplicated text at its full length, largest first."""
        found: Dict[Tuple[int, bytes], set] = {}
        for digest, places in self.places.items():
            if len(places) < 2:
                continue
            for a in range(len(places)):
                for b in range(a + 1, len(places)):
                    self._extend(places[a], places[b], found)
        copies = [Copy(length, tuple(sorted(places))) for (length, _), places in found.items()]
        return sorted(copies, key=lambda copy: (-copy.length, -len(copy.places), copy.places))

    def _extend(self, first: Tuple[str, int], second: Tuple[str, int], found: Dict) -> None:
        (path_a, i), (path_b, j) = first, second
        digests_a, digests_b = self.digests[path_a], self.digests[path_b]
        if path_a == path_b and abs(i - j) < self.window:
            return
        if i > 0 and j > 0 and digests_a[i - 1] == digests_b[j - 1]:
            return  # not the start of this copy
        steps = 1
        while (i + steps < len(digests_a) and j + steps < len(digests_b)
               and digests_a[i + steps] == digests_b[j + steps]
               and (path_a != path_b or abs(i - j) >= self.window + steps)):
            steps += 1
        length = steps + self.window - 1
        lines_a = self.files[path_a][i:i + length]
        lines_b = self.files[path_b][j:j + length]
        key = (length, _digest(lines_a))
        places = found.setdefault(key, set())
        places.add((path_a, lines_a[0].number, lines_a[-1].number))
        places.add((path_b, lines_b[0].number, lines_b[-1].number))


def folder_zone(path: str) -> str:
    """The zone of a path outside the engine: its first three folders at most."""
    return "/".join(path.split("/")[:-1][:3]) or "."


def read_tree(root: Path, scan_roots: Sequence[str]) -> Tuple[Dict[str, List[Line]], List[str]]:
    """The significant lines of every file, and the files that could not be read (named)."""
    files: Dict[str, List[Line]] = {}
    unreadable: List[str] = []
    for file in source_files(root, scan_roots, SUFFIXES):
        path = relative(file, root)
        try:
            text = read_source(file, root)
        except UnreadableSource as exc:
            unreadable.append(str(exc))
            continue
        if not is_generated(text):
            files[path] = significant_lines(text, path)
    return files, unreadable


def print_copies(copies: Sequence[Copy], top: int = 10) -> None:
    print(f"\nLargest copies ({len(copies)} in all, in significant lines):")
    for copy in copies[:top]:
        where = "; ".join(f"{path}:{first}-{last}" for path, first, last in copy.places)
        print(f"  {copy.length:5d}  x{len(copy.places)}  {where}")


def self_test_cases() -> Dict[str, Tuple[Dict[str, str], str]]:
    """Each fake tree, and the file the gate must name (empty: the tree must stay green).

    Each text that is not a copy (imports, comments, docstrings) is long enough to fill a window if
    it were kept: dropping one of the rules that leaves it out turns its case red.
    """
    body = "".join(f"    total = total + value_{n} * {n}\n" for n in range(WINDOW))
    helper = f"def helper(total):\n{body}    return total\n"
    ts_body = "".join(f"  total = total + value{n} * {n}\n" for n in range(WINDOW))
    ts_helper = f"export function helper(total: number): number {{\n{ts_body}  return total\n}}\n"

    names = [f"name_{n}" for n in range(WINDOW)]

    def twice(suffix: str, text: str) -> Dict[str, str]:
        return {f"a{suffix}": text, f"b{suffix}": text}

    return {
        "a Python helper copied into another file": ({"a.py": helper, "b.py": "x = 1\n" + helper}, "b.py"),
        "a TypeScript helper copied into another file": ({"a.ts": ts_helper, "b.tsx": ts_helper}, "b.tsx"),
        "a copy re-indented and re-spaced": (
            {"a.py": helper,
             "b.py": "class K:\n" + "".join(f"    {line}\n" for line in helper.replace(" + ", "  +  ").splitlines())},
            "b.py"),
        "a copy inside the same file": ({"a.py": helper + "\n\n" + helper.replace("helper", "other")}, "a.py"),
        "Python imports are not a copy": (twice(".py", "import os\nfrom x import y\n" * WINDOW), ""),
        "a parenthesised Python import is not a copy": (
            twice(".py", "from x import (\n" + "".join(f"    {name},\n" for name in names) + ")\n"), ""),
        "a continued Python import is not a copy": (
            twice(".py", "from x import y, \\\n" + "".join(f"    {name}, \\\n" for name in names) + "    z\n"), ""),
        "a Python docstring is not a copy": (twice(".py", '"""Doc\nshared\nlines\n"""\n' * WINDOW), ""),
        "Python comments are not a copy": (twice(".py", "# note\n" * WINDOW), ""),
        "TypeScript imports are not a copy": (
            twice(".ts", "import {\n" + "".join(f"  {name},\n" for name in names) + "} from './x'\n"), ""),
        "TypeScript re-exports are not a copy": (
            twice(".ts", "export * from './y'\nexport {\n  c,\n} from './z'\n" * WINDOW), ""),
        "a require is not a copy": (twice(".cjs", "const { d } = require('w')\n" * WINDOW), ""),
        "TypeScript line comments are not a copy": (twice(".ts", "// note\n" * WINDOW), ""),
        "TypeScript block comments are not a copy": (twice(".ts", "/* block\n more */\n" * WINDOW), ""),
        "JSX comments are not a copy": (twice(".tsx", "{/* Header */}\n" * WINDOW), ""),
        "a generated file is left out": (
            {"a.ts": ts_helper, "b.ts": "/**\n * GENERATED from the bot - do not edit.\n */\n" + ts_helper}, ""),
        "a text shorter than the window is not a copy": (
            {"a.py": "def f(total):\n" + body.split("\n", 1)[1], "b.py": "def g(total):\n" + body.split("\n", 1)[1]}, ""),
    }


def judge(tree: Dict[str, str]) -> Tuple[Dict[str, int], List[str]]:
    """The counts of a fake tree written to a throwaway folder, and its unreadable files."""
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        for path, text in tree.items():
            (root / path).write_text(text, encoding="utf-8", newline="\n")
        files, unreadable = read_tree(root, (".",))
        return Detector(files).counts(), unreadable


def self_test() -> int:
    missed: List[str] = []
    for name, (tree, expected) in self_test_cases().items():
        counts, unreadable = judge(tree)
        named = {path.rsplit("/", 1)[-1] for path in counts}
        if unreadable or (expected and expected not in named) or (not expected and named):
            missed.append(f"{name}: expected {expected or 'nothing'}, got {sorted(named) or 'nothing'}")
    if missed:
        for line in missed:
            print(f"Self-test FAILED, {line}")
        return 1
    print(f"Duplicated lines self-test OK ({len(self_test_cases())} trees, each judged as expected)")
    return 0


def _option(argv: Sequence[str], name: str) -> Optional[str]:
    if name not in argv:
        return None
    at = list(argv).index(name) + 1
    if at >= len(argv) or argv[at].startswith("--"):
        raise SystemExit(f"{name} expects a value")
    return argv[at]


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    root = Path(_option(argv, "--root") or ROOT).resolve()
    scan = tuple((_option(argv, "--scan") or ",".join(SCAN_ROOTS)).split(","))
    baseline = Path(_option(argv, "--baseline") or BASELINE)
    command = _option(argv, "--command") or COMMAND

    files, unreadable = read_tree(root, scan)
    detector = Detector(files)
    actual = detector.counts()
    if "--list" in argv:
        print_listing(actual, NOUN, zone=core_zone if root == ROOT else folder_zone)
        print_copies(detector.copies())
        return 0
    return enforce(actual, Ratchet(
        label="Duplicated lines",
        noun=NOUN,
        remedy="Reuse or extend the existing code instead of copying it.",
        command=command,
        baseline=baseline,
    ), update="--update-baseline" in argv, other_failures=unreadable)


if __name__ == "__main__":
    raise SystemExit(main())
