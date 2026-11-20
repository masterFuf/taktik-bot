"""A cut caption is tapped open at the start of its first line, never on a link, and never left.

The caption is one TextView whose hashtags and mentions are links inside its text: a tap at its
centre can open one. Real screens of TikTok 47.0.3 in French (Pixel 6a, 2026-11-20), anonymized: a
cut caption before the tap and the same video after it (opened), a caption that starts with a
mention (43.1.4), and a photo post whose caption starts with its link « Publication 1 | », whose tap
left the video during the proof, then the back key brought the video again.
Only the device is replaced: the photo it shows, the tap and the back key.
"""

import pytest

from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.shared.device.ui_dump import parse_bounds
from taktik.core.social_media.tiktok.actions.atomic.detection import video_detector as module
from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector
from taktik.core.social_media.tiktok.ui.labels import CAPTION_TAP_HEIGHT, CAPTION_TAP_WIDTH
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
BEFORE = "tt4703_fr_caption_cut_before_tap.xml"
OPENED = "tt4703_fr_caption_opened_after_tap.xml"
POST = "tt4703_fr_caption_photo_post_link.xml"
LEFT = "tt4703_fr_caption_tap_left_video.xml"


def _xml(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class _Phone:
    """Shows `screens[0]`, then `after_tap` once tapped; records the taps and the back key."""

    def __init__(self, shown, after_tap=None, after_back=None):
        self.shown = _xml(shown)
        self.after_tap = _xml(after_tap) if after_tap else None
        self.after_back = _xml(after_back) if after_back else None
        self.taps = []
        self.backs = 0

    def snapshot(self, max_age_s=0.0):
        return ScreenSnapshot(self.shown)

    def human_tap(self, bounds, *, rng=None, quick=False):
        self.taps.append(bounds)
        if self.after_tap:
            self.shown = self.after_tap
        return bounds[0] + 1, bounds[1] + 1

    def press_back(self):
        self.backs += 1
        if self.after_back:
            self.shown = self.after_back


def _detector(phone):
    detector = VideoDetector.__new__(VideoDetector)
    detector.device = phone
    from loguru import logger

    detector.logger = logger
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_SELECTORS

    detector.video_selectors = VIDEO_SELECTORS
    detector._human_like_delay = lambda _kind="general": None
    return detector


@pytest.fixture(autouse=True)
def _french_without_waits(monkeypatch):
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _caption_bounds(name):
    photo = ScreenSnapshot(_xml(name))
    node = photo.elements('//*[contains(@resource-id, ":id/desc")]')[0]
    return parse_bounds(node.attrib["bounds"])


def test_a_caption_that_starts_with_text_is_tapped_at_the_start_of_its_first_line():
    phone = _Phone(BEFORE, after_tap=OPENED)
    detector = _detector(phone)

    caption = detector.get_video_description_full()

    left, top, right, bottom = _caption_bounds(BEFORE)
    assert phone.taps == [(left, top, left + int((right - left) * CAPTION_TAP_WIDTH),
                           top + int((bottom - top) * CAPTION_TAP_HEIGHT))]
    assert detector.last_caption_tap["expanded"] is True and detector.last_caption_tap["reason"] == "opened"
    assert not caption.endswith("plus") and "Voir la traduction" not in caption and phone.backs == 0


def test_a_caption_that_starts_with_a_link_is_not_tapped():
    phone = _Phone("tt4314_fr_liked_video.xml", after_tap=OPENED)
    detector = _detector(phone)

    detector.get_video_description_full()

    assert phone.taps == [] and detector.last_caption_tap["reason"] == "starts_with_link"


def test_a_caption_that_starts_with_a_photo_post_link_is_not_tapped():
    """Video 37 of the proof: « Publication 1 | … », the link of a photo post."""
    phone = _Phone(POST, after_tap=LEFT)
    detector = _detector(phone)

    detector.get_video_description_full()

    assert phone.taps == [] and detector.last_caption_tap["reason"] == "starts_with_link"


def test_a_tap_that_leaves_the_video_goes_back_and_keeps_the_cut_caption(monkeypatch):
    """The same video, had its start been taken for text: the tap opened the post (no caption
    node, its author, « Suivre », its sound), the back key brought the video again."""
    monkeypatch.setattr(module, "caption_starts_plain", lambda _text: True)
    phone = _Phone(POST, after_tap=LEFT, after_back="tt4703_fr_caption_back_on_video.xml")
    detector = _detector(phone)

    caption = detector.get_video_description_full()

    assert phone.backs == 1 and detector.last_caption_tap["reason"] == "left_the_video"
    assert caption.endswith("plus") and "Voir la traduction" not in caption


def test_the_translation_link_after_a_whole_caption_is_not_read_as_its_text():
    """Videos 31 and 32 of the proof: a whole caption, two spaces, then « Voir la traduction »."""
    phone = _Phone("tt4703_fr_caption_whole_translate_link.xml")
    detector = _detector(phone)

    caption = detector.get_video_description_full()

    assert phone.taps == [] and caption and not caption.endswith("Voir la traduction")
    assert caption == caption.rstrip()
