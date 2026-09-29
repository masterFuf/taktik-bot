"""A TikTok feed decision is read on ONE photo (`DetectionActions.read_screen`).

The screens are captures of TikTok in French, anonymized, read by uiautomator2's own
`XPathEntry`; the clock only moves when the code dumps or sleeps. On 43.1.4 (Pixel 3a): a For You
video, an ad, the comment sheet over a video, the suggestion page of the feed, a profile, the
Messages inbox, the new followers page (a screen the reader does not know) and the update prompt
(an unlabelled dialog); on 46.9.3 (Pixel 6a): a LIVE preview, and an English ad whose caption ends
in « more ». The GDPR notice is still written by hand: TikTok shows it once, and no capture holds it.
"""

from types import SimpleNamespace

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

import taktik.core.shared.device.snapshot as snapshot_module
import taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler as popup_module
import taktik.core.social_media.tiktok.actions.core.base_action as base_action_module
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
from taktik.core.social_media.tiktok.actions.atomic.detection.screen_reading import TikTokScreen
from taktik.core.social_media.tiktok.actions.business.workflows._internal.popup_handler import PopupHandler
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.paths import CORE

PKG = "com.zhiliaoapp.musically:id/"
DUMP_S = 0.25
FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


VIDEO = _capture("tt4314_fr_for_you_video.xml")
AD = _capture("tt4314_fr_ad.xml")
COMMENTS = _capture("tt4314_fr_comment_sheet.xml")
SUGGESTION = _capture("tt4314_fr_suggestion_page.xml")
PROFILE = _capture("tt4314_fr_profile.xml")
INBOX = _capture("tt4314_fr_inbox_messages.xml")
UNKNOWN = _capture("tt4314_fr_new_followers.xml")
UPDATE_PROMPT = _capture("tt4314_fr_update_prompt.xml")
LIVE = _capture("tt4693_fr_live_preview.xml")
AD_WITH_CAPTION_EN = _capture("tt4693_en_ad_caption_more.xml")
# Written by hand: see the module docstring.
GDPR = ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0"><node class="android.widget.TextView" '
        'text="Nous avons mis à jour les transferts de données des utilisateurs de l\'EEE vers la Chine" '
        'content-desc="" resource-id="" package="com.zhiliaoapp.musically" clickable="false" '
        'bounds="[40,1000][1040,1100]" /></hierarchy>')


def _field(xml, rid, attribute="text"):
    """What a node of the capture says, read without the production readers."""
    return etree.fromstring(xml.encode("utf-8")).xpath(f'//node[@resource-id="{PKG}{rid}"]')[0].get(attribute)


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def time(self):
        return self.now

    monotonic = perf_counter = time

    def sleep(self, seconds):
        self.now += max(float(seconds), 0.0)


class _Phone:
    """Shows one screen at a time; counts the dumps and the taps."""

    wait_timeout = 1.0

    def __init__(self, clock, xml):
        self.clock, self.xml = clock, xml
        self.dumps, self.gestures = 0, []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        self.dumps += 1
        self.clock.now += DUMP_S
        return self.xml(self) if callable(self.xml) else self.xml

    def click(self, *_a):
        self.gestures.append("click")

    def window_size(self):
        return 1080, 2400


@pytest.fixture
def clock(monkeypatch):
    fake = _Clock()
    for module in (snapshot_module, base_action_module, popup_module):
        monkeypatch.setattr(module, "time", fake)
    return fake


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _reader(clock, xml):
    phone = _Phone(clock, xml)
    return DetectionActions(phone), phone


@pytest.mark.parametrize("xml, kind", [
    (VIDEO, "video"), (AD, "ad"), (COMMENTS, "comments"), (SUGGESTION, "suggestion"),
    (PROFILE, "profile"), (INBOX, "inbox"), (GDPR, "popup"),
], ids=["video", "ad", "comments", "suggestion", "profile", "inbox", "gdpr"])
def test_each_screen_is_recognised_on_one_photo(clock, xml, kind):
    detection, phone = _reader(clock, xml)
    screen = detection.read_screen()
    assert (screen.kind, phone.dumps) == (kind, 1)


def test_a_live_preview_is_recognised_where_its_ids_are_known(clock):
    apply_version_overrides("tiktok", "46.9.3")
    try:
        detection, phone = _reader(clock, LIVE)
        assert (detection.read_screen().kind, phone.dumps) == ("live", 1)
    finally:
        apply_version_overrides("tiktok", "43.1.4")


