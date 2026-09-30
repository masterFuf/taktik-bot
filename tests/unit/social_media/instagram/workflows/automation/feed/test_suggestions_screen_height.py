"""The suggestions carousel's framing scroll measures the screen like every dump reader.

The height the framing scroll divides its distance by is the device's, as the scroll gesture
measures it. When the device cannot say, it was computed a second way, by hand (the lowest edge of
any widget); it now comes from `dump_screen_size`, the one reading of a dump's screen (decision D9
of 2026-09-27). On the real dumps of the fixtures, both readings agree: nothing moves on screen.
"""

from __future__ import annotations

from taktik.core.shared.device.ui_dump import dump_screen_size, parse_ui_dump
from taktik.core.social_media.instagram.workflows.automation.feed import suggestions
from taktik.core.social_media.instagram.workflows.automation.feed.suggestions import (
    FeedSuggestionsMixin,
)
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
CUT_UNDER_AD = parse_ui_dump((FIXTURES / "ig410_en_feed_carousel_cut_under_ad.xml").read_text(encoding="utf-8"))


class _NoSizeDevice:
    def get_screen_size(self):
        raise RuntimeError("no screen size")


class _SizedDevice:
    def get_screen_size(self):
        return (1080, 2220)


class _Logger:
    def debug(self, _message):
        pass


def _mixin(device) -> FeedSuggestionsMixin:
    mixin = object.__new__(FeedSuggestionsMixin)
    mixin.device = device
    mixin.logger = _Logger()
    return mixin


def test_the_device_size_comes_first():
    assert _mixin(_SizedDevice())._suggestions_screen_height(CUT_UNDER_AD) == 2220


def test_without_it_the_dump_says_its_screen():
    assert _mixin(_NoSizeDevice())._suggestions_screen_height(CUT_UNDER_AD) == dump_screen_size(CUT_UNDER_AD)[1] == 1280


def test_the_dump_reading_is_the_shared_one(monkeypatch):
    monkeypatch.setattr(suggestions, "dump_screen_size", lambda root: (1, 4321))

    assert _mixin(_NoSizeDevice())._suggestions_screen_height(CUT_UNDER_AD) == 4321


def test_no_dump_no_device_no_height():
    assert _mixin(_NoSizeDevice())._suggestions_screen_height(None) == 0
