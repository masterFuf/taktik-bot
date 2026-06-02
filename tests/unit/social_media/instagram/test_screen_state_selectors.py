from lxml import etree

from taktik.core.social_media.instagram.actions.atomic.detection.screen_detection import (
    ScreenDetectionMixin,
)
from taktik.core.social_media.instagram.ui.language import filter_selectors
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DetectionSelectors


def _matches(xml: str, selectors: list[str]) -> bool:
    tree = etree.fromstring(xml.encode("utf-8"))
    return any(tree.xpath(selector) for selector in selectors)


class _NoopLogger:
    def debug(self, *args, **kwargs):
        return None


class _ScreenProbe(ScreenDetectionMixin):
    def __init__(self, xml: str, *, enable_batch: bool = False):
        self._tree = etree.fromstring(xml.encode("utf-8"))
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


def test_feed_post_header_does_not_match_profile_surface():
    selectors = DetectionSelectors()
    xml = """
    <hierarchy>
      <node resource-id="com.instagram.android:id/feed_tab" content-desc="Home" selected="true" />
      <node resource-id="com.instagram.android:id/row_feed_profile_header" />
      <node resource-id="com.instagram.android:id/action_bar_title" text="Instagram" />
      <node text="Follow" />
    </hierarchy>
    """

    assert _matches(xml, selectors.home_screen_indicators) is True
    assert _matches(xml, selectors.profile_surface_indicators) is False


def test_home_feed_with_post_header_is_not_reported_as_profile_screen():
    probe = _ScreenProbe(
        """
        <hierarchy>
          <node resource-id="com.instagram.android:id/feed_tab" content-desc="Home" selected="true" />
          <node resource-id="com.instagram.android:id/row_feed_profile_header" />
          <node resource-id="com.instagram.android:id/action_bar_title" text="Instagram" />
          <node text="Follow" />
        </hierarchy>
        """
    )

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is False


def test_real_profile_header_matches_profile_surface():
    selectors = DetectionSelectors()
    xml = """
    <hierarchy>
      <node resource-id="com.instagram.android:id/profile_header_container">
        <node resource-id="com.instagram.android:id/row_profile_header" />
      </node>
    </hierarchy>
    """

    assert _matches(xml, selectors.profile_surface_indicators) is True
    assert _matches(xml, selectors.profile_screen_indicators) is True


def test_real_profile_header_is_reported_as_profile_screen():
    probe = _ScreenProbe(
        """
        <hierarchy>
          <node resource-id="com.instagram.android:id/profile_header_container">
            <node resource-id="com.instagram.android:id/row_profile_header" />
          </node>
        </hierarchy>
        """
    )

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is True


def test_screen_detection_reuses_batched_signal_snapshot():
    probe = _ScreenProbe(
        """
        <hierarchy>
          <node resource-id="com.instagram.android:id/feed_tab" content-desc="Home" selected="true" />
          <node resource-id="com.instagram.android:id/row_feed_profile_header" />
        </hierarchy>
        """,
        enable_batch=True,
    )

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is False
    assert ScreenDetectionMixin.is_on_home_screen(probe) is True
    assert probe.batch_calls == 1


def test_batched_negatives_avoid_live_fallback_on_unknown_screen():
    # An unknown screen makes every batched signal negative. The single dump must
    # stay authoritative: no live re-probing of every indicator list.
    probe = _ScreenProbe(
        """
        <hierarchy>
          <node resource-id="com.instagram.android:id/some_unrelated_view" />
        </hierarchy>
        """,
        enable_batch=True,
    )

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is False
    assert ScreenDetectionMixin.is_on_home_screen(probe) is False
    assert ScreenDetectionMixin.is_on_search_screen(probe) is False
    assert ScreenDetectionMixin.is_on_post_screen(probe) is False

    assert probe.batch_calls == 1
    assert probe.live_calls == 0


def test_screen_detection_falls_back_without_batch_xpath_check():
    probe = _ScreenProbe(
        """
        <hierarchy>
          <node resource-id="com.instagram.android:id/profile_header_container" />
        </hierarchy>
        """
    )

    assert ScreenDetectionMixin.is_on_profile_screen(probe) is True


def test_french_language_filter_keeps_neutral_selected_feed_tab():
    selectors = DetectionSelectors()
    filtered = filter_selectors(selectors.home_screen_indicators, "fr")

    assert '//*[@resource-id="com.instagram.android:id/feed_tab" and @selected="true"]' in filtered
    assert '//*[contains(@content-desc, "Home") and @selected="true"]' not in filtered


def test_unselected_search_tabs_do_not_match_search_screen():
    selectors = DetectionSelectors()
    xml = """
    <hierarchy>
      <node resource-id="com.instagram.android:id/feed_tab" content-desc="Home" selected="true" />
      <node resource-id="com.instagram.android:id/search_tab" content-desc="Search" selected="false" />
      <node resource-id="com.instagram.android:id/clips_tab" content-desc="Reels" selected="false" />
    </hierarchy>
    """

    assert _matches(xml, selectors.search_screen_indicators) is False
