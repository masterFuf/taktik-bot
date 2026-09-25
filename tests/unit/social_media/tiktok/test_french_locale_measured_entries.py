"""French entries written from captures of TikTok 43.1.4 and 46.6.3: each answers on its screen
and stays silent on the screen that carries the same word elsewhere.

The screens below reproduce the SHAPE of those captures, as the device dumps them (every element
a <node>, the widget type an attribute), evaluated by uiautomator2's own `d.xpath()` engine. Names
and counts are invented: the dumps stay out of this public repository.
"""

import pytest
from uiautomator2.xpath import XPathEntry

import taktik.core.social_media.tiktok.ui.selectors as catalogue
from taktik.core.social_media.tiktok.ui.selectors.locales import L, set_active_locale

PKG = "com.zhiliaoapp.musically:id/"


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _n(cls, text="", desc="", rid="", clickable=False, selected=False, hint=None, children=""):
    attrs = (f'class="android.widget.{cls}" text="{text}" content-desc="{desc}" '
             f'resource-id="{rid}" clickable="{str(clickable).lower()}" '
             f'selected="{str(selected).lower()}" bounds="[0,0][10,10]"')
    if hint is not None:
        attrs += f' hint="{hint}"'
    return f"<node {attrs}>{children}</node>"


def _screen(*body):
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{"".join(body)}</hierarchy>'


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


def _tab(label, selected=False):
    return _n("FrameLayout", clickable=True, selected=selected, children=_n(
        "LinearLayout", desc=label, children=_n("TextView", label, rid=PKG + "text1")))


FEED = _screen(_n("HorizontalScrollView", children=_n("LinearLayout", children=(
    _tab("Suivis") + _tab("Boutique") + _tab("Pour toi", selected=True)))))

SEARCH_RESULTS = _screen(_n("LinearLayout", children="".join(
    _n("FrameLayout", desc=label, clickable=True, children=_n("TextView", label))
    for label in ("Top", "Utilisateurs", "Vidéos", "Boutique"))))

COMPOSER = _n("EditText", "Ajouter un commentaire…", rid=PKG + "egn", clickable=True,
              hint="Ajouter un commentaire…")
COMMENT_SHEET = _screen(_n("FrameLayout", children=(
    _n("LinearLayout", children=_n("TextView", "128 commentaires"))
    + _n("RelativeLayout", children=_n("ImageView", desc="Fermer", clickable=True))
    + _n("FrameLayout", children=COMPOSER))))

FOLLOWERS_LIST = _screen(
    _n("ImageView", desc="Fermer", clickable=True)
    + _n("LinearLayout", clickable=True, children=_n("TextView", "Suivis 39", rid=PKG + "text1"))
    + _n("LinearLayout", clickable=True, children=(
        _n("TextView", "Alpha", rid=PKG + "txt_user_name")
        + _n("TextView", "alpha_one", rid=PKG + "txt_desc")
        + _n("Button", "Suivre", clickable=True))))

BOTTOM_BAR = _n("FrameLayout", desc="Messages", clickable=True, children=_n("TextView", "Messages"))

INBOX = _screen(
    _n("TextView", "Messages", rid=PKG + "title")
    + _n("ViewGroup", children=(
        _n("ViewGroup", clickable=True, children=(
            _n("TextView", "Élevez un compagnon ensemble !") + _n("Button", "Inviter", clickable=True)))
        + _n("FrameLayout", clickable=True, children=_n("ImageView", desc="Fermer")))))

LAUNCHER = _screen(_n("TextView", "Messages", desc="Messages", clickable=True,
                      rid="com.google.android.apps.nexuslauncher:id/icon"))

FRIENDS_PAGE = _screen(
    _n("LinearLayout", children=_n("Button", "Inviter", clickable=True))
    + _n("LinearLayout", children=_n("FrameLayout", clickable=True,
                                     children=_n("ImageView", desc="Fermer"))))

PROFILE = _screen(_n("LinearLayout", children=(
    _n("LinearLayout", clickable=True, children=_n("TextView", "262") + _n("TextView", "Suivis"))
    + _n("ViewGroup", clickable=True, children=_n("TextView", "155") + _n("TextView", "Followers")))))

FEED_FOLLOWING_TAB = _screen(_n("FrameLayout", desc="Suivis", children=_n(
    "LinearLayout", children=_n("TextView", "Suivis", rid=PKG + "text1") + _n("View"))))


def _user_row(handle):
    return _n("Button", clickable=True, children=_n("RelativeLayout", clickable=True, children=(
        _n("LinearLayout", children=(
            _n("ViewGroup", children=_n("TextView", handle, rid=PKG + "tv_username"))
            + _n("TextView", "154 followers", rid=PKG + "tv_desc")))
        + _n("FrameLayout", children=_n("Button", "Suivre", clickable=True)))))


