"""Audit how the bot reads LANGUAGE-DEPENDENT UI text.

Selectors find a node; a label says what that node *is*. `audit_selector_hardcodes.py`
guards the first half. This script guards the second, which failed silently three times in
a row (hashtag counters, likers popup, TikTok profile stats) because a missed label reads
exactly like "nothing on screen" — no exception, no error line, just zero.

Three rules:

1. LOCALE XPATH MUST COMPILE. `//x[@text='J'aime']` is not valid XPath: the apostrophe
   closes the literal. uiautomator2 swallows the parse error, so the selector silently
   matches nothing forever.

2. A LOCALE XPATH MUST NOT HINGE ON ONE APOSTROPHE SHAPE. Instagram and TikTok render the
   TYPOGRAPHIC apostrophe (U+2019) in "J’aime" / "Don’t allow"; catalogues get typed with
   the ASCII one. An xpath naming one form must name the other too. Bare labels are exempt:
   they are compared through `shared.text.normalize_ui_label`, which folds both.

3. RUNTIME CODE MUST NOT COMPARE UI TEXT TO A HARDCODED LANGUAGE LITERAL. Localized words
   belong in `ui/selectors/locales/**` and are reached via `L(...)`.

Run: python scripts/audit_ui_language.py [--show-allowed]
"""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]

LOCALE_DIRS = (
    ROOT / "taktik" / "core" / "social_media" / "instagram" / "ui" / "selectors" / "locales",
    ROOT / "taktik" / "core" / "social_media" / "tiktok" / "ui" / "selectors" / "locales",
)

SCAN_ROOTS = (
    ROOT / "taktik" / "core" / "social_media",
    ROOT / "taktik" / "core" / "app" / "email",
)

STRAIGHT = "'"
CURLY = "’"
IN_WORD_STRAIGHT = re.compile(r"[A-Za-zÀ-ÿ]'[A-Za-zÀ-ÿ]")
IN_WORD_CURLY = re.compile(r"[A-Za-zÀ-ÿ]’[A-Za-zÀ-ÿ]")

# Sites still comparing UI text to a hardcoded literal. Each carries BOTH the French and
# the English form, so they work on the fleet we run today and break only on a third
# language. Listed — not silently tolerated — so the debt stays visible.
ALLOWLIST = {
    # story highlight titles: EN and FR patterns, side by side
    "taktik/core/social_media/instagram/actions/atomic/detection/screen_detection.py",
    # author from a profile-picture content-desc; PRIORITY 1 above it is language-agnostic
    "taktik/core/social_media/instagram/actions/business/workflows/post_url/mixins/url_handling.py",
    # already-liked guard, EN + FR
    "taktik/core/social_media/threads/workflows/search_and_interact.py",
    # "<name> profile" / "Profil <name>" + "Sound:"/"Son :", EN + FR
    "taktik/core/social_media/tiktok/actions/atomic/video_detector.py",
    # "connected as" / "connecté en tant que", EN + FR
    "taktik/core/app/email/gmail/workflows/account.py",
    # already-liked guard on a feed post ("unlike"/"liked"/"ne plus aimer"), EN + FR. High
    # stakes — a miss re-taps a liked post, i.e. UNLIKES it — but covered on both languages.
    "taktik/core/social_media/instagram/actions/business/workflows/feed/post_actions.py",
    # counter-extraction FALLBACKS ("N likes"/"N J'aime", "N comments"/"N commentaires"),
    # EN + FR with re.IGNORECASE. The PRIMARY path is `count_from_counter_label`, which is
    # language-free; these only run when the counter element itself was not found.
    "taktik/core/social_media/instagram/ui/extractors.py",
}

# `info` is deliberately absent: `'hashtag' in workflow_info` is a dict-key test on our own
# payload, not a substring test on screen text. Real UI access is named for what it reads
# (content-desc, text, label…), and reaching it through `.info.get('contentDescription')`
# resolves to that key anyway.
UI_VARS = re.compile(
    r"(content_?desc|contentDescription|text$|_text$|label|title|caption|desc|"
    r"button|element|screen|node|name|value|line|row)",
    re.IGNORECASE,
)
NOT_UI = re.compile(
    r"(url|path|file|platform|mode|status|state|kind|type|key|id$|_id|json|payload|"
    r"config|env|arg|cmd|command|query|sql|version|model|provider|locale|lang)",
    re.IGNORECASE,
)
TECH = re.compile(r"[._/:=\d]")
KEYWORDS = {"true", "false", "none", "null", "yes", "no", "ok", "utf", "and", "or", "not",
            "json", "xml", "html", "notification"}


@dataclass(frozen=True)
class Finding:
    rule: str
    path: str
    line: int
    detail: str

    def format(self) -> str:
        return f"[{self.rule}] {self.path}:{self.line} — {self.detail}"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_xpath(value: str) -> bool:
    return value.lstrip().startswith(("//", "(//", "./", "*[", "\\*["))


def looks_like_ui_text(value: str) -> bool:
    if len(value) < 3 or len(value) > 80:
        return False
    if value.strip().lower() in KEYWORDS:
        return False
    if TECH.search(value):
        return False
    if value.startswith(("//", "(//", "com.", "android.", "http", "@")):
        return False
    return bool(re.search(r"[A-Za-z]", value))


def ui_target(name: Optional[str]) -> bool:
    name = name or ""
    if NOT_UI.search(name):
        return False
    return bool(UI_VARS.search(name))


