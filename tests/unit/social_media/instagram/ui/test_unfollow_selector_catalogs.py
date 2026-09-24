"""The unfollow catalogue holds no visible text: every label comes from the locale layer.

This test used to lock "Following", "Follow back" and "Unfollow" as expected values, which is
what kept the unfollow English-only. It now checks that those literals are gone, and that the
selectors built from the locale labels find the real controls (structure of the Instagram 410 and
447 dumps, English and French, September 2026; synthetic usernames).
"""

import pytest
from lxml import etree

from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

APP = "com.instagram.android"


@pytest.fixture(autouse=True)
def _reset_locale():
    yield
    set_active_locale(None)


def _tree(*nodes):
    return etree.fromstring(
        ('<hierarchy><node class="android.widget.FrameLayout">' + "".join(nodes) + "</node></hierarchy>").encode("utf-8")
    )


def _tabs(*titles):
    buttons = "".join(
        f'<node text="{t}" resource-id="{APP}:id/title" class="android.widget.Button" content-desc="" />'
        for t in titles
    )
    return f'<node resource-id="{APP}:id/unified_follow_list_tab_layout" class="android.widget.HorizontalScrollView">{buttons}</node>'


def _matches(tree, selectors):
    return [node.get("text") or node.get("content-desc") for sel in selectors for node in tree.xpath(sel)]


def test_no_visible_label_is_hardcoded_in_the_catalogue():
    for literal in ("following_tab_text_probe", "following_button_text", "follow_back_button_text",
                    "unfollow_confirm_text"):
        assert not hasattr(UNFOLLOW_SELECTORS, literal), literal


def test_unfollow_active_package_resource_builders():
    assert (UNFOLLOW_SELECTORS.active_follow_list_username_resource_id(APP)
            == "com.instagram.android:id/follow_list_username")
    assert (UNFOLLOW_SELECTORS.active_follow_list_button_resource_id(APP)
            == "com.instagram.android:id/follow_list_row_large_follow_button")
    assert (UNFOLLOW_SELECTORS.active_follow_list_button_resource_id("com.clone.x")
            == "com.clone.x:id/follow_list_row_large_follow_button")


def test_french_447_followers_tab_and_never_the_subscriptions_tab():
    """447 in French titles its tabs "673 followers", "1 287 suivi(e)s", "0 abonnements"."""
    set_active_locale("fr")
    tree = _tree(_tabs("673 followers", "1 287 suivi(e)s", "0\xa0abonnements", "À vérifier"))
    assert _matches(tree, UNFOLLOW_SELECTORS.unified_followers_tab_selectors(APP))[:1] == ["673 followers"]
    assert "0\xa0abonnements" not in _matches(tree, UNFOLLOW_SELECTORS.unified_followers_tab_selectors(APP))


def test_english_followers_tab():
    set_active_locale("en")
    tree = _tree(_tabs("673 followers", "1,287 following"))
    assert _matches(tree, UNFOLLOW_SELECTORS.unified_followers_tab_selectors(APP)) == ["673 followers"]


def test_french_447_fans_category():
    set_active_locale("fr")
    label = "Followers que vous ne suivez pas"
    tree = _tree(
        f'<node text="" resource-id="{APP}:id/container" class="android.widget.Button" content-desc="{label}" />',
        f'<node text="Interactions les plus rares" resource-id="{APP}:id/title" class="android.widget.TextView" content-desc="" />',
    )
    assert _matches(tree, UNFOLLOW_SELECTORS.fans_category_selectors(APP)) == [label]


def test_english_fans_category():
    set_active_locale("en")
    tree = _tree(
        f'<node text="" resource-id="{APP}:id/container" class="android.widget.Button" '
        f'content-desc="People you don\'t follow back" />'
    )
    assert _matches(tree, UNFOLLOW_SELECTORS.fans_category_selectors(APP))


@pytest.mark.parametrize("lang,label", [("fr", "Ne plus suivre"), ("en", "Unfollow")])
def test_confirm_button_is_scoped_by_id_and_label(lang, label):
    set_active_locale(lang)
    tree = _tree(f'<node text="{label}" resource-id="{APP}:id/primary_button" class="android.widget.Button" content-desc="" />')
    assert _matches(tree, UNFOLLOW_SELECTORS.unfollow_confirm_selectors(APP))[0] == label


def test_french_sort_button_found_by_its_content_desc():
    set_active_locale("fr")
    tree = _tree('<node text="" resource-id="" class="android.widget.Button" content-desc="Trier par" />')
    assert _matches(tree, UNFOLLOW_SELECTORS.sort_button) == ["Trier par"]
