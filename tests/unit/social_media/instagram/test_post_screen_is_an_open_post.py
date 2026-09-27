"""`is_on_post_screen` answers "a post is open": the post viewer or the Reels player, never the feed.

Found by the Lab auto-test on 2026-09-28 (Pixel 3a, Instagram 410 in English): the detection said
yes on the home feed and on the notifications. Its signals were a post's like button, which every
post of the feed carries, and any description containing "Like", which the notification rows and
the story viewer's heart carry. And it said no on a post opened from a grid in French, where the
row's buttons were below the screen. Its production callers mean an opened post: the single-post
branch of the like (the Reels player), and the story workflow that backs out of a post its last tap
opened on the profile grid.

The screens are real captures of Instagram 410 and 447 (Pixel 3a, 4a, 6a), anonymized, read through
the Lab's own Instagram facade (one photo of the screen, as `batch_xpath_check` asks it).
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.compat.diagnostics.runtime.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors import locales

FIXTURES = Path(__file__).parent / "fixtures"


class _Phone:
    """uiautomator2 as the facade touches it: `xpath()` and a dump of one screen."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.instagram.android", "activity": "demo.Activity"}


def _post_open(name: str) -> bool:
    before = locales.active_locale()
    locales.set_active_locale("fr" if "_fr_" in name else "en")
    try:
        xml = (FIXTURES / name).read_text(encoding="utf-8")
        bundle = build_instagram_action_bundle(create_instagram_device_facade(_Phone(xml)))
        return bundle.detection.is_on_post_screen()
    finally:
        locales.set_active_locale(before)


@pytest.mark.parametrize("name", [
    # The home feed: posts with their like buttons, none of them "open".
    "ig410_en_feed_post_day_ago.xml",
    "ig410_en_feed_carousel_framed.xml",
    "ig410_en_home_feed_reel_row.xml",
    "ig410_fr_feed_caption_with_hashtags.xml",
    "ig410_fr_feed_two_captions.xml",
    "ig447_fr_home_feed_cold_start.xml",
    # The notifications: rows whose descriptions say "Like".
    "ig410_en_notifications.xml",
    # A story: its heart is described "Like".
    "ig410_en_story_viewer.xml",
])
def test_a_screen_where_no_post_is_open_answers_no(name):
    assert _post_open(name) is False


@pytest.mark.parametrize("name", [
    # A post opened from a profile grid, its buttons on screen or below it.
    "ig410_en_profile_posts_next_photo_framed.xml",
    "ig410_en_profile_posts_video_row_below_screen.xml",
    "ig410_fr_post_opened_from_grid.xml",
    "ig447_fr_profile_posts_list.xml",
    # The Reels player.
    "ig410_en_reel_viewer.xml",
    "ig410_fr_reel_viewer_paused.xml",
    "ig447_fr_reel_open.xml",
])
def test_an_open_post_answers_yes(name):
    assert _post_open(name) is True
