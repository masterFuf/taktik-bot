"""Audit the engine for logging calls that pass `exc_info=` to a loguru logger.

The rule: a trace is written one way, `logger.exception(message)`, or
`logger.opt(exception=...).<level>(message)` at another level than ERROR. Never `exc_info=`.

Why: `exc_info=` is the standard `logging` module's keyword, and the engine logs through loguru.
Loguru does not know it. It filed it among the record's extra fields and wrote the message without
its trace; worse, it formats the message with the keywords it receives (`message.format(**kwargs)`),
so a message whose text holds braces (an HTTP body in an exception's text) raised KeyError out of
the logging call itself. Nothing was written, and the crash path of the Instagram session loop left
without its `session_stop`.

What is flagged: a call to a logging method (`debug`, `info`, `warning`, `error`, `exception`,
`critical`, `success`, `trace`, `log`) with an `exc_info=` keyword, in `taktik/`, `bridges/` and
`scripts/` (tests left out). What is left alone: a logger of the standard library, where `exc_info=`
is the standard's own way: a call on the `logging` module itself, or on a name or attribute the
module assigns from `logging.getLogger(...)`. Every other logger of the engine is loguru's, held
directly or re-exported by another module (`bridges.common.bridge_base.logger`).

No list of exceptions: the count is zero, and stays there.

Run: ``python scripts/audits/audit_log_exc_info.py``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

from ratchet import UnreadableSource, parse_source, relative, source_files

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = ("taktik", "bridges", "scripts")
LOG_METHODS = {"trace", "debug", "info", "success", "warning", "error", "exception", "critical", "log"}
REMEDY = ("write logger.exception(...), or logger.opt(exception=...).<level>(...) at another level: "
          "loguru ignores exc_info and formats the message with it (braces in the text raise KeyError)")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    call: str

    def render(self) -> str:
        return f"{self.path}:{self.line}: {self.call}(..., exc_info=...) -- {REMEDY}"


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return f"{_dotted(node.func)}()"
    return ""


def _is_get_logger(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _dotted(node.func) == "logging.getLogger"


def _standard_logger_names(tree: ast.Module) -> Set[str]:
    """Names and attributes the module binds to a logger of the standard library."""
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_get_logger(node.value):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None and _is_get_logger(node.value):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
            elif isinstance(target, ast.Attribute):
                names.add(target.attr)
    return names


def _is_standard_logger(receiver: ast.AST, standard_names: Set[str]) -> bool:
    if _is_get_logger(receiver):
        return True
    text = _dotted(receiver)
    if text == "logging":
        return True
    last = text.rsplit(".", 1)[-1]
    return last in standard_names


def scan_tree(tree: ast.Module, rel: str) -> List[Finding]:
    standard_names = _standard_logger_names(tree)
    findings: List[Finding] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in LOG_METHODS:
            continue
        if not any(keyword.arg == "exc_info" for keyword in node.keywords):
            continue
        if _is_standard_logger(node.func.value, standard_names):
            continue
        findings.append(Finding(rel, node.lineno, _dotted(node.func)))
    return sorted(findings, key=lambda finding: finding.line)


def scan_source(source: str, rel: str = "<source>") -> List[Finding]:
    return scan_tree(ast.parse(source), rel)


def _is_test(rel: str) -> bool:
    return "/tests/" in f"/{rel}" or rel.rsplit("/", 1)[-1].startswith("test_")


def collect(root: Path = ROOT) -> List[Finding]:
    findings: List[Finding] = []
    for path in source_files(root, SCAN_ROOTS, (".py",)):
        rel = relative(path, root)
        if _is_test(rel):
            continue
        findings.extend(scan_tree(parse_source(path, root), rel))
    return findings


def main() -> int:
    try:
        findings = collect()
    except UnreadableSource as exc:
        print(f"exc_info audit FAILED: {exc}")
        return 1
    if findings:
        print(f"exc_info audit FAILED: {len(findings)} logging call(s) pass exc_info= to a loguru logger")
        for finding in findings:
            print(f" - {finding.render()}")
        return 1
    print("exc_info audit OK (no logging call passes exc_info= to a loguru logger)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