def var_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
        return var_name(node.func)
    if isinstance(node, ast.Subscript):
        return var_name(node.value)
    return ""


def natural_words(pattern: str) -> int:
    stripped = re.sub(r"\\[a-zA-Z]", " ", pattern)
    stripped = re.sub(r"\(\?P?<[^>]*>", " ", stripped)
    stripped = re.sub(r"[\[\](){}|*+?^$.\\]", " ", stripped)
    return len(re.findall(r"[A-Za-zÀ-ÿ]{3,}", stripped))


def audit_locales() -> List[Finding]:
    try:
        from lxml import etree
    except ImportError:
        etree = None

    findings: List[Finding] = []
    for directory in LOCALE_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.py")):
            if path.name == "__init__.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                    continue
                value = node.value
                if not is_xpath(value):
                    continue  # bare labels go through normalize_ui_label
                if etree is not None:
                    try:
                        etree.XPath(value)
                    except Exception as exc:
                        findings.append(Finding(
                            "xpath-invalide", rel(path), node.lineno,
                            f"{value[:70]} ({str(exc)[:50]})",
                        ))
                        continue
                has_straight = bool(IN_WORD_STRAIGHT.search(value))
                has_curly = bool(IN_WORD_CURLY.search(value))
                if has_straight != has_curly:
                    shape = "droite (U+0027)" if has_straight else "typographique (U+2019)"
                    findings.append(Finding(
                        "apostrophe-unique", rel(path), node.lineno,
                        f"ne connait que l'apostrophe {shape}: {value[:70]}",
                    ))
    return findings


def audit_code() -> List[Finding]:
    findings: List[Finding] = []
    for scan_root in SCAN_ROOTS:
        if not scan_root.exists():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            relative = rel(path)
            if "/locales/" in f"/{relative}" or "__pycache__" in relative:
                continue
            if "/tests/" in f"/{relative}":
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            except (SyntaxError, UnicodeDecodeError) as exc:
                # NOT `continue`. A file the audit cannot read is a file the audit does not
                # guard, and silence makes that indistinguishable from a clean file — the
                # exact failure mode this whole script exists to catch. 17 files opened with
                # a UTF-8 BOM used to be swallowed here (ast.parse rejects U+FEFF in an
                # already-decoded string), among them `ui/extractors.py` and `likers_base.py`
                # — the hottest UI-reading code we own. Reading as utf-8-sig fixed those;
                # anything else left unreadable must be shouted about, not hidden.
                findings.append(Finding("fichier-illisible", relative, 1, str(exc)[:80]))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    for op, comparator in zip(node.ops, node.comparators):
                        if (isinstance(op, ast.In)
                                and isinstance(node.left, ast.Constant)
                                and isinstance(node.left.value, str)
                                and ui_target(var_name(comparator))
                                and looks_like_ui_text(node.left.value)):
                            findings.append(Finding(
                                "langue-en-dur", relative, node.lineno,
                                f"'{node.left.value}' in {var_name(comparator)}",
                            ))
                        # A VARIABLE compared to a literal can hold screen text; a CALL
                        # result cannot — `classify_action_button(desc) == 'like'` compares
                        # our own enum, not what the phone renders.
                        if (isinstance(op, ast.Eq)
                                and isinstance(node.left, (ast.Name, ast.Attribute))
                                and isinstance(comparator, ast.Constant)
                                and isinstance(comparator.value, str)
                                and ui_target(var_name(node.left))
                                and looks_like_ui_text(comparator.value)):
                            findings.append(Finding(
                                "langue-en-dur", relative, node.lineno,
                                f"{var_name(node.left)} == '{comparator.value}'",
                            ))
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("startswith", "endswith"):
                        name = var_name(node.func.value)
                        for arg in node.args:
                            if (isinstance(arg, ast.Constant)
                                    and isinstance(arg.value, str)
                                    and ui_target(name)
                                    and looks_like_ui_text(arg.value)):
                                findings.append(Finding(
                                    "langue-en-dur", relative, node.lineno,
                                    f"{name}.{node.func.attr}('{arg.value}')",
                                ))
                    if (node.func.attr in ("search", "match", "findall", "fullmatch")
                            and len(node.args) >= 2):
                        pattern, target = node.args[0], node.args[1]
                        if (isinstance(pattern, ast.Constant)
                                and isinstance(pattern.value, str)
                                and ui_target(var_name(target))
                                and natural_words(pattern.value) >= 2):
                            findings.append(Finding(
                                "langue-en-dur", relative, node.lineno,
                                f"re.{node.func.attr}('{pattern.value[:50]}', {var_name(target)})",
                            ))
    return findings


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show-allowed", action="store_true",
                        help="list the allowlisted sites too")
    args = parser.parse_args(list(argv) if argv is not None else None)

    locale_findings = audit_locales()
    code_findings = audit_code()

    new = [f for f in code_findings if f.path not in ALLOWLIST]
    allowed = [f for f in code_findings if f.path in ALLOWLIST]
    blocking = locale_findings + new

    if blocking:
        print(f"UI language audit FAILED — {len(blocking)} finding(s)\n")
        for finding in blocking:
            print(f" - {finding.format()}")
        print("\nSelectors and localized words belong in ui/selectors/locales/**, reached")
        print("via L(...); compare labels through shared.text.normalize_ui_label.")
        return 1

    print(
        "UI language audit OK "
        f"(0 new findings, {len(allowed)} allowlisted bilingual site(s))"
    )
    if args.show_allowed:
        for finding in allowed:
            print(f" - {finding.format()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