USERS_TAB = _screen(_user_row("alpha_one") + _user_row("beta_two"))


def _video(share_desc):
    return _screen(_n("FrameLayout", children=(
        _n("Button", desc="Attribuer un « J'aime » à la vidéo. 12 « J'aime »", clickable=True)
        + _n("Button", desc=share_desc, clickable=True))))


CONVERSATION = _screen(
    _n("TextView", "Partager la publication")
    + _n("EditText", clickable=True, hint="Envoyer un message…")
    + _n("ImageView", desc="Fermer", clickable=True))

OWN_PROFILE_SHARE = _screen(_n("ImageView", desc="Partager"))


def test_the_shop_tab_of_the_feed_is_not_the_one_of_search_results():
    assert len(_found("navigation.shop_tab", FEED)) == 1
    assert _found("navigation.shop_tab", SEARCH_RESULTS) == []


def test_the_shop_tab_of_search_results_is_not_the_one_of_the_feed():
    assert [el.attrib.get("content-desc") for el in _found("search.shop_tab", SEARCH_RESULTS)] == ["Boutique"]
    assert _found("search.shop_tab", FEED) == []


def test_the_comment_sheet_closes_by_its_own_cross_only():
    found = _found("popup.comments_close_button", COMMENT_SHEET)
    assert [el.attrib.get("content-desc") for el in found] == ["Fermer"]
    assert _found("popup.comments_close_button", FOLLOWERS_LIST) == []
    assert _found("popup.comments_close_button", CONVERSATION) == []


def test_the_inbox_is_told_by_its_title_not_by_the_bottom_bar_or_the_launcher():
    assert len(_found("popup.inbox_page_indicator", INBOX)) == 1
    assert _found("popup.inbox_page_indicator", _screen(BOTTOM_BAR)) == []
    assert _found("popup.inbox_page_indicator", LAUNCHER) == []


def test_the_promo_cross_is_the_clickable_beside_the_invite_banner():
    found = _found("popup.promo_close_button", INBOX)
    assert len(found) == 1
    assert found[0].attrib.get("clickable") == "true"
    assert _found("popup.promo_close_button", FRIENDS_PAGE) == []
    assert _found("popup.promo_close_button", COMMENT_SHEET) == []


def test_a_profile_is_told_by_its_stat_label_not_by_a_following_tab():
    assert len(_found("profile.profile_page_indicator", PROFILE)) == 1
    assert _found("profile.profile_page_indicator", FEED_FOLLOWING_TAB) == []
    assert _found("profile.profile_page_indicator", FOLLOWERS_LIST) == []


def test_the_search_follow_button_is_one_per_user_row_and_none_on_a_follower_list():
    assert len(_found("search.user_result_follow_button", USERS_TAB)) == 2
    assert _found("search.user_result_follow_button", FOLLOWERS_LIST) == []


@pytest.mark.parametrize("share_desc", ["Partager une vidéo. 1 234 partages",
                                        "Partager une vidéo. Partager partages"])
def test_the_video_share_button_reads_with_or_without_a_count(share_desc):
    screen = _video(share_desc)
    assert len(_found("video_engagement.share_button", screen)) == 1
    assert len(_found("video_state.video_page_indicator", screen)) == 1


def test_other_share_labels_are_not_a_video_page():
    for screen in (CONVERSATION, OWN_PROFILE_SHARE):
        assert _found("video_engagement.share_button", screen) == []
        assert _found("video_state.video_page_indicator", screen) == []


@pytest.mark.parametrize("key, singleton, prop", [
    ("navigation.shop_tab", "NAVIGATION_SELECTORS", "shop_tab"),
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


SKIP_HINT = _n("TextView", "Balaie vers le haut pour ignorer")
SUGGESTION_PAGE = _screen(_n("FrameLayout", children=(
    _n("ImageView", desc="Fermer", clickable=True)
    + _n("TextView", "demo_suggested")
    + _n("TextView", "Personnes que tu pourrais connaître")
    + _n("Button", "Pas intéressé(e)", clickable=True)
    + _n("Button", "Suivre en retour", clickable=True)
    + SKIP_HINT)))
FOLLOWERS_TO_FOLLOW_BACK = _screen(
    _n("ImageView", desc="Fermer", clickable=True)
    + _n("Button", "Suivre en retour", clickable=True))
FEED_SURVEY = _screen(_n("Button", "Pas intéressé(e)", clickable=True))


@pytest.mark.parametrize("key", [
    "popup.suggestion_close", "popup.suggestion_follow_back", "popup.suggestion_not_interested",
])
def test_the_suggestion_page_buttons_answer_on_that_page_only(key):
    assert len(_found(key, SUGGESTION_PAGE)) == 1
    for screen in (FOLLOWERS_TO_FOLLOW_BACK, FEED_SURVEY, FOLLOWERS_LIST):
        assert _found(key, screen) == []
