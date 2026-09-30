"""Which screen Instagram shows, read on real screens of Instagram 410.0.0.53.71 (fixtures).

A post header on the home feed is not a profile; a profile header is. The screens are real dumps,
anonymized: the English home feed with its suggestions carousel, the French one, the connected
account's profile in both languages, a profile opened from the search, and the information window
of the story editor, which none of the four signals describes. They are read the way production
reads a dump (`parse_ui_dump`).

On some 410 home feeds the selection sits on the tab's icon (`tab_icon` under `feed_tab`), not on
`feed_tab` itself, and `feed_timeline` is not in the tree: proven on a Pixel 3 (FR, "Pour vous"
feed), whose dump is `ig410_fr_home_feed_tab_icon_selected.xml`; the French home feed
fixture has the same shape. Those screens are also read through the selector rewrite every
Instagram bridge applies (`CloneAwareDeviceProxy.rewrite_xpath`), as production reads them.
"""

import pytest

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.actions.atomic.detection.screen_detection import (
    ScreenDetectionMixin,
)
from taktik.core.social_media.instagram.ui.language import filter_selectors
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DetectionSelectors
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


HOME_EN = _screen("ig410_en_feed_carousel_framed.xml")
HOME_FR = _screen("ig410_fr_home_feed.xml")
# Pixel 3, Instagram 410.0.0.53.71, French, "Pour vous" feed.
HOME_FR_TAB_ICON = _screen("ig410_fr_home_feed_tab_icon_selected.xml")
PROFILES = {
    "own_en": _screen("ig410_en_own_profile.xml"),
    "own_fr": _screen("ig410_fr_own_profile.xml"),
    "from_search_fr": _screen("ig410_fr_profile_opened_from_search.xml"),
    "with_message_button_en": _screen("ig410_en_profile_with_message_button.xml"),
}
STORY_WINDOW = _screen("ig410_en_story_share_information_window.xml")


def _matches(xml: str, selectors: list[str]) -> bool:
    root = parse_ui_dump(xml)
    return any(root.xpath(selector) for selector in selectors)


class _NoopLogger:
    def debug(self, *args, **kwargs):
        return None


class _ScreenProbe(ScreenDetectionMixin):
    def __init__(self, xml: str, *, enable_batch: bool = False):
        self._tree = parse_ui_dump(xml)
        self.detection_selectors = DetectionSelectors()
        self.logger = _NoopLogger()
        self.device = self if enable_batch else _LiveOnlyDevice()
        self.batch_calls = 0
        self.live_calls = 0

    def _is_element_present(self, selectors):
        self.live_calls += 1
        if isinstance(selectors, str):
            selectors = [selectors]
        return any(self._tree.xpath(selector) for selector in selectors)

    def batch_xpath_check(self, selectors_dict: dict[str, list[str]]) -> dict[str, bool]:
        self.batch_calls += 1
        return {
            name: any(self._tree.xpath(selector) for selector in selectors)
            for name, selectors in selectors_dict.items()
        }


class _LiveOnlyDevice:
    pass


HOMES = {"en": HOME_EN, "fr": HOME_FR, "fr_tab_icon": HOME_FR_TAB_ICON}


def _production_photo(xml: str) -> ScreenSnapshot:
    """The dump as the facade reads it: every id equality rewritten by the clone proxy."""
    proxy = CloneAwareDeviceProxy(object(), "com.instagram.android")
    return ScreenSnapshot(xml, rewrite=proxy.rewrite_xpath)


@pytest.mark.parametrize("xml", HOMES.values(), ids=HOMES.keys())
def test_feed_post_header_does_not_match_profile_surface(xml):
    selectors = DetectionSelectors()

    assert _matches(xml, selectors.profile_surface_indicators) is False


@pytest.mark.parametrize("xml", HOMES.values(), ids=HOMES.keys())
def test_every_home_feed_is_a_home_screen(xml):
    assert _matches(xml, DetectionSelectors().home_screen_indicators) is True