def test_the_signals_are_the_production_readers_answers(clock):
    detection, _ = _reader(clock, VIDEO)
    screen = detection.read_screen()
    assert screen.for_you and screen.video and not (screen.ad or screen.live or screen.inbox)
    assert screen.popups == frozenset() and screen.photo_age_ms is not None
    # On the inbox the author reader answers too ("Messages"): it reads, it does not recognise.
    inbox, _ = _reader(clock, INBOX)
    screen = inbox.read_screen()
    assert inbox.get_video_author(screen) == "Messages"
    assert (screen.kind, screen.video, screen.popups) == ("inbox", False, frozenset({"inbox_page"}))


def test_an_unknown_screen_is_read_again_until_the_timeout(clock):
    detection, phone = _reader(clock, UNKNOWN)
    started = clock.now
    screen = detection.read_screen()
    assert screen.kind == "unknown" and screen.photo is not None
    # Photos at 0, 0.55, 1.1, 1.65 and 2.2 s, one every 0.3 s after each dump: the fifth ends the wait.
    assert phone.dumps == 5 and clock.now - started == pytest.approx(5 * DUMP_S + 4 * 0.3)


def test_until_names_what_the_wait_is_for(clock):
    screens = [INBOX, VIDEO]
    detection, phone = _reader(clock, lambda _phone: screens.pop(0) if len(screens) > 1 else screens[0])
    screen = detection.read_screen(until=lambda s: s.for_you)
    assert (screen.kind, phone.dumps) == ("video", 2)


def test_a_screen_that_cannot_be_read_answers_nothing(clock):
    detection, phone = _reader(clock, "")
    screen = detection.read_screen()
    assert screen == TikTokScreen() and screen.kind == "unknown" and phone.dumps == 5
    assert detection.get_video_info(screen=screen)["author"] is None


def test_every_reader_answers_on_the_photo_without_a_dump(clock):
    detection, phone = _reader(clock, VIDEO)
    screen = detection.read_screen()
    started = clock.now
    info = detection.get_video_info(light_if_ad=True, screen=screen)
    answers = (detection.has_comments_section_open(screen), detection.has_suggestion_page(screen),
               detection.is_on_for_you_page(screen), detection.is_on_inbox_page(screen))
    sound = _field(VIDEO, "nhe", "content-desc").split(" : ", 1)[1]
    assert (info["author"], info["sound"], info["like_count"]) == (
        _field(VIDEO, "title"), sound, _field(VIDEO, "f4z"))
    assert info["description"] == _field(VIDEO, "desc") and info["hashtags"] == []
    assert answers == (False, False, True, False)
    assert (phone.dumps, clock.now) == (1, started)


def test_video_info_without_a_photo_takes_one(clock):
    detection, phone = _reader(clock, VIDEO)
    alone = detection.get_video_info(light_if_ad=True)
    assert phone.dumps == 1
    assert alone == detection.get_video_info(light_if_ad=True, screen=detection.read_screen())


def test_an_ad_s_caption_is_never_tapped_open(clock):
    set_active_locale("en")
    apply_version_overrides("tiktok", "46.9.3")
    try:
        caption = _field(AD_WITH_CAPTION_EN, "desc")
        assert caption.endswith("…more")
        detection, phone = _reader(clock, AD_WITH_CAPTION_EN)
        screen = detection.read_screen()
        skipped = detection.get_video_info(light_if_ad=True, screen=screen)
        kept = detection.get_video_info(light_if_ad=False, screen=screen)
        assert (skipped["is_ad"], skipped["description"]) == (True, None)
        assert skipped["author"] == _field(AD_WITH_CAPTION_EN, "title")
        assert kept["description"] and caption.startswith(kept["description"])
        assert "more" not in kept["description"]
        assert phone.gestures == [] and phone.dumps == 1
    finally:
        apply_version_overrides("tiktok", "43.1.4")


def test_the_popup_handler_reads_the_turn_s_photo(clock, monkeypatch):
    noted = []
    import taktik.core.shared.diagnostics.screen_ring as ring

    monkeypatch.setattr(ring, "noter", lambda xml, platform: noted.append(platform))
    detection, phone = _reader(clock, GDPR)
    closed = []
    handler = PopupHandler(SimpleNamespace(close_gdpr_popup=lambda: closed.append("gdpr") or True), detection)
    screen = detection.read_screen()
    assert handler.close_all(screen) is True
    assert (closed, noted, phone.dumps) == (["gdpr"], ["tiktok"], 1)
    assert handler.detect(TikTokScreen()) == {"_fallback"}


def test_an_unlabelled_dialog_is_seen_on_the_photo_as_by_the_dump_scan(clock):
    detection, _ = _reader(clock, UPDATE_PROMPT)
    screen = detection.read_screen()
    handler = PopupHandler(None, detection)
    assert screen.popups == frozenset({"unlabelled_overlay"}) and screen.kind == "popup"
    assert screen.overlay_region == (152, 562, 928, 1658)
    assert handler.detect(screen) == handler._fast_detect() == {"unlabelled_overlay"}
