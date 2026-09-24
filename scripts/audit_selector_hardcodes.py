"""Audit Instagram/TikTok/Threads runtime code for inline Android UI selectors.

The rule is intentionally conservative: selectors belong in
``social_media/<platform>/ui/selectors/**`` or ``ui/language.py`` (``threads/ui``
for Threads). This script flags new literal XPath/uiautomator selector signatures
in runtime code while allowlisting the legacy hotspots that still need dedicated
cleanup lots.

A third rule, ``ui-text-comparison``, looks at what the first two cannot see: a
label word compared with text READ from the screen (``'unlike' in content_desc``,
``desc.startswith('Profile ')``, ``re.search(r'Photo de profil de ...', desc)``).
Found missing on 2026-09-24: the audit stayed green over such words in the Feed,
post_url, the DM inbox, the TikTok author read and Threads.
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = (
    ROOT / "taktik" / "core" / "social_media" / "instagram",
    ROOT / "taktik" / "core" / "social_media" / "tiktok",
    ROOT / "taktik" / "core" / "social_media" / "threads",
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


# Keys under which uiautomator2 / lxml hand back the text of a node.
UI_TEXT_KEYS = {
    "content-desc", "contentDescription", "description", "hint", "resource-id",
    "resourceId", "resourceName", "text",
}
# Variable names that hold text read from the screen. `text` alone is left out on purpose:
# it names comment bodies and log lines as often as a node's text.
UI_TEXT_NAME = re.compile(
    r"(^|_)(desc|description|content_desc|label|hint)($|_)|^(node_text|el_text|element_text)$",
    re.IGNORECASE,
)
# A regex pattern that spells words, not only digits and separators.
WORDY_PATTERN = re.compile(r"[A-Za-zÀ-ÿ]{3,} [A-Za-zÀ-ÿ]")
HAS_LETTER = re.compile(r"[A-Za-zÀ-ÿ]")


KNOWN_SELECTOR_DEBT = (
    # Count parsers: the language words sit inside the number regexes. Owner: Instagram UI
    # extraction. Exit: a count parser driven by the locale files, in its own lot.
    AllowlistEntry(
        "taktik/core/social_media/instagram/ui/extractors.py",
        "ui-text-comparison",
        "'likes'",
        "Like-count parser gate (FR/EN words inside the count regex); locale-driven parser to come.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/ui/extractors.py",
        "ui-text-comparison",
        "'aime'",
        "Like-count parser gate (FR/EN words inside the count regex); locale-driven parser to come.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/ui/extractors.py",
        "ui-text-comparison",
        "'commentaire'",
        "Comment-count parser gate (FR/EN words inside the count regex); locale-driven parser to come.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/ui/extractors.py",
        "ui-text-comparison",
        "'comment'",
        "Comment-count parser gate (FR/EN words inside the count regex); locale-driven parser to come.",
    ),
    # Owner: TikTok video detection. `_extract_french_like_count` is a French parser by name;
    # exit with the same locale-driven count parser.
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/atomic/detection/video_detector.py",
        "ui-text-comparison",
        "\"J'aime\"",
        "French like-count parser of the like button content-desc; locale-driven parser to come.",
    ),
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
        "taktik/core/social_media/tiktok/actions/atomic/messaging/dm_actions.py",
        "selector-string",
        r'@resource-id\s*=\s*"([^"]+)"',
        "Regex builder for resourceIdMatches (contains-form XPath -> regex), not a runtime selector.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/atomic/messaging/dm_actions.py",
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
            # Threads keeps its whole catalog in `threads/ui/` (no `selectors/` subpackage).
            if scan_root.name == "threads" and relative_parts[0] == "ui":
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


def is_screen_text(node: ast.AST) -> bool:
    """Whether the expression holds text read from a UI node."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ("lower", "upper", "casefold", "strip") and not node.args:
            return is_screen_text(node.func.value)
        if node.func.attr == "get" and node.args:
            return string_value(node.args[0]) in UI_TEXT_KEYS
    if isinstance(node, ast.Subscript):
        return string_value(node.slice) in UI_TEXT_KEYS
    if isinstance(node, ast.Name):
        return bool(UI_TEXT_NAME.search(node.id))
    if isinstance(node, ast.Attribute):
        return bool(UI_TEXT_NAME.search(node.attr))
    return False


def label_word(node: ast.AST) -> str | None:
    value = string_value(node)
    return value if value is not None and HAS_LETTER.search(value) else None


def ui_text_comparison_findings(path: Path, tree: ast.AST) -> list[Finding]:
    findings: list[Finding] = []

    def found(node: ast.AST, form: str, word: str) -> None:
        findings.append(Finding(path=path, line=getattr(node, "lineno", 0),
                                rule="ui-text-comparison", value=f"{form}: {word!r}"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            left = node.left
            for op, right in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)):
                    word = label_word(left)
                    if word and is_screen_text(right):
                        found(node, "in", word)
                elif isinstance(op, (ast.Eq, ast.NotEq)):
                    for literal_side, other in ((left, right), (right, left)):
                        word = label_word(literal_side)
                        if word and is_screen_text(other):
                            found(node, "eq", word)
                left = right
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            if attr in ("startswith", "endswith") and node.args and is_screen_text(node.func.value):
                word = label_word(node.args[0])
                if word:
                    found(node, attr, word)
            elif (isinstance(node.func.value, ast.Name) and node.func.value.id == "re"
                    and attr in ("search", "match", "fullmatch", "findall")
                    and len(node.args) >= 2 and is_screen_text(node.args[1])):
                word = label_word(node.args[0])
                if word and WORDY_PATTERN.search(word):
                    found(node, "regex", word)
    return findings


def collect_findings() -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_python_files():
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        findings.extend(selector_string_findings(path, tree))
        findings.extend(call_keyword_findings(path, tree))
        findings.extend(ui_text_comparison_findings(path, tree))
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
