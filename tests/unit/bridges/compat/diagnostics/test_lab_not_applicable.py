"""A Lab action says "not applicable" itself, and only on the screen it expects, read.

The Lab auto-test counts a test "not applicable" only when the action declares it
(`details.not_applicable`, recommendation 4 of the bancrecette lot, validated by Kevin on 2026-09-28):
no follow request pending, no popup to close, no story ring on the profile, an ad on screen instead
of a video. The plan never guesses it. Declared on the screen the action expects, read and the app's;
anywhere else the action still fails, so a broken selector is never taken for absent content.

The screens are real dumps, anonymized: Instagram 410 (English notifications, home feed; French
profile with highlights only) and TikTok 43.1.4 in French (For You video, an ad, the inbox).
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY as INSTAGRAM_ACTIONS
from bridges.compat.diagnostics.actions.instagram import register_actions as register_instagram
from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY as TIKTOK_ACTIONS
from bridges.compat.diagnostics.actions.tiktok import register_actions as register_tiktok
from bridges.compat.diagnostics.runtime.action_test.bundles.instagram import (
    build_instagram_action_bundle,
    create_instagram_device_facade,
)
from bridges.compat.diagnostics.runtime.action_test.bundles.tiktok import (
    build_tiktok_action_bundle,
    create_tiktok_device_facade,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale as instagram_locale
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale as tiktok_locale

SOCIAL = Path(__file__).resolve().parents[3] / "social_media"


def _dump(platform, name):
    return (SOCIAL / platform / "fixtures" / name).read_text(encoding="utf-8")


IG_NOTIFICATIONS = _dump("instagram", "ig410_en_notifications.xml")
IG_FEED = _dump("instagram", "ig410_en_home_feed_carousel_post.xml")
IG_PROFILE_HIGHLIGHTS_ONLY = _dump("instagram", "ig410_fr_profile_highlights_only.xml")
TT_VIDEO = _dump("tiktok", "tt4314_fr_for_you_video.xml")
TT_AD = _dump("tiktok", "tt4314_fr_ad.xml")
TT_INBOX = _dump("tiktok", "tt4314_fr_inbox.xml")


class _Phone:
    """uiautomator2 as the Lab touches it: `xpath()`, one dump, and the taps it would inject."""

    wait_timeout = 0.2

    def __init__(self, xml, package):
        self.xml, self.package = xml, package
        self.xpath = XPathEntry(self)
        self.taps = []

    def dump_hierarchy(self, *_a, **_k):
        return self.xml

    def app_current(self):
        return {"package": self.package, "activity": "demo.Activity"}

    def window_size(self):
        return (1080, 2220)

    def click(self, x, y):
        self.taps.append((x, y))


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    register_tiktok()
    register_instagram()
    yield
    tiktok_locale(None)
    instagram_locale(None)


def _instagram(xml, lang):
    instagram_locale(lang)
    phone = _Phone(xml, "com.instagram.android")
    return build_instagram_action_bundle(create_instagram_device_facade(phone)), phone


def _tiktok(xml):
    tiktok_locale("fr")
    phone = _Phone(xml, "com.zhiliaoapp.musically")
    return build_tiktok_action_bundle(create_tiktok_device_facade(phone)), phone


def _declared(result):
    return (result.get("details") or {}).get("not_applicable")


def test_no_follow_request_pending_is_declared_on_the_notifications_screen():
    bundle, phone = _instagram(IG_NOTIFICATIONS, "en")
    result = INSTAGRAM_ACTIONS["notifications.open_follow_requests"](bundle, {})
    assert result["success"] is False
    assert _declared(result) == "no follow requests row on the notifications screen"
    assert phone.taps == []


def test_off_the_notifications_screen_it_stays_a_failure():
    bundle, _phone = _instagram(IG_FEED, "en")
    result = INSTAGRAM_ACTIONS["notifications.open_follow_requests"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)
    assert "not on the notifications screen" in result["message"]


def test_a_profile_without_a_story_up_declares_no_ring():
    bundle, _phone = _instagram(IG_PROFILE_HIGHLIGHTS_ONLY, "fr")
    result = INSTAGRAM_ACTIONS["story.open_from_profile"](bundle, {})
    assert _declared(result) == "no story ring on this profile"


def test_off_a_profile_no_ring_is_not_declared():
    bundle, _phone = _instagram(IG_FEED, "en")
    result = INSTAGRAM_ACTIONS["story.open_from_profile"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)


@pytest.mark.parametrize("name, lang, declared", [
    ("ig410_en_profile_follow_back.xml", "en", "no truncated bio on this profile"),
    # Truncated: the expander is OCR'd on a screenshot, which this phone cannot take: a failure.
    ("ig410_fr_profile_bio_truncated.xml", "fr", None),
])
def test_a_bio_not_truncated_is_declared_and_a_truncated_one_is_not(name, lang, declared):
    bundle, _phone = _instagram(_dump("instagram", name), lang)
    result = INSTAGRAM_ACTIONS["profile.expand_bio_more"](bundle, {})
    assert (result["success"], _declared(result)) == (False, declared)


def test_nothing_to_close_on_a_video_is_declared():
    bundle, phone = _tiktok(TT_VIDEO)
    result = TIKTOK_ACTIONS["tt.popups.close_popup"](bundle, {})
    assert _declared(result) == "no popup or banner on screen"
    assert phone.taps == []


def test_nothing_to_close_on_an_unreadable_screen_is_a_failure():
    bundle, _phone = _tiktok("")
    result = TIKTOK_ACTIONS["tt.popups.close_popup"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)
    assert "screen unreadable" in result["message"]


def test_an_ad_has_no_sound_page_to_open_and_nothing_is_tapped():
    bundle, phone = _tiktok(TT_AD)
    result = TIKTOK_ACTIONS["tt.sound.open_page"](bundle, {})
    assert _declared(result) == "the For You item on screen is an ad: its promoted sound has no page"
    assert phone.taps == []


def test_a_video_whose_sound_page_does_not_open_is_a_failure():
    bundle, _phone = _tiktok(TT_VIDEO)
    result = TIKTOK_ACTIONS["tt.sound.open_page"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)


def test_a_profile_without_a_message_entry_declares_none_and_a_feed_is_a_failure():
    """TikTok 47.0.3: a profile that follows us, not followed back, has no « Message » (fixture of
    `test_tiktok_dm_outreach_no_message_entry.py`); the For You feed is not a profile at all."""
    from taktik.core.compat.selectors.setup import apply_version_overrides

    apply_version_overrides("tiktok", "47.0.3")
    try:
        bundle, phone = _tiktok(_dump("tiktok", "tt47_fr_profile_follows_us_no_message_entry.xml"))
        result = TIKTOK_ACTIONS["tt.profile.click_message"](bundle, {})
        assert _declared(result) == "the open profile offers no message entry"
        bundle, phone = _tiktok(_dump("tiktok", "tt4703_fr_home.xml"))
        result = TIKTOK_ACTIONS["tt.profile.click_message"](bundle, {})
        assert (result["success"], _declared(result)) == (False, None)
    finally:
        apply_version_overrides("tiktok", "43.1.4")


def test_an_inbox_without_message_requests_declares_none():
    bundle, _phone = _tiktok(TT_INBOX)
    result = TIKTOK_ACTIONS["tt.inbox.open_message_requests"](bundle, {})
    assert _declared(result) == "no message requests row on the inbox"


def test_an_inbox_offering_no_wave_declares_none_and_the_feed_does_not():
    bundle, _phone = _tiktok(TT_INBOX)
    assert _declared(TIKTOK_ACTIONS["tt.inbox.hello_candidates"](bundle, {})) == "no wave offered on the inbox"
    bundle, _phone = _tiktok(TT_VIDEO)
    result = TIKTOK_ACTIONS["tt.inbox.hello_candidates"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)
