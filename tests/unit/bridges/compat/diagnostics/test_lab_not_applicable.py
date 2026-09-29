"""A Lab action says "not applicable" itself, and only on the screen it expects, read.

The Lab auto-test counts a test "not applicable" only when the action declares it
(`details.not_applicable`, recommendation 4 of the bancrecette lot, validated by Kevin on 2026-09-28):
no follow request pending, no popup to close, no story ring on the profile, an ad on screen instead
of a video. The plan never guesses it. Declared on the screen the action expects, read and the app's;
anywhere else the action still fails, so a broken selector is never taken for absent content.

The screens are real dumps, anonymized: Instagram 410 (English notifications, home feed; French
profile with highlights only; our English followers list with and without its categories, and read
further down), Instagram 447 (our French followers list with and without its categories), TikTok
43.1.4 in French (For You video, a video without a
description, the « Voir les Stories » card the feed serves in place of a video, an ad, a LIVE
preview, the inbox) and TikTok 47.0.3 in French (For You video, the same card).
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
TT_VIDEO_NO_DESCRIPTION = _dump("tiktok", "tt4314_fr_for_you_video_no_description.xml")
TT_STORIES_CARD = _dump("tiktok", "tt4314_fr_for_you_stories_card.xml")
TT_AD = _dump("tiktok", "tt4314_fr_ad.xml")
TT_LIVE = _dump("tiktok", "tt4314_fr_for_you_live_preview.xml")
TT_INBOX = _dump("tiktok", "tt4314_fr_inbox.xml")
TT4703_VIDEO = _dump("tiktok", "tt4703_fr_for_you_video.xml")
TT4703_STORIES_CARD = _dump("tiktok", "tt4703_fr_for_you_stories_card.xml")


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


@pytest.fixture
def on_47_0_3():
    """The catalogues patched for TikTok 47.0.3, as at the connection of a phone that runs it."""
    from taktik.core.compat.selectors.setup import apply_version_overrides

    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


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


def test_a_follow_list_without_load_more_declares_none_and_the_feed_does_not():
    bundle, phone = _instagram(_dump("instagram", "ig410_en_followers_list.xml"), "en")
    result = INSTAGRAM_ACTIONS["scraping.click_load_more"](bundle, {})
    assert _declared(result) == "no load more affordance on this list"
    assert phone.taps == []
    bundle, _phone = _instagram(IG_FEED, "en")
    assert _declared(INSTAGRAM_ACTIONS["scraping.click_load_more"](bundle, {})) is None


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


@pytest.mark.parametrize("action_id, declared", [
    ("tt.sound.read", "the For You item on screen is a LIVE: no sound row"),
    ("tt.video.click_comment", "the For You item on screen is a LIVE: no comment button"),
])
def test_a_live_preview_has_no_sound_row_nor_comment_button_and_nothing_is_tapped(action_id, declared):
    """43.1.4: a LIVE preview of the For You feed, where the second auto-test pass of the Pixel 3a
    failed both tests (no sound row, no comment button found)."""
    bundle, phone = _tiktok(TT_LIVE)
    result = TIKTOK_ACTIONS[action_id](bundle, {})
    assert (result["success"], _declared(result)) == (False, declared)
    assert phone.taps == []


def test_on_a_video_the_comment_button_is_not_declared_absent():
    """The production click answers (a bool): no declaration on a video."""
    bundle, _phone = _tiktok(TT_VIDEO)
    result = TIKTOK_ACTIONS["tt.video.click_comment"](bundle, {})
    assert not isinstance(result, dict)


def test_a_video_whose_sound_page_does_not_open_is_a_failure():
    bundle, _phone = _tiktok(TT_VIDEO)
    result = TIKTOK_ACTIONS["tt.sound.open_page"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)


def test_a_profile_without_a_message_entry_declares_none_and_a_feed_is_a_failure(on_47_0_3):
    """TikTok 47.0.3: a profile that follows us, not followed back, has no « Message » (fixture of
    `test_tiktok_dm_outreach_no_message_entry.py`); the For You feed is not a profile at all."""
    bundle, phone = _tiktok(_dump("tiktok", "tt47_fr_profile_follows_us_no_message_entry.xml"))
    result = TIKTOK_ACTIONS["tt.profile.click_message"](bundle, {})
    assert _declared(result) == "the open profile offers no message entry"
    bundle, phone = _tiktok(_dump("tiktok", "tt4703_fr_home.xml"))
    result = TIKTOK_ACTIONS["tt.profile.click_message"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)


def test_a_video_without_a_description_declares_none_and_nothing_is_tapped():
    """43.1.4, For You surface of the Pixel 3a pass of 2026-09-29 (step 21, « 0 chars »): a video
    that shows its author, in LIVE, its sound and its buttons, and no description. The production
    reader, handed the photo a For You turn is read on, finds none: an item of the feed, not a
    selector that stopped reading."""
    bundle, phone = _tiktok(TT_VIDEO_NO_DESCRIPTION)
    result = TIKTOK_ACTIONS["tt.detection.get_video_description"](bundle, {})
    assert (result["success"], _declared(result)) == (False, "no description on the video")
    assert phone.taps == []


@pytest.mark.parametrize("xml", [TT_VIDEO, TT_AD], ids=["video", "ad"])
def test_a_description_on_screen_is_read_and_nothing_is_declared(xml):
    """A French caption is read as the screen shows it, never tapped open, an ad's no more than a
    video's (a tap on an ad's caption would be a click on the ad)."""
    bundle, phone = _tiktok(xml)
    result = TIKTOK_ACTIONS["tt.detection.get_video_description"](bundle, {})
    assert (result["success"], _declared(result)) == (True, None)
    assert result["details"]["description"]
    assert phone.taps == []


def test_a_live_preview_has_no_description_to_read():
    bundle, phone = _tiktok(TT_LIVE)
    result = TIKTOK_ACTIONS["tt.detection.get_video_description"](bundle, {})
    assert (result["success"], _declared(result)) == (
        False, "the For You item on screen is a LIVE: no description")
    assert phone.taps == []


def test_a_stories_card_has_no_description_to_read():
    """43.1.4, For You surface of the Pixel 3a pass of 2026-09-29, after the first fix: the feed served
    a followed account's « Voir les Stories » card, read as « no video on screen (unknown) »."""
    bundle, phone = _tiktok(TT_STORIES_CARD)
    result = TIKTOK_ACTIONS["tt.detection.get_video_description"](bundle, {})
    assert (result["success"], _declared(result)) == (
        False, "the For You item on screen is a Stories card: no description")
    assert phone.taps == []


