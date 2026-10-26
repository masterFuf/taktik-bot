"""Instagram 447: the first friend's story of the home tray, never the « add to story » badge.

In 447 the badge on our own bubble (`reel_empty_badge`, described « Ajouter à la story ») became a
clickable Button inside the tray; in 410 it is an ImageView. The tray selector takes every Button of
the tray whose description says « story », so in 447 it took the badge too, second after our own
bubble: `click_feed_story(0)`, which skips our bubble, tapped the badge and opened the story CAMERA
(gallery « Ajouter à la story ») instead of a friend's story. Seen on a Pixel 6a in French on every
tray opening of the Lab bench (October 2026): ten openings, ten cameras, the story tests played on the
gallery. The count was off by one too (« 4 visibles » for three friends).

The screens are real dumps, anonymized: the 447 home feed of that phone (badge a Button) and the 410
home feed of a Pixel 3a (badge an ImageView). The 447 entry is a version override
(compat/data/overrides/instagram.yaml), applied here as the patcher does.
"""

from types import SimpleNamespace

import pytest
import yaml

from taktik.core.social_media.instagram.actions.atomic.detection.screen_detection import (
    ScreenDetectionMixin,
)
from taktik.core.social_media.instagram.actions.atomic.interaction.story_interaction import (
    StoryInteractionMixin,
)
from taktik.core.social_media.instagram.ui.selectors.surfaces.story_viewer import STORY_SELECTORS
from unit.paths import CORE
from unit.social_media.instagram.actions.atomic.interaction.sheet_phone import SheetPhone, capture

OVERRIDES = CORE / "taktik/core/compat/data/overrides/instagram.yaml"
FIELDS = ("feed_story_buttons", "feed_unseen_story_buttons")


@pytest.fixture
def ig_447(monkeypatch):
    entries = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8"))["versions"]["447.0.0.0"]
    for field in FIELDS:
        # A str field: the patcher gives it the first entry of the list.
        monkeypatch.setattr(STORY_SELECTORS, field, entries[f"story.{field}"][0])


def _bubble(xml, description_start):
    """Bounds of the tray Button whose description starts with `description_start`, as
    uiautomator2 reads them on the capture."""
    found = SheetPhone(xml, xml).xpath(
        f'//android.widget.Button[starts-with(@content-desc, "{description_start}")]').all()
    assert found, f"no tray button {description_start!r} on this capture"
    return found[0].bounds


def _host(cls, phone):
    """The production mixin on the phone, without the facade its __init__ would build."""
    host = cls.__new__(cls)
    host.device = SimpleNamespace(xpath=phone.xpath, click_coordinates=phone.click)
    host.logger = SimpleNamespace(debug=lambda *_a, **_k: None, warning=lambda *_a, **_k: None,
                                  error=lambda *_a, **_k: None)
    host._human_like_delay = lambda *_a, **_k: None
    return host


def _tapped(name):
    xml = capture(name)
    phone = SheetPhone(xml, xml)
    assert _host(StoryInteractionMixin, phone).click_feed_story(0) is True
    [(kind, x, y)] = phone.gestures
    assert kind == "click"
    return xml, (x, y)


def _inside(point, box):
    left, top, right, bottom = box
    return left <= point[0] <= right and top <= point[1] <= bottom


def test_447_opens_the_first_friend_not_the_add_to_story_badge(ig_447):
    xml, point = _tapped("ig447_fr_home_feed.xml")

    assert not _inside(point, _bubble(xml, "Ajouter à la story")), point
    assert _inside(point, _bubble(xml, "Story de name_3, 1 ")), point


def test_447_counts_the_friends_of_the_tray_without_the_badge(ig_447):
    phone = SheetPhone(capture("ig447_fr_home_feed.xml"), capture("ig447_fr_home_feed.xml"))

    assert _host(ScreenDetectionMixin, phone).count_visible_feed_stories() == 3


def test_410_baseline_still_opens_the_first_friend():
    xml, point = _tapped("ig410_fr_home_feed_before_dm_tab.xml")

    assert _inside(point, _bubble(xml, "Story de user_2, 1 ")), point