def test_the_home_tab_selected_on_its_icon_only_is_the_home_screen():
    """The phone's shape: `feed_tab` selected="false", its `tab_icon` selected="true", no
    `feed_timeline`. Every earlier home signal missed it."""
    root = parse_ui_dump(HOME_FR_TAB_ICON)
    assert not root.xpath('//*[@resource-id="com.instagram.android:id/feed_tab" and @selected="true"]')
    assert not root.xpath('//*[contains(@resource-id, "feed_timeline")]')

    probe = _ScreenProbe(HOME_FR_TAB_ICON, enable_batch=True)
    assert ScreenDetectionMixin.is_on_home_screen(probe) is True
    assert ScreenDetectionMixin.is_on_search_screen(probe) is False
    assert ScreenDetectionMixin.is_on_profile_screen(probe) is False


@pytest.mark.parametrize("xml", HOMES.values(), ids=HOMES.keys())
def test_home_signal_answers_through_the_clone_proxy_rewrite(xml):
    photo = _production_photo(xml)
    indicators = filter_selectors(DetectionSelectors().home_screen_indicators, "fr")

    assert photo.exists(indicators) is True
    assert photo.exists(DetectionSelectors().search_screen_indicators) is False


def test_an_unselected_tab_icon_is_not_its_screen():
    """`search_tab` and its icon are on every screen with the tab bar: on the home feed its icon
    is not the selected one, so the icon form of the search signal stays silent."""
    icon_form = [s for s in DetectionSelectors().search_screen_indicators if "tab_icon" in s]
    assert icon_form
    for xml in HOMES.values():
        assert _matches(xml, icon_form) is False


@pytest.mark.parametrize("xml", HOMES.values(), ids=HOMES.keys())
def test_home_feed_with_post_header_is_not_reported_as_profile_screen(xml):
    assert ScreenDetectionMixin.is_on_profile_screen(_ScreenProbe(xml)) is False


@pytest.mark.parametrize("xml", PROFILES.values(), ids=PROFILES.keys())
def test_real_profile_header_matches_profile_surface(xml):
    selectors = DetectionSelectors()

    assert _matches(xml, selectors.profile_surface_indicators) is True
    assert _matches(xml, selectors.profile_screen_indicators) is True


@pytest.mark.parametrize("xml", PROFILES.values(), ids=PROFILES.keys())
def test_real_profile_header_is_reported_as_profile_screen(xml):
    assert ScreenDetectionMixin.is_on_profile_screen(_ScreenProbe(xml)) is True


def test_screen_detection_reuses_batched_signal_snapshot():
    probe = _ScreenProbe(HOME_EN, enable_batch=True)

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is False
    assert ScreenDetectionMixin.is_on_home_screen(probe) is True
    assert probe.batch_calls == 1


def test_batched_negatives_avoid_live_fallback_on_unknown_screen():
    # A screen no signal describes makes every batched signal negative. The single dump must
    # stay authoritative: no live re-probing of every indicator list.
    probe = _ScreenProbe(STORY_WINDOW, enable_batch=True)

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is False
    assert ScreenDetectionMixin.is_on_home_screen(probe) is False
    assert ScreenDetectionMixin.is_on_search_screen(probe) is False
    assert ScreenDetectionMixin.is_on_post_screen(probe) is False

    assert probe.batch_calls == 1
    assert probe.live_calls == 0


def test_screen_detection_falls_back_without_batch_xpath_check():
    probe = _ScreenProbe(PROFILES["own_fr"])

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is True
    assert probe.live_calls >= 1


def test_french_language_filter_keeps_neutral_selected_feed_tab():
    selectors = DetectionSelectors()
    filtered = filter_selectors(selectors.home_screen_indicators, "fr")

    assert '//*[@resource-id="com.instagram.android:id/feed_tab" and @selected="true"]' in filtered
    assert '//*[contains(@content-desc, "Home") and @selected="true"]' not in filtered
    assert any("tab_icon" in selector for selector in filtered)


@pytest.mark.parametrize("xml", HOMES.values(), ids=HOMES.keys())
def test_unselected_search_tabs_do_not_match_search_screen(xml):
    assert _matches(xml, DetectionSelectors().search_screen_indicators) is False
