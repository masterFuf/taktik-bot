"""Audit Instagram/TikTok runtime code for inline Android UI selectors.

The rule is intentionally conservative: selectors belong in
``social_media/<platform>/ui/selectors/**`` or ``ui/language.py``. This script
flags new literal XPath/uiautomator selector signatures in runtime code while
allowlisting the legacy hotspots that still need dedicated cleanup lots.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "taktik" / "core" / "social_media" / "instagram",
    ROOT / "taktik" / "core" / "social_media" / "tiktok",
)

SELECTOR_SUBSTRINGS = (
    "//android.",
    "//*[@",
    "@resource-id",
    "@text",
    "@content-desc",
    "@hint",
    "contains(@resource-id",
    "contains(@text",
    "contains(@content-desc",
    "com.android.packageinstaller:id/",
    "com.instagram.android:id/",
    "com.zhiliaoapp.musically:id/",
    "com.ss.android.ugc.trill:id/",
)

UI_SELECTOR_KWARGS = {
    "className",
    "contentDescription",
    "description",
    "descriptionContains",
    "resourceId",
    "resourceIdMatches",
    "text",
    "textContains",
    "textMatches",
    "textStartsWith",
}


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule: str
    value: str

    @property
    def relative_path(self) -> str:
        return self.path.relative_to(ROOT).as_posix()


@dataclass(frozen=True)
class AllowlistEntry:
    path: str
    rule: str
    contains: str
    reason: str

    def matches(self, finding: Finding) -> bool:
        return (
            finding.relative_path == self.path
            and finding.rule == self.rule
            and self.contains in finding.value
        )


KNOWN_SELECTOR_DEBT = (
)

NON_RUNTIME_SIGNATURES = (
    AllowlistEntry(
        "taktik/core/social_media/instagram/actions/compatibility/cli_adapter.py",
        "uiautomator-literal",
        "Instagram Bot - New Modular Architecture",
        "Synthetic CLI compatibility probe, not a runtime Android UI selector.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/core/utils.py",
        "selector-string",
        '@resource-id="([^"]+)"',
        "Regex parser for catalog-provided XPath, not a selector used against the UI.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/atomic/dm_actions.py",
        "selector-string",
        r'@resource-id\s*=\s*"([^"]+)"',
        "Regex builder for resourceIdMatches (contains-form XPath -> regex), not a runtime selector.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/atomic/dm_actions.py",
        "selector-string",
        r'@resource-id\s*,\s*"([^"]+)"',
        "Regex builder for resourceIdMatches (contains-form XPath -> regex), not a runtime selector.",
    ),
)


def iter_python_files() -> Iterable[Path]:
    for scan_root in SCAN_ROOTS:
        for path in scan_root.rglob("*.py"):
            relative_parts = path.relative_to(scan_root).parts
            if "__pycache__" in relative_parts:
                continue
            if "test" in relative_parts or "tests" in relative_parts:
                continue
            if path.name == "language.py" and "ui" in relative_parts:
                continue
            if "ui" in relative_parts and "selectors" in relative_parts:
                continue
            yield path


def docstring_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                lines.add(first.lineno)
    return lines


def string_value(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def call_keyword_findings(path: Path, tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg not in UI_SELECTOR_KWARGS:
                continue
            value = string_value(keyword.value)
            if value is None:
                continue
            findings.append(
                Finding(
                    path=path,
                    line=getattr(keyword.value, "lineno", getattr(node, "lineno", 0)),
                    rule="uiautomator-literal",
                    value=f"{keyword.arg}={value!r}",
                )
            )
    return findings


def selector_string_findings(path: Path, tree: ast.AST) -> list[Finding]:
    docs = docstring_lines(tree)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        value = string_value(node)
        if value is None:
            continue
        line = getattr(node, "lineno", 0)
        if line in docs:
            continue
        if any(part in value for part in SELECTOR_SUBSTRINGS):
            findings.append(
                Finding(
                    path=path,
                    line=line,
                    rule="selector-string",
                    value=value,
                )
            )
    return findings


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        findings.extend(selector_string_findings(path, tree))
        findings.extend(call_keyword_findings(path, tree))
    return sorted(findings, key=lambda finding: (finding.relative_path, finding.line, finding.rule))


def is_allowlisted(finding: Finding) -> bool:
    return any(entry.matches(finding) for entry in KNOWN_SELECTOR_DEBT)


def is_non_runtime_signature(finding: Finding) -> bool:
    return any(entry.matches(finding) for entry in NON_RUNTIME_SIGNATURES)


def format_finding(finding: Finding) -> str:
    value = finding.value.replace("\n", "\\n")
    if len(value) > 140:
        value = f"{value[:137]}..."
    return f"{finding.relative_path}:{finding.line}: {finding.rule}: {value}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--show-allowed",
        action="store_true",
        help="print allowlisted selector debt as well as blocking findings",
    )
    args = parser.parse_args()

    findings = collect_findings()
    runtime_findings = [
        finding for finding in findings if not is_non_runtime_signature(finding)
    ]
    blocking = [finding for finding in runtime_findings if not is_allowlisted(finding)]
    allowed = [finding for finding in findings if is_allowlisted(finding)]
    ignored = [finding for finding in findings if is_non_runtime_signature(finding)]

    if blocking:
        print("Selector hardcode audit failed:")
        for finding in blocking:
            print(f" - {format_finding(finding)}")
        if allowed:
            print(f"\nAllowlisted legacy selector debt: {len(allowed)} finding(s)")
        return 1

    print(
        "Selector hardcode audit OK "
        f"(0 new findings, {len(allowed)} allowlisted legacy finding(s), "
        f"{len(ignored)} non-runtime exception(s))"
    )
    if args.show_allowed and allowed:
        for finding in allowed:
            print(f" - {format_finding(finding)}")
    if args.show_allowed and ignored:
        print("\nIgnored non-runtime signatures:")
        for finding in ignored:
            print(f" - {format_finding(finding)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