@pytest.mark.parametrize("xml", [TT_INBOX, ""], ids=["inbox", "unreadable"])
def test_off_a_video_no_description_is_declared_absent(xml):
    """Nothing was read where no video is: a failure, never « no description »."""
    bundle, _phone = _tiktok(xml)
    result = TIKTOK_ACTIONS["tt.detection.get_video_description"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)


def _no_video_to_link_on(card_xml):
    """The production finds no share button on the card and answers nothing, which is right; the
    Lab says why, and taps nothing."""
    bundle, phone = _tiktok(card_xml)
    result = TIKTOK_ACTIONS["tt.video.collect_post"](bundle, {})
    assert (result["success"], _declared(result)) == (
        False, "the For You item on screen is a Stories card: no video to link")
    assert phone.taps == []


def test_a_stories_card_served_in_place_of_a_video_has_no_link():
    """43.1.4, the card of the Pixel 3a pass of 2026-09-29 (ids of the reference)."""
    _no_video_to_link_on(TT_STORIES_CARD)


def test_a_stories_card_served_in_place_of_a_video_has_no_link_on_47_0_3(on_47_0_3):
    """47.0.3, the card of the Pixel 6a pass of 2026-09-29 (ids of the override)."""
    _no_video_to_link_on(TT4703_STORIES_CARD)


def test_a_video_whose_link_is_not_had_is_not_declared(on_47_0_3):
    """A video has a link to copy: when the copy fails, the action fails."""
    bundle, _phone = _tiktok(TT4703_VIDEO)
    result = TIKTOK_ACTIONS["tt.video.collect_post"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)


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


def test_a_thread_longer_than_the_screen_declares_no_card_and_the_inbox_does_not():
    """The card that prints the handle scrolls away once the conversation outgrows the screen
    (43.1.4, a thread between two test accounts); the inbox is not a thread at all."""
    bundle, phone = _tiktok(_dump("tiktok", "tt4314_fr_dm_thread_card_scrolled_away.xml"))
    result = TIKTOK_ACTIONS["tt.inbox.read_thread_handle"](bundle, {})
    assert (result["success"], _declared(result)) == (False, "no profile card on the open thread")
    assert phone.taps == []
    bundle, _phone = _tiktok(TT_INBOX)
    result = TIKTOK_ACTIONS["tt.inbox.read_thread_handle"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)
    assert "no thread open" in result["message"]


