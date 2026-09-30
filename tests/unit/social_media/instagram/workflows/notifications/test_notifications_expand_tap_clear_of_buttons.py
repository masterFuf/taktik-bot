"""The tap that expands a truncated comment ("… suite") never lands on a button of its row.

Seen on the Pixel 4a (lot `notifscan`, scan by the bridge, Instagram 410 in French): the expander is
a span with no node, found by OCR inside the comment's text node; the tap aimed at the word's
centre, jittered by up to 18 px around it, and landed at (424, 2115): in the text node
(253,1940)-(893,2136) AND in the row's « Répondre » button (311,2107)-(463,2209), which overlap by
29 px. That time the text unfolded; another layout could open the reply field of a "read only" scan.

The screen is that capture, anonymized (`ig410_fr_activity_truncated_comment.xml`). OCR cannot run
on a dump: the word's box is DERIVED from the run: centred on the point the run tapped, one line of
the text node high (the node holds four lines, 196 px), five letters wide; and the same box moved by
the 18 px of the old jitter, up and down, since the recorded tap was a sample around the centre.
"""

import random

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.shared.vision.ocr import TextMatch
from taktik.core.social_media.instagram.workflows.notifications import (
    notifications_workflow as module,
)
from unit.paths import CORE

FIXTURE = CORE / "tests/unit/social_media/instagram/fixtures/ig410_fr_activity_truncated_comment.xml"
TEXT_NODE = (253, 1940, 893, 2136)
REPLY = (311, 2107, 463, 2209)
LIKE = (204, 2107, 311, 2209)
TAPPED = (424, 2115)
LINE = (2136 - 1940) // 4


def _inside(point, box):
    x, y = point
    left, top, right, bottom = box
    return left <= x < right and top <= y < bottom


class _Phone:
    def __init__(self):
        self.taps = []

    def long_click(self, x, y, _duration=None):
        self.taps.append((x, y))

    def click(self, x, y):
        self.taps.append((x, y))


def _workflow(phone, word):
    workflow = module.NotificationsEngagementWorkflow.__new__(module.NotificationsEngagementWorkflow)
    workflow.device = phone
    workflow.selectors = module.NOTIFICATION_SELECTORS
    workflow.logger = module.logger
    workflow._expanded_keys = set()
    root = parse_ui_dump(FIXTURE.read_text(encoding="utf-8"))
    workflow._dump_root = lambda: root
    workflow._notify = lambda *a, **k: None
    workflow._on_notifications_screen = lambda: True
    return workflow


def _word(shift):
    """The derived OCR box, kept inside the text node (the OCR reads the node's region only)."""
    x, y = TAPPED[0], TAPPED[1] + shift
    top, bottom = max(TEXT_NODE[1], y - LINE // 2), min(TEXT_NODE[3], y + LINE // 2)
    return TextMatch("suite", 90.0, left=x - 35, top=top, width=70, height=bottom - top)


@pytest.mark.parametrize("shift, tapped", [(0, True), (-18, True), (18, False)])
def test_the_expand_tap_stays_on_the_word_and_off_the_row_s_buttons(monkeypatch, shift, tapped):
    """Moved down by 18 px, the word lies whole in the strip « Répondre » covers: no tap."""
    word = _word(shift)
    monkeypatch.setattr(module, "locate_text_on_screen", lambda *a, **k: [word])
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    random.seed(20260928)

    taps = []
    for _ in range(200):
        phone = _Phone()
        assert _workflow(phone, word)._expand_one_more() is True
        taps.extend(phone.taps)

    on_a_button = [tap for tap in taps if _inside(tap, REPLY) or _inside(tap, LIKE)]
    assert on_a_button == []
    word_box = (word.left, word.top, word.left + word.width, word.top + word.height)
    assert all(_inside(tap, word_box) and _inside(tap, TEXT_NODE) for tap in taps)
    assert len(taps) == (200 if tapped else 0)


def test_a_word_the_buttons_cover_whole_is_not_tapped(monkeypatch):
    """The word entirely inside « Répondre »: nothing to aim at that is not the button."""
    word = TextMatch("suite", 90.0, left=360, top=2110, width=60, height=20)
    monkeypatch.setattr(module, "locate_text_on_screen", lambda *a, **k: [word])
    phone = _Phone()

    assert _workflow(phone, word)._expand_one_more() is True    # the row was tried
    assert phone.taps == []
