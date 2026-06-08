"""Anti-regression: profile-avatar story ring detection must not count highlights.

Background (2026-06-08): a profile with only "à la une" highlights was reported as
having a watchable story (count_visible_stories == 2), then the click failed with
"No stories found" — the bot never opened the actual story. Root cause: detection
and click used two different, conflated selector sets. count_visible_stories matched
the highlights tray while the click path fell back to a broken selector.

These fixtures are anonymized minimal extracts of real IG v410 (FR) UI dumps:
  - profile live story ring : id=row_profile_header_imageview,
                              content-desc="story de <user> non vue"
  - highlight bubble        : Button under highlights_reel_tray_recycler_view,
                              content-desc="Story de <user>, N sur 0, Vus."
"""

from lxml import etree

from taktik.core.social_media.instagram.actions.atomic.detection.screen_detection import (
    ScreenDetectionMixin,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.story_viewer import (
    STORY_SELECTORS,
)


class _XPathResult:
    def __init__(self, nodes):
        self._nodes = nodes

    @property
    def exists(self) -> bool:
        return len(self._nodes) > 0

    def all(self):
        return self._nodes

    def get(self):
        return self._nodes[0] if self._nodes else None


class _XmlDevice:
    def __init__(self, xml: str):
        self._tree = etree.fromstring(xml.encode("utf-8"))

    def xpath(self, selector: str) -> _XPathResult:
        return _XPathResult(self._tree.xpath(selector))


class _NoopLogger:
    def debug(self, *args, **kwargs):
        return None


class _Detector(ScreenDetectionMixin):
    def __init__(self, xml: str):
        self.device = _XmlDevice(xml)
        self.logger = _NoopLogger()


def _matches(xml: str, selector: str) -> list:
    tree = etree.fromstring(xml.encode("utf-8"))
    return tree.xpath(selector)


# A profile with an active (unseen) story on its avatar ring.
_PROFILE_WITH_UNSEEN_STORY = """
<hierarchy>
  <node resource-id="com.instagram.android:id/row_profile_header">
    <node resource-id="com.instagram.android:id/reel_ring" content-desc="" />
    <node resource-id="com.instagram.android:id/row_profile_header_imageview_frame_layout" clickable="true" content-desc="">
      <node resource-id="com.instagram.android:id/row_profile_header_imageview" content-desc="story de demo_user non vue" />
    </node>
  </node>
</hierarchy>
"""

# A profile with NO live story but several "à la une" highlights — the original bug.
_PROFILE_WITH_ONLY_HIGHLIGHTS = """
<hierarchy>
  <node resource-id="com.instagram.android:id/row_profile_header">
    <node resource-id="com.instagram.android:id/row_profile_header_imageview_frame_layout" clickable="true" content-desc="">
      <node resource-id="com.instagram.android:id/row_profile_header_imageview" content-desc="Photo de profil de demo_user" />
    </node>
  </node>
  <node resource-id="com.instagram.android:id/highlights_reel_tray_recycler_view">
    <node class="android.widget.Button" content-desc="Story de demo_user, 0 sur 0, Vus." />
    <node class="android.widget.Button" content-desc="Story de demo_user, 1 sur 0, Vus." />
  </node>
</hierarchy>
"""

# A profile whose story has already been seen ("vue", not "non vue").
_PROFILE_WITH_SEEN_STORY = """
<hierarchy>
  <node resource-id="com.instagram.android:id/row_profile_header">
    <node resource-id="com.instagram.android:id/row_profile_header_imageview_frame_layout" clickable="true" content-desc="">
      <node resource-id="com.instagram.android:id/row_profile_header_imageview" content-desc="story de demo_user vue" />
    </node>
  </node>
</hierarchy>
"""


def test_unseen_profile_story_ring_is_detected():
    assert len(_matches(_PROFILE_WITH_UNSEEN_STORY, STORY_SELECTORS.profile_unseen_story_avatar)) == 1
    assert ScreenDetectionMixin.has_unseen_profile_story(_Detector(_PROFILE_WITH_UNSEEN_STORY)) is True
    assert ScreenDetectionMixin.count_visible_stories(_Detector(_PROFILE_WITH_UNSEEN_STORY)) == 1


def test_highlights_only_profile_reports_no_story():
    # The regression: highlights must NOT be counted as a watchable story.
    assert _matches(_PROFILE_WITH_ONLY_HIGHLIGHTS, STORY_SELECTORS.profile_unseen_story_avatar) == []
    assert ScreenDetectionMixin.has_unseen_profile_story(_Detector(_PROFILE_WITH_ONLY_HIGHLIGHTS)) is False
    assert ScreenDetectionMixin.count_visible_stories(_Detector(_PROFILE_WITH_ONLY_HIGHLIGHTS)) == 0


def test_seen_story_is_not_reported_as_unseen():
    assert _matches(_PROFILE_WITH_SEEN_STORY, STORY_SELECTORS.profile_unseen_story_avatar) == []
    assert ScreenDetectionMixin.count_visible_stories(_Detector(_PROFILE_WITH_SEEN_STORY)) == 0
