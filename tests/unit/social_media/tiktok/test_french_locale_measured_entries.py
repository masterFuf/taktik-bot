"""French entries written from captures of TikTok 43.1.4 and 46.6.3: each answers on its screen
and stays silent on the screen that carries the same word elsewhere.

The screens are real captures, anonymized, in French, evaluated by uiautomator2's own `d.xpath()`
engine: TikTok 43.1.4 (Pixel 3a: For You feed, search results, comment sheet, following list,
inbox with its « Inviter » banner, a profile, our own profile, the « Personnes que tu pourrais
connaître » page, the new followers page; Pixel 6a in June: a feed video with its « Pas
intéressé(e) » survey, a feed holding a « Personnes que tu pourrais connaître » card), 46.9.3 and
47.0.3 (Pixel 6a: users tab, a video without a share count, a DM conversation), and the Pixel
launcher, whose « Messages » app carries the inbox's word.
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.tiktok.ui.selectors as catalogue
from taktik.core.social_media.tiktok.ui.selectors.locales import L, set_active_locale

FIXTURES = Path(__file__).parent / "fixtures"
LAUNCHER_FIXTURES = Path(__file__).parents[2] / "shared" / "device" / "fixtures"


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _capture(name, folder=FIXTURES):
    return (folder / name).read_text(encoding="utf-8")


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


def _found(key, xml):
    device = _Device(xml)
    return [el for sel in L(key) for el in device.xpath(sel).all()]


FEED = _capture("tt4314_fr_for_you_video.xml")
SEARCH_RESULTS = _capture("tt4314_fr_search_top_results.xml")
COMMENT_SHEET = _capture("tt4314_fr_comment_sheet.xml")
FOLLOWING_LIST = _capture("tt4314_fr_following_list.xml")
INBOX = _capture("tt4314_fr_inbox.xml")
INBOX_WITHOUT_BANNER = _capture("tt4314_fr_inbox_messages.xml")
LAUNCHER = _capture("android12_fr_launcher_home.xml", LAUNCHER_FIXTURES)
PROFILE = _capture("tt4314_fr_profile.xml")
OWN_PROFILE = _capture("tt4314_fr_own_profile.xml")
USERS_TAB = _capture("tt4693_fr_search_users.xml")
CONVERSATION = _capture("tt4693_fr_dm_conversation.xml")
SUGGESTION_PAGE = _capture("tt4314_fr_suggestion_page.xml")
NEW_FOLLOWERS = _capture("tt4314_fr_new_followers.xml")
FEED_SURVEY = _capture("tt4314_fr_feed_survey.xml")
FEED_PEOPLE_CARD = _capture("tt4314_fr_feed_people_card.xml")


def test_the_shop_tab_of_the_feed_is_not_the_one_of_search_results():
    assert len(_found("navigation.shop_tab", FEED)) == 1
    assert _found("navigation.shop_tab", SEARCH_RESULTS) == []


def test_the_shop_tab_of_search_results_is_not_the_one_of_the_feed():
    assert [el.attrib.get("content-desc") for el in _found("search.shop_tab", SEARCH_RESULTS)] == ["Boutique"]
    assert _found("search.shop_tab", FEED) == []


def test_the_comment_sheet_closes_by_its_own_cross_only():
    found = _found("popup.comments_close_button", COMMENT_SHEET)
    assert [el.attrib.get("content-desc") for el in found] == ["Fermer"]
    # The suggestion page has its own clickable « Fermer ».
    assert 'content-desc="Fermer"' in SUGGESTION_PAGE
    for screen in (FOLLOWING_LIST, CONVERSATION, SUGGESTION_PAGE):
        assert _found("popup.comments_close_button", screen) == []


def test_the_inbox_is_told_by_its_title_not_by_the_bottom_bar_or_the_launcher():
    assert len(_found("popup.inbox_page_indicator", INBOX)) == 1
    # The feed's bottom bar and the launcher's app both read « Messages ».
    for screen in (FEED, LAUNCHER):
        assert 'content-desc="Messages"' in screen
        assert _found("popup.inbox_page_indicator", screen) == []


def test_the_promo_cross_is_the_clickable_beside_the_invite_banner():
    found = _found("popup.promo_close_button", INBOX)
    assert len(found) == 1
    assert found[0].attrib.get("clickable") == "true"
    # The same inbox once the banner is gone, and other screens with their own « Fermer ».
    for screen in (INBOX_WITHOUT_BANNER, COMMENT_SHEET, SUGGESTION_PAGE, CONVERSATION):
        assert _found("popup.promo_close_button", screen) == []


def test_a_profile_is_told_by_its_stat_label_not_by_a_following_tab():
    assert len(_found("profile.profile_page_indicator", PROFILE)) == 1
    # The feed's « Suivis » tab, and the following list whose title and buttons say « Suivis ».
    assert _found("profile.profile_page_indicator", FEED) == []
    assert _found("profile.profile_page_indicator", FOLLOWING_LIST) == []


def test_the_following_tab_is_the_feed_header_one_not_a_profile_or_list_label():
    assert len(_found("navigation.following_tab", FEED)) == 1
    assert _found("navigation.following_tab", PROFILE) == []
    assert _found("navigation.following_tab", FOLLOWING_LIST) == []


def test_the_search_follow_button_is_one_per_user_row_and_none_on_a_follower_list():
    rows = USERS_TAB.count(":id/tv_username")
    assert rows == 10
    assert len(_found("search.user_result_follow_button", USERS_TAB)) == rows
    assert _found("search.user_result_follow_button", FOLLOWING_LIST) == []
    assert _found("search.user_result_follow_button", NEW_FOLLOWERS) == []


@pytest.mark.parametrize("name, share_desc", [
    ("tt4693_fr_ad_with_label.xml", "Partager une vidéo. 18 partages"),
    ("tt4703_fr_for_you_video.xml", "Partager une vidéo. Partager partages"),
])
def test_the_video_share_button_reads_with_or_without_a_count(name, share_desc):
    screen = _capture(name)
    assert f'content-desc="{share_desc}"' in screen
    assert len(_found("video_engagement.share_button", screen)) == 1
    assert len(_found("video_state.video_page_indicator", screen)) == 1


def test_other_share_labels_are_not_a_video_page():
    """Our own profile carries a « Partager » button; a DM conversation shares nothing."""
    assert 'content-desc="Partager"' in OWN_PROFILE
    for screen in (CONVERSATION, OWN_PROFILE):
        assert _found("video_engagement.share_button", screen) == []
        assert _found("video_state.video_page_indicator", screen) == []


@pytest.mark.parametrize("key, singleton, prop", [
    ("navigation.shop_tab", "NAVIGATION_SELECTORS", "shop_tab"),
    ("navigation.following_tab", "NAVIGATION_SELECTORS", "following_tab"),
    ("search.shop_tab", "SEARCH_SELECTORS", "shop_tab"),
    ("popup.comments_close_button", "POPUP_SELECTORS", "comments_close_button"),
    ("popup.inbox_page_indicator", "POPUP_SELECTORS", "inbox_page_indicator"),
    ("popup.promo_close_button", "POPUP_SELECTORS", "promo_close_button"),
    ("profile.profile_page_indicator", "PROFILE_SELECTORS", "profile_page_indicator"),
    ("search.user_result_follow_button", "SEARCH_SELECTORS", "user_result_follow_button"),
    ("video_engagement.share_button", "VIDEO_ENGAGEMENT_SELECTORS", "share_button"),
    ("video_state.video_page_indicator", "VIDEO_STATE_SELECTORS", "video_page_indicator"),
])
def test_the_catalogue_field_carries_the_french_entry(key, singleton, prop):
    entries = L(key)
    assert entries
    field = getattr(getattr(catalogue, singleton), prop)
    assert all(entry in field for entry in entries)


@pytest.mark.parametrize("key", [
    "popup.suggestion_close", "popup.suggestion_follow_back", "popup.suggestion_not_interested",
])
def test_the_suggestion_page_buttons_answer_on_that_page_only(key):
    assert len(_found(key, SUGGESTION_PAGE)) == 1
    # « Suivre en retour » on the new followers page and in a conversation; « Pas intéressé(e) »
    # under a feed video; the three words together on a feed card that is not the page.
    for screen in (NEW_FOLLOWERS, CONVERSATION, FEED_SURVEY, FEED_PEOPLE_CARD, FOLLOWING_LIST):
        assert _found(key, screen) == []
    assert "Personnes que tu pourrais connaître" in FEED_PEOPLE_CARD
    assert "Pas intéressé(e)" in FEED_SURVEY and "Suivre en retour" in NEW_FOLLOWERS
