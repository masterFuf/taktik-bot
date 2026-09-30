"""A LIVE preview in the For You feed is not a video: it has no author, and it carries readable ids,
per version: the baseline (43.1.4) in the catalogue, 46.9.3 in the overrides.

The screens are real captures, anonymized: TikTok 46.9.3 in French (Pixel 6a), a LIVE preview of
the For You feed and a video opened from a search; TikTok 43.1.4 in French (Pixel 3a), a LIVE
preview and a video of the For You feed.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector
from taktik.core.social_media.tiktok.workflows.common.models import VideoWorkflowStats
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
LIVE = (FIXTURES / "tt4693_fr_live_preview.xml").read_text(encoding="utf-8")
VIDEO = (FIXTURES / "tt4693_fr_search_result_video.xml").read_text(encoding="utf-8")
LIVE_4314 = (FIXTURES / "tt4314_fr_for_you_live_preview.xml").read_text(encoding="utf-8")
VIDEO_4314 = (FIXTURES / "tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


@pytest.fixture
def on_46_9_3():
    apply_version_overrides("tiktok", "46.9.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


def _found(xml):
    device = _Device(xml)
    return any(device.xpath(sel).exists for sel in VIDEO_SELECTORS.live_preview)


def test_on_the_baseline_the_live_preview_is_found_and_a_video_is_not():
    """43.1.4, Pixel 3a in French: the For You preview the Lab auto-test landed on (anonymized)."""
    assert _found(LIVE_4314)
    assert not _found(VIDEO_4314)


def test_on_46_9_3_the_live_preview_is_found_and_a_video_is_not(on_46_9_3):
    assert _found(LIVE)
    assert not _found(VIDEO)


PHOTO = object()  # every reader is stubbed: the photo is never looked at


def _detector(author, live, calls):
    detector = object.__new__(VideoDetector)

    def record(name, value):
        def reader(*_a, **_k):
            calls.append(name)
            return value
        return reader

    detector.is_ad_video = record("is_ad", False)
    detector.is_live_preview = record("is_live", live)
    detector.get_video_author = record("author", author)
    detector.get_video_description_parsed = record("desc", {"description_text": None, "hashtags": []})
    for name in ("get_video_sound", "get_video_like_count", "is_video_liked", "is_video_favorited"):
        setattr(detector, name, record(name, None))
    return detector


def test_a_screen_without_author_is_asked_whether_it_is_a_live():
    calls = []
    info = _detector(None, True, calls).get_video_info(screen=PHOTO)
    assert info["is_live"] is True


def test_a_video_with_an_author_pays_no_extra_read():
    calls = []
    info = _detector("demo_author", True, calls).get_video_info(screen=PHOTO)
    assert info["is_live"] is False
    assert "is_live" not in calls


def test_the_run_stats_carry_the_skipped_lives():
    stats = VideoWorkflowStats()
    stats.lives_skipped += 1
    assert stats.to_dict()["lives_skipped"] == 1
