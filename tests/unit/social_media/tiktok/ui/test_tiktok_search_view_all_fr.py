"""The « Tout voir » of the Users section on the search results, on a French phone.

`search.view_all_button` was EMPTY in French. `L()` does not fall back to English: under the
French locale the field held no selector at all, so the control could not be found. The label
was later captured on the Top results of TikTok 43.1.4 (the reference version) and 47.0.3.

The screens are those captures, anonymized: the Top results of 43.1.4 (Pixel 3a) and of 47.0.3
(Pixel 6a), and the same label elsewhere, the Activity page (43.1.4, Pixel 6a) and the suggested
accounts of a profile (47.0.3, Pixel 6a). The new followers page of 46.6.3 is still written by
hand after its capture (capture it again, TikTok 46.6.3 or later, French). Evaluated by
uiautomator2's own `d.xpath()` engine, through `first_matching`, as production reads a selector
list.
"""

from pathlib import Path

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS

ID = "com.zhiliaoapp.musically:id/"
FIXTURES = Path(__file__).parents[1] / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


#: Top results, TikTok 43.1.4 (Pixel 3a, French).
RESULTS_43_1_4 = _capture("tt4314_fr_search_top_results.xml")

#: Top results, TikTok 47.0.3 (Pixel 6a, French): same shape, every build id moved.
RESULTS_47_0_3 = _capture("tt4703_fr_search_top_results.xml")

#: The same label elsewhere: the Activity page (43.1.4), the new followers page (46.6.3) and the
#: suggested accounts of a profile (47.0.3). None of them sits beside a « Utilisateurs » title.
ACTIVITY_43_1_4 = _capture("tt4314_fr_activity.xml")
#: Written by hand after the 46.6.3 capture, which the corpus no longer holds.
NEW_FOLLOWERS_46_6_3 = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    '<node class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">'
    '<node class="android.widget.RelativeLayout" resource-id="com.zhiliaoapp.musically:id/ufg" text="" '
    'content-desc="" clickable="true" bounds="[0,903][1080,998]">'
    '<node class="android.widget.RelativeLayout" resource-id="" text="" content-desc="" clickable="false" '
    'bounds="[449,929][630,971]">'
    '<node class="android.widget.TextView" resource-id="com.zhiliaoapp.musically:id/tv_see_all" '
    'text="Tout voir" content-desc="" clickable="false" bounds="[449,929][593,971]"/>'
    '<node class="android.widget.ImageView" resource-id="com.zhiliaoapp.musically:id/kmr" text="" '
    'content-desc="Défiler vers le bas" clickable="false" bounds="[0,0][1,1]"/>'
    '</node></node></node></hierarchy>'
)
PROFILE_SUGGESTED_47_0_3 = _capture("tt4703_fr_profile_suggested_accounts.xml")


def _labels(xml):
    return {node.get("text") for node in etree.fromstring(xml.encode("utf-8")).iter("node")}


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
    assert "Tout voir" in _labels(xml)
    assert _found(xml) == []
