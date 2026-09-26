"""The « Tout voir » of the Users section on the search results, on a French phone.

`search.view_all_button` was EMPTY in French. `L()` does not fall back to English: under the
French locale the field held no selector at all, so the control could not be found. The label
was later captured on the Top results of TikTok 43.1.4 (the reference version) and 47.0.3.

The screens below are extracts of those captures, then anonymized: structure, ids and bounds of
the capture; no third-party text is kept. Evaluated by uiautomator2's own `d.xpath()` engine,
through `first_matching`, as production reads a selector list.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS

ID = "com.zhiliaoapp.musically:id/"


def _node(cls, rid="", text="", desc="", clickable=False, bounds="[0,0][1,1]", children=""):
    head = (f'class="{cls}" resource-id="{rid and ID + rid}" text="{text}" content-desc="{desc}" '
            f'clickable="{str(clickable).lower()}" bounds="{bounds}"')
    return f"<node {head}>{children}</node>" if children else f"<node {head}/>"


def _screen(*body):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">{"".join(body)}</node>'
            "</hierarchy>")


def _users_section(section, header, title, link, label, chevron, rows, bounds):
    """The Users section of the Top results: a title and a « Tout voir » link in a header row."""
    top, link_bounds, label_bounds = bounds
    return _node("android.widget.LinearLayout", section, bounds=top[0], children=(
        _node("android.view.ViewGroup", header, clickable=True, bounds=top[1], children=(
            _node("android.widget.TextView", title, "Utilisateurs", bounds=top[2])
            + _node("android.widget.LinearLayout", link, clickable=True, bounds=link_bounds, children=(
                _node("android.widget.TextView", label, "Tout voir", bounds=label_bounds)
                + _node("android.widget.ImageView", chevron)))))
        + _node("android.widget.LinearLayout", rows, children=_node(
            "androidx.recyclerview.widget.RecyclerView", children=_node(
                "android.widget.Button", clickable=True)))))


#: Top results, TikTok 43.1.4 (Pixel 3a, French).
RESULTS_43_1_4 = _screen(_users_section(
    "sm4", "n54", "sm3", "sm5", "sm6", "ks1", "sm1",
    (("[0,330][1080,1088]", "[0,330][1080,435]", "[0,374][853,435]"),
     "[853,383][1036,427]", "[853,383][1003,427]")))

#: Top results, TikTok 47.0.3 (Pixel 6a, French): same shape, every build id moved.
RESULTS_47_0_3 = _screen(_users_section(
    "vj9", "p9e", "vj8", "vj_", "vja", "mhj", "vj6",
    (("[0,373][1080,710]", "[0,373][1080,473]", "[0,415][862,473]"),
     "[862,423][1038,465]", "[862,423][1006,465]")))

#: The same label elsewhere: the Activity page (43.1.4), the new followers page (46.6.3) and the
#: suggested accounts of a profile (47.0.3). None of them sits beside a « Utilisateurs » title.
ACTIVITY_43_1_4 = _screen(_node(
    "android.widget.RelativeLayout", "ry0", clickable=True, bounds="[0,1269][1080,1364]", children=_node(
        "android.widget.RelativeLayout", bounds="[449,1295][630,1337]", children=(
            _node("android.widget.TextView", "y6h", "Tout voir", bounds="[449,1295][593,1337]")
            + _node("android.widget.ImageView", "j8p", desc="Défiler vers le bas")))))
NEW_FOLLOWERS_46_6_3 = _screen(_node(
    "android.widget.RelativeLayout", "ufg", clickable=True, bounds="[0,903][1080,998]", children=_node(
        "android.widget.RelativeLayout", bounds="[449,929][630,971]", children=(
            _node("android.widget.TextView", "tv_see_all", "Tout voir", bounds="[449,929][593,971]")
            + _node("android.widget.ImageView", "kmr", desc="Défiler vers le bas")))))
PROFILE_SUGGESTED_47_0_3 = _screen(_node(
    "android.widget.RelativeLayout", "k2v", bounds="[0,726][1080,768]", children=(
        _node("android.widget.TextView", "ze8", "Comptes suggérés", bounds="[42,726][351,768]")
        + _node("android.widget.ImageView", "la1", clickable=True)
        + _node("android.widget.LinearLayout", "user_card_horizontal_right_widget", clickable=True,
                bounds="[868,726][1038,768]", children=(
                    _node("android.widget.TextView", "vpy", "Tout voir", bounds="[868,726][1012,768]")
                    + _node("android.widget.ImageView", "vpw"))))))


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self.xml


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _found(xml):
    return first_matching(_Device(xml), SEARCH_SELECTORS.view_all_button)


def test_the_reference_results_offer_their_users_link():
    """43.1.4, the reference: the link of the Users section, by its id and its label."""
    found = _found(RESULTS_43_1_4)
    assert [el.attrib.get("resource-id") for el in found] == [ID + "sm6"]


def test_the_link_is_still_found_once_the_build_ids_moved():
    """47.0.3: `sm6` is gone, the section keeps its shape and its French labels."""
    found = _found(RESULTS_47_0_3)
    assert [el.attrib.get("resource-id") for el in found] == [ID + "vja"]


@pytest.mark.parametrize("xml", [ACTIVITY_43_1_4, NEW_FOLLOWERS_46_6_3, PROFILE_SUGGESTED_47_0_3],
                         ids=["activity", "new-followers", "profile-suggested"])
def test_the_same_label_on_another_screen_is_not_the_search_link(xml):
    assert _found(xml) == []
