"""The selector audit sees a label word compared with text read from the screen.

It only knew XPath strings and uiautomator keywords, and stayed green over
`'unlike' in content_desc` in the Feed, a `re.search(r'Photo de profil de ...')` in post_url,
the DM inbox's "non lu" and the TikTok author read (2026-09-24). The `ui-text-comparison` rule
covers the forms found there; a word compared with anything else is none of its business.
"""

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_selector_hardcodes as audit  # noqa: E402


def _findings(source: str) -> list[str]:
    tree = ast.parse(source)
    return [f.value for f in audit.ui_text_comparison_findings(Path("x.py"), tree)]


@pytest.mark.parametrize("source, expected", [
    ("if 'unlike' in content_desc: pass", ["in: 'unlike'"]),
    ("x = 'non lu' in thread_info.get('contentDescription', '').lower()", ["in: 'non lu'"]),
    ("x = 'Suivre' == node.attrib['text']", ["eq: 'Suivre'"]),
    ("x = desc.startswith('Profile ')", ["startswith: 'Profile '"]),
    ("x = desc.endswith(' profile')", ["endswith: ' profile'"]),
    ("import re\nm = re.search(r'Photo de profil de ([a-z]+)', content_desc)",
     ["regex: 'Photo de profil de ([a-z]+)'"]),
])
def test_a_label_word_against_screen_text_is_found(source, expected):
    assert _findings(source) == expected


@pytest.mark.parametrize("source", [
    # A comment body or a log line is not screen text.
    "if 'merci' in text: pass",
    "if 'error' in message: pass",
    # Names from a catalog are the fix, not the defect.
    "x = any(f in content_desc for f in SEL.liked_fragments)",
    # A regex of digits only is a number parser, not a label.
    "import re\nm = re.search(r'(\\d+)\\s*k', desc)",
])
def test_anything_else_is_left_alone(source):
    assert _findings(source) == []


def test_the_runtime_code_passes_the_audit():
    findings = audit.collect_findings()
    blocking = [f for f in findings
                if not audit.is_non_runtime_signature(f) and not audit.is_allowlisted(f)]
    assert blocking == []
