"""The banner « Continuer la modification de cette publication ? » is a popup, closed by « Enreg. brouillon ».

When a publication is left half-way, TikTok 47.0.3 lays a banner over the top of every screen: the
title `uj8`, the buttons `v5z` « Enreg. brouillon » and `uj4` « Modifier ». Both end in a draft
(the editor's back arrow saves one by itself); the banner offers no abandon. While it is there, a
creator's profile reads without its header: `read_screen` answered `unknown`, the turn never saw a
profile, and the return to the feed never ran. On the feed it answered `video` with no popup.

The screens are real captures (Pixel 6a, TikTok 47.0.3 in French, 2026-11-15), anonymized: the
banner over a creator's profile, the banner over the For You feed, and the editor that « Modifier »
opens. Evaluated by uiautomator2's own `d.xpath()` engine, as on the phone.
"""

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.tiktok.actions.base.base_action as base_action_module
import taktik.core.social_media.tiktok.workflows.common.popup_handler as popup_module
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
from taktik.core.social_media.tiktok.actions.atomic.interaction.click_actions import ClickActions
from taktik.core.social_media.tiktok.actions.base.device_facade import DeviceFacade
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.workflows.common.popup_handler import PopupHandler
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
OVER_PROFILE = (FIXTURES / "tt4703_fr_draft_banner_profile.xml").read_text(encoding="utf-8")
OVER_FOR_YOU = (FIXTURES / "tt4703_fr_draft_banner_for_you.xml").read_text(encoding="utf-8")
EDITOR = (FIXTURES / "tt4703_fr_draft_editor.xml").read_text(encoding="utf-8")

#: The buttons of the banner in both captures (left, top, right, bottom).
SAVE_DRAFT = (211, 316, 608, 400)
EDIT = (629, 316, 1027, 400)


def _inside(point, box):
    (x, y), (left, top, right, bottom) = point, box
    return left <= x <= right and top <= y <= bottom


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(float(seconds), 0.0)


class _Phone:
    """uiautomator2 as the production touches it: `xpath()`, a still screen, the taps it injects."""

    wait_timeout = 0.2

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)
        self.taps = []
        self.keys = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": "com.zhiliaoapp.musically", "activity": "demo.Activity"}

    def window_size(self):
        return (1080, 2400)

    def click(self, x, y):
        self.taps.append((x, y))

    def press(self, key):
        self.keys.append(key)


@pytest.fixture(autouse=True)
def still_clock(monkeypatch):
    clock = _Clock()
    for module in (snapshot_module, base_action_module, popup_module):
        monkeypatch.setattr(module, "time", clock)
    import time

    monkeypatch.setattr(time, "sleep", clock.sleep)
    return clock


@pytest.fixture
def phone_4703():
    """A phone on TikTok 47.0.3, its catalogues as the connection leaves them."""
    apply_version_overrides("tiktok", "47.0.3")
    yield
    set_active_locale(None)
    apply_version_overrides("tiktok", "43.1.4")


def _read(xml):
    phone = _Phone(xml)
    facade = DeviceFacade(phone)
    detection = DetectionActions(facade)
    return detection, ClickActions(facade), phone


@pytest.mark.parametrize("xml", [OVER_PROFILE, OVER_FOR_YOU], ids=["over_profile", "over_for_you"])
def test_the_banner_is_a_popup_of_the_turn_s_photo(phone_4703, xml):
    """Over the profile the photo answered `unknown`, over the feed `video`: the turn went on as if
    nothing covered the screen."""
    set_active_locale("fr")
    detection, _, _ = _read(xml)
    screen = detection.read_screen()
    assert "draft_resume_banner" in screen.popups
    assert screen.kind == "popup"


@pytest.mark.parametrize("language", ["fr", "en"])
@pytest.mark.parametrize("xml", [OVER_PROFILE, OVER_FOR_YOU], ids=["over_profile", "over_for_you"])
def test_the_popup_chain_taps_save_draft_and_never_edit(phone_4703, xml, language):
    """« Enreg. brouillon »: nothing is published, nothing is lost. On 47.0.3 the ids of the override
    find it in any language: a phone in English is read with the English locale, which has never
    seen this banner."""
    set_active_locale(language)
    detection, click, phone = _read(xml)
    handler = PopupHandler(click, detection)
    assert handler.close_all(detection.read_screen()) is True
    assert len(phone.taps) == 1
    assert _inside(phone.taps[0], SAVE_DRAFT) and not _inside(phone.taps[0], EDIT)
    assert phone.keys == []


def test_the_dump_scan_of_the_handler_sees_it_too(phone_4703):
    """The target profiles and the followers runs ask the handler without a photo: same table."""
    set_active_locale("fr")
    detection, click, _ = _read(OVER_PROFILE)
    assert "draft_resume_banner" in PopupHandler(click, detection).detect()


def test_on_the_baseline_the_french_label_finds_it_alone():
    """Another version: no id known, the locale's title and button answer."""
    set_active_locale("fr")
    try:
        detection, click, phone = _read(OVER_FOR_YOU)
        assert "draft_resume_banner" in detection.read_screen().popups
        assert PopupHandler(click, detection).close_all() is True
        assert len(phone.taps) == 1 and _inside(phone.taps[0], SAVE_DRAFT)
    finally:
        set_active_locale(None)


def test_the_editor_that_edit_opens_is_not_the_banner(phone_4703):
    """« Modifier » opens the editor, whose back arrow saves a draft: nothing there to tap."""
    set_active_locale("fr")
    detection, click, phone = _read(EDITOR)
    assert "draft_resume_banner" not in detection.read_screen().popups
    assert "draft_resume_banner" not in PopupHandler(click, detection).detect()
