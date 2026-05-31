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
    AllowlistEntry(
        "taktik/core/social_media/instagram/ui/detectors/problematic_page.py",
        "selector-string",
        "com.android.packageinstaller:id/permission_allow_button",
        "Android permission popup detector; move to a support selector catalog in a focused lot.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/scraping/list_strategy.py",
        "selector-string",
        "//android.widget.Button",
        "Comment-list username fast path still uses a raw class XPath.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/post_scraping/engagement_scraping.py",
        "selector-string",
        "//android.widget.Button",
        "Post engagement scraping still scans raw button nodes.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/post_scraping/engagement_scraping.py",
        "selector-string",
        "//android.view.ViewGroup",
        "Post engagement scraping still scans raw view groups.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/post_scraping/post_scraping_workflow.py",
        "selector-string",
        "//android.widget.Button",
        "Post scraping navigation still scans raw button nodes.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/atomic/video_detector.py",
        "selector-string",
        "Like video",
        "Video like detector fallback still owns two inline content-desc probes.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/atomic/video_detector.py",
        "selector-string",
        "Attribuer un",
        "Video like detector fallback still owns two inline content-desc probes.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/actions/business/management/content/navigation.py",
        "selector-string",
        "contains(@text",
        "Hashtag selection fallback still composes raw XPath around the target hashtag.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/actions/business/management/content/navigation.py",
        "selector-string",
        "contains(@resource-id",
        "Hashtag selection fallback still uses a raw resource-id probe.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/actions/compatibility/cli_adapter.py",
        "uiautomator-literal",
        "Instagram Bot - New Modular Architecture",
        "Compatibility CLI smoke test describes a synthetic UI probe, not a workflow selector.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/auth/login/screen_detection.py",
        "selector-string",
        '//*[@clickable="true" and @visible-to-user="true"]',
        "Login screen detector still has a generic clickable fallback outside the auth catalog.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/management/content/content_ui_helpers.py",
        "uiautomator-literal",
        "android.view.ViewGroup",
        "Content publishing gallery fallback still uses a raw class selector.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/management/content/content_ui_helpers.py",
        "uiautomator-literal",
        "android.widget.EditText",
        "Content publishing text/search fallbacks still use raw class selectors.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/management/content/content_ui_helpers.py",
        "uiautomator-literal",
        "android.widget.TextView",
        "Content publishing location fallback still uses a raw class selector.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/instagram/workflows/management/content/content_ui_helpers.py",
        "uiautomator-literal",
        "android.inputmethodservice.SoftInputWindow",
        "Keyboard visibility fallback should move to an input/support selector owner.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/business/workflows/_internal/profile_extractor.py",
        "uiautomator-literal",
        "android.widget.Button",
        "TikTok profile bio button fallback needs a scoped profile selector builder.",
    ),
    AllowlistEntry(
        "taktik/core/social_media/tiktok/actions/core/utils.py",
        "selector-string",
        '@resource-id="([^"]+)"',
        "Selector parser utility intentionally reads resource-id from catalog-provided XPath.",
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
    blocking = [finding for finding in findings if not is_allowlisted(finding)]
    allowed = [finding for finding in findings if is_allowlisted(finding)]

    if blocking:
        print("Selector hardcode audit failed:")
        for finding in blocking:
            print(f" - {format_finding(finding)}")
        if allowed:
            print(f"\nAllowlisted legacy selector debt: {len(allowed)} finding(s)")
        return 1

    print(
        "Selector hardcode audit OK "
        f"(0 new findings, {len(allowed)} allowlisted legacy finding(s))"
    )
    if args.show_allowed and allowed:
        for finding in allowed:
            print(f" - {format_finding(finding)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
