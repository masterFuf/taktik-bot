"""The feed crawl knows an ad as the Feed knows it, in every language the catalogue speaks.

Instagram 410 in English labels a sponsored post "Ad", in the secondary label under its author, and a
video ad carries no "Sponsored" description anywhere: the crawl, which looked only for the
"Sponsored"/"Sponsorisé" tokens of a description, took it for a real post. The Feed workflow has
always read the label (`FEED_SELECTORS.sponsored_indicators`, `"Ad"` matched exactly); the crawl now
reads that same catalogue.

Measured on the 410 corpus (home feed, English): 62 screens show an ad the catalogue reads, and on 41
of them the crawl saw no ad marker at all. In French, 102 of 102. Found by the Lab auto-test of
2026-10-03 on the Pixel 3a: `scroll.reveal_post` stopped on such a video ad, framed it as a real
post, and failed.

The screens are real dumps, anonymized: Instagram 410 in English on a Pixel 3a (a video ad labelled
"Ad", 2026-09-27; a real post; an ad below a carousel, the share sheet open over it), on a 576-wide
device (an ad above a carousel, June), and Instagram 410 in French on a Pixel 3a (a sponsored post
framed, a real post under a sponsored one).
"""

import pytest

from taktik.core.shared.device.snapshot import SnapshotSource
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll import FeedScrollMixin
from taktik.core.social_media.instagram.ui.selectors import locales
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


class _Log:
    def debug(self, *args, **kwargs):
        pass

    info = warning = debug


class _Phone:
    """The device as the crawl reads it: one photo of the capture per question."""

    def __init__(self, xml):
        self._source = SnapshotSource(lambda *args, **kwargs: xml)

    def snapshot(self, max_age_s=0.0):
        return self._source.snapshot()


class _Crawl(FeedScrollMixin):
    """The production crawl on a phone that shows one capture."""

    def __init__(self, name):
        xml = (FIXTURES / name).read_text(encoding="utf-8")
        width = height = 0
        for node in parse_ui_dump(xml).iter():
            if node.get("bounds"):
                right, bottom = node.get("bounds").split("][")[1].rstrip("]").split(",")
                width, height = max(width, int(right)), max(height, int(bottom))
        self.device = _Phone(xml)
        self.screen_width, self.screen_height = width, height
        self.logger = _Log()

    def dominant_is_ad(self):
        anchors = self._read_feed_anchors()
        assert anchors["on_feed"]
        return self._dominant_is_ad(anchors)


@pytest.fixture
def english():
    before = locales.active_locale()
    locales.set_active_locale("en")
    yield
    locales.set_active_locale(before)


@pytest.fixture
def french():
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)


def test_a_video_ad_labelled_ad_is_an_ad_for_the_crawl(english):
    assert _Crawl("ig410_en_home_feed_video_ad_labelled_ad.xml").dominant_is_ad() is True


def test_the_label_is_read_on_another_screen_size_too(english):
    assert _Crawl("ig410_en_feed_carousel_cut_under_ad.xml").dominant_is_ad() is True


def test_an_ad_label_under_the_next_header_does_not_make_the_post_above_an_ad(english):
    """The share sheet is open over a carousel; the ad starts below it, with its own header."""
    assert _Crawl("ig410_en_share_sheet_over_sponsored_post.xml").dominant_is_ad() is False


def test_a_real_post_stays_a_real_post(english):
    assert _Crawl("ig410_en_feed_post_hours_ago.xml").dominant_is_ad() is False


def test_the_crawl_still_reads_a_french_ad(french):
    assert _Crawl("ig410_fr_feed_two_captions.xml").dominant_is_ad() is True


def test_a_french_post_under_an_ad_of_the_next_row_stays_a_real_post(french):
    assert _Crawl("ig410_fr_home_feed_framed_post_hides_likes.xml").dominant_is_ad() is False
