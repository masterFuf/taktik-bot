"""The persona analysis reads the comment bodies Instagram 410 renders with Litho.

Found by the Lab auto-test on 2026-09-28 and reproduced on the Pixel 3a (Instagram 410 in English)
on a post of a public account: `comment.read_thread` read 2 comments on the open sheet,
`comment.read_visible_texts` (the persona analysis's reader) 0. On 410 the bodies are not in the
accessibility tree, only in the Litho dump (`dumpsys activity top`); the persona reader read the
tree alone (the body ids, then the rows of IG 442), a second way of reading the same comments that
missed the source the thread reader uses. It now reads through the thread's reader when the tree has
no body.

The screen is that capture, anonymized (fixture `ig410_en_comment_sheet_litho_bodies.xml`), with the
Litho rows of the `dumpsys activity top` taken at the same moment, usernames given the fixture's
values and bodies replaced (`ig410_en_comment_sheet_litho_bodies.dumpsys.txt`).
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.compat.diagnostics.actions.instagram import register_actions
from bridges.compat.diagnostics.runtime.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.workflows.common import comment_reading

FIXTURES = Path(__file__).resolve().parents[2] / "social_media" / "instagram" / "fixtures"
SHEET = (FIXTURES / "ig410_en_comment_sheet_litho_bodies.xml").read_text(encoding="utf-8")
LITHO = (FIXTURES / "ig410_en_comment_sheet_litho_bodies.dumpsys.txt").read_text(encoding="utf-8")

#: The two bodies the sheet shows in full (the third row is cut by the screen: no text in the dump).
BODIES = [
    "First comment body of the thread, read from the Litho dump.",
    "Second comment body, longer, cut by the screen in the dump.",
]


class _Phone:
    """uiautomator2 as the facade touches it: `xpath()`, one dump, and the phone's serial."""

    wait_timeout = 1.0
    serial = "PHONE-SERIAL"

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "demo.Activity"}


@pytest.fixture(autouse=True)
def phone_answers(monkeypatch):
    before = locales.active_locale()
    locales.set_active_locale("en")
    register_actions()
    asked = []

    def adb_shell(serial, command, **_kwargs):
        asked.append((serial, command))
        assert command == ["dumpsys", "activity", "top"]
        return SimpleNamespace(stdout=LITHO, stderr="", returncode=0)

    monkeypatch.setattr(comment_reading, "run_adb_shell_process", adb_shell)
    yield asked
    locales.set_active_locale(before)


def _bundle():
    return build_instagram_action_bundle(create_instagram_device_facade(_Phone(SHEET)))


def test_the_thread_reader_reads_the_two_bodies_of_the_sheet():
    result = INSTAGRAM_ACTIONS["comment.read_thread"](_bundle(), {})
    assert [c["text"] for c in result["details"]["comments"]] == BODIES


def test_the_persona_reader_reads_the_same_bodies(phone_answers):
    result = INSTAGRAM_ACTIONS["comment.read_visible_texts"](_bundle(), {})
    assert result["success"] is True
    assert result["details"]["texts"] == BODIES
    assert phone_answers == [("PHONE-SERIAL", ["dumpsys", "activity", "top"])]
