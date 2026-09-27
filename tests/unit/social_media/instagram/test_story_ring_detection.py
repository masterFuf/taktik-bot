"""Anti-regression: profile-avatar story ring detection must not count highlights.

Background (2026-06-08): a profile with only "à la une" highlights was reported as
having a watchable story (count_visible_stories == 2), then the click failed with
"No stories found" — the bot never opened the actual story. Root cause: detection
and click used two different, conflated selector sets. count_visible_stories matched
the highlights tray while the click path fell back to a broken selector.

The screens are real profiles of Instagram 410.0.0.53.71 in French, anonymized, each with its
highlights tray ("à la une": Buttons under highlights_reel_tray_recycler_view, a localized
content-desc carrying the story position):
  - an unseen story on the avatar (id=row_profile_header_imageview, content-desc
    "story de <user> non vue"), Pixel 3;
  - no story on the avatar ("Photo de profil de <user>"), highlights only, Pixel 3a;
  - a story already seen ("story de <user> vue"), Pixel 3a.
They are read the way `d.xpath()` reads a dump (`parse_ui_dump`).
"""

from pathlib import Path

import pytest

from taktik.core.shared.device.ui_dump import parse_ui_dump

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
        self._tree = parse_ui_dump(xml)

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
    return parse_ui_dump(xml).xpath(selector)


def _screen(name: str) -> str:
    return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")


def _highlights(xml: str) -> list:
    return _matches(xml, '//*[contains(@resource-id, "highlights_reel_tray_recycler_view")]//android.widget.Button')


_PROFILE_WITH_UNSEEN_STORY = _screen("ig410_fr_profile_follow_with_mutuals.xml")
# A profile with NO live story but several "à la une" highlights — the original bug.
_PROFILE_WITH_ONLY_HIGHLIGHTS = _screen("ig410_fr_profile_highlights_only.xml")
# A profile whose story has already been seen ("vue", not "non vue").
_PROFILE_WITH_SEEN_STORY = _screen("ig410_fr_profile_bio_truncated.xml")


def test_every_profile_shows_highlights():
    for xml in (_PROFILE_WITH_UNSEEN_STORY, _PROFILE_WITH_ONLY_HIGHLIGHTS, _PROFILE_WITH_SEEN_STORY):
        assert len(_highlights(xml)) >= 4


def test_unseen_profile_story_ring_is_detected():
    # On the real header both branches answer: the avatar's `reel_ring` and the "non vue" image.
    ring = _matches(_PROFILE_WITH_UNSEEN_STORY, STORY_SELECTORS.profile_unseen_story_avatar)
    assert {node.get("resource-id").rsplit("/", 1)[-1] for node in ring} == {
        "reel_ring", "row_profile_header_imageview"}
    assert ScreenDetectionMixin.has_unseen_profile_story(_Detector(_PROFILE_WITH_UNSEEN_STORY)) is True
    assert ScreenDetectionMixin.count_visible_stories(_Detector(_PROFILE_WITH_UNSEEN_STORY)) == 1


def test_highlights_only_profile_reports_no_story():
    # The regression: highlights must NOT be counted as a watchable story.
    assert _matches(_PROFILE_WITH_ONLY_HIGHLIGHTS, STORY_SELECTORS.profile_unseen_story_avatar) == []
    assert ScreenDetectionMixin.has_unseen_profile_story(_Detector(_PROFILE_WITH_ONLY_HIGHLIGHTS)) is False
    assert ScreenDetectionMixin.count_visible_stories(_Detector(_PROFILE_WITH_ONLY_HIGHLIGHTS)) == 0


@pytest.mark.xfail(strict=True, reason=(
    "Instagram 410 draws the avatar's reel_ring for a SEEN story too (its image says "
    "'story de <user> vue'), and the selector's first branch takes any reel_ring inside "
    "profile_header_avatar_container (ui/selectors/surfaces/story_viewer.py, "
    "profile_unseen_story_avatar): a seen story is reported unseen. Open point, to prove on a "
    "phone before a selector changes."))
def test_seen_story_is_not_reported_as_unseen():
    assert _matches(_PROFILE_WITH_SEEN_STORY, STORY_SELECTORS.profile_unseen_story_avatar) == []
    assert ScreenDetectionMixin.count_visible_stories(_Detector(_PROFILE_WITH_SEEN_STORY)) == 0
