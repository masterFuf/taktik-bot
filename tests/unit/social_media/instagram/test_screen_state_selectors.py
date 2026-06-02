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


class _ScreenProbe:
    def __init__(self, xml: str):
        self._tree = etree.fromstring(xml.encode("utf-8"))
        self.detection_selectors = DetectionSelectors()
        self.logger = _NoopLogger()

    def _is_element_present(self, selectors):
        if isinstance(selectors, str):
            selectors = [selectors]
        return any(self._tree.xpath(selector) for selector in selectors)


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


def test_french_language_filter_keeps_neutral_selected_feed_tab():
    selectors = DetectionSelectors()
    filtered = filter_selectors(selectors.home_screen_indicators, "fr")

    assert '//*[@resource-id="com.instagram.android:id/feed_tab" and @selected="true"]' in filtered
    assert '//*[contains(@content-desc, "Home") and @selected="true"]' not in filtered