FANS_NOT_SERVED = "our followers list opens on its accounts, Instagram serves it no category now"


def _unfollow_on(xml, lang, monkeypatch):
    """The Lab's unfollow engine on our followers list: account bound, the follow graph a spy."""
    from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins import sync_following

    written = []
    monkeypatch.setattr(sync_following, "InstagramFollowGraphService",
                        type("GraphSpy", (), {"upsert_follower": staticmethod(lambda **kw: written.append(kw))}))
    bundle, phone = _instagram(xml, lang)
    bundle.unfollow.active_account_id = 1
    return bundle, phone, written


@pytest.mark.parametrize("name, lang, list_top", [
    ("ig410_en_own_followers_list_no_category.xml", "en", 363),
    ("ig447_fr_own_followers_list_no_category.xml", "fr", 405),
])
def test_a_followers_list_opening_on_its_accounts_declares_the_fans_category_not_served(name, lang, list_top,
                                                                                         monkeypatch):
    """Instagram serves the categories of our followers tab on some days only. 410 in English: the
    Pixel 3a pass of 2026-09-29, failed on « 0 fans »; 447 in French: the Pixel 6a, a sort row under
    the search box. Nothing in the list is tapped, nothing is recorded."""
    bundle, phone, written = _unfollow_on(_dump("instagram", name), lang, monkeypatch)
    result = INSTAGRAM_ACTIONS["unfollow.read_fans_category"](bundle, {})
    assert (result["success"], _declared(result)) == (False, FANS_NOT_SERVED)
    assert written == []
    assert [y for _x, y in phone.taps if y >= list_top] == []


@pytest.mark.parametrize("name, lang, category_row", [
    ("ig410_en_own_followers_list_categories.xml", "en", (680, 878)),
    ("ig447_fr_own_followers_list.xml", "fr", (708, 897)),
])
def test_a_served_fans_category_is_opened_and_never_declared_absent(name, lang, category_row, monkeypatch):
    """410 in English (Pixel 3a) and 447 in French (Pixel 6a), the category served. The screen does
    not change after the tap here: what the read then finds is not this test's subject."""
    bundle, phone, _written = _unfollow_on(_dump("instagram", name), lang, monkeypatch)
    result = INSTAGRAM_ACTIONS["unfollow.read_fans_category"](bundle, {})
    assert _declared(result) is None
    assert any(category_row[0] <= y <= category_row[1] for _x, y in phone.taps)


def _selected_tab(xml, shown, hidden):
    """The dump with the tab titled `shown` selected in place of the one titled `hidden`."""
    for title, before, after in ((hidden, 'selected="true"', 'selected="false"'),
                                 (shown, 'selected="false"', 'selected="true"')):
        start = xml.index(f'text="{title}"')
        end = xml.index("/>", start)
        assert before in xml[start:end]
        xml = xml[:start] + xml[start:end].replace(before, after) + xml[end:]
    return xml


SERVED_410 = _dump("instagram", "ig410_en_own_followers_list_categories.xml")
NO_CATEGORY_447 = _dump("instagram", "ig447_fr_own_followers_list_no_category.xml")


@pytest.mark.parametrize("xml, lang", [
    # Derived: the served list, its fans category under a label no locale knows.
    (SERVED_410.replace("People you don't follow back", "Followers you haven't followed back"), "en"),
    # Our followers list read further down (410 in English, Pixel 3a): accounts first, and the
    # categories may be above them.
    (_dump("instagram", "ig410_en_own_followers_newest_first_2.xml"), "en"),
    # Derived: the 447 list without category, the following tab shown, as when the tap on the
    # followers tab did not take.
    (_selected_tab(NO_CATEGORY_447, "1\u202f280 suivi(e)s", "691 followers"), "fr"),
], ids=["renamed category", "list read further down", "another tab"])
def test_what_does_not_prove_the_category_not_served_stays_a_failure(xml, lang, monkeypatch):
    bundle, _phone, written = _unfollow_on(xml, lang, monkeypatch)
    result = INSTAGRAM_ACTIONS["unfollow.read_fans_category"](bundle, {})
    assert (result["success"], _declared(result)) == (False, None)
    assert result["message"] == "0 fans"
    assert written == []
