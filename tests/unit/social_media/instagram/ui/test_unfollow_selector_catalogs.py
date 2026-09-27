"""The unfollow catalogue holds no visible text: every label comes from the locale layer.

This test used to lock "Following", "Follow back" and "Unfollow" as expected values, which is
what kept the unfollow English-only. It now checks that those literals are gone, and that the
selectors built from the locale labels find the real controls, on real dumps, anonymized: the own
followers list of Instagram 447 in French (Pixel 6a, 2026-09-27) and of 410 in English (Pixel 3a,
2026-09-23), both with their categories, and the following list of 410 in French (Pixel 3).

The private account's confirmation dialog is still written by hand: it only shows once a
followed account's button is tapped, which is the unfollow itself.
"""

from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale

APP = "com.instagram.android"
FIXTURES = Path(__file__).parents[1] / "fixtures"


def _capture(name):
    return etree.fromstring((FIXTURES / name).read_bytes())


FOLLOWERS_447_FR = _capture("ig447_fr_own_followers_list.xml")
FOLLOWERS_410_EN = _capture("ig410_en_own_followers_list_categories.xml")
FOLLOWING_410_FR = _capture("ig410_fr_following_list_sorted_default.xml")


@pytest.fixture(autouse=True)
def _reset_locale():
    yield
    set_active_locale(None)


def _confirm_dialog(label):
    """Written by hand: see the module docstring."""
    return etree.fromstring(
        f'<hierarchy><node class="android.widget.FrameLayout"><node text="{label}" '
        f'resource-id="{APP}:id/primary_button" class="android.widget.Button" content-desc="" />'
        f'</node></hierarchy>'.encode("utf-8"))


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
    """447 in French titles its tabs "678 followers", "1 292 suivi(e)s", "0 abonnements"."""
    set_active_locale("fr")
    found = _matches(FOLLOWERS_447_FR, UNFOLLOW_SELECTORS.unified_followers_tab_selectors(APP))
    assert found[:1] == ["678 followers"]
    assert "0\u00a0abonnements" not in found


def test_english_followers_tab():
    set_active_locale("en")
    assert _matches(FOLLOWERS_410_EN, UNFOLLOW_SELECTORS.unified_followers_tab_selectors(APP)) == [
        "295 followers"]


def _first_and_all(tree, selectors):
    found = [node for sel in selectors for node in tree.xpath(sel)]
    return found[0], {node.get("text") or node.get("content-desc") for node in found}


def test_french_447_fans_category():
    """The row's clickable container first, its title after: one category, "Interactions les plus
    rares" and the others left alone."""
    set_active_locale("fr")
    first, labels = _first_and_all(FOLLOWERS_447_FR, UNFOLLOW_SELECTORS.fans_category_selectors(APP))
    assert first.get("resource-id") == f"{APP}:id/container"
    assert labels == {"Followers que vous ne suivez pas"}


def test_english_fans_category():
    set_active_locale("en")
    first, labels = _first_and_all(FOLLOWERS_410_EN, UNFOLLOW_SELECTORS.fans_category_selectors(APP))
    assert first.get("resource-id") == f"{APP}:id/container"
    assert labels == {"People you don't follow back"}


@pytest.mark.parametrize("lang,label", [("fr", "Ne plus suivre"), ("en", "Unfollow")])
def test_confirm_button_is_scoped_by_id_and_label(lang, label):
    set_active_locale(lang)
    assert _matches(_confirm_dialog(label), UNFOLLOW_SELECTORS.unfollow_confirm_selectors(APP))[0] == label


def test_french_sort_button_found_by_its_content_desc():
    set_active_locale("fr")
    first, labels = _first_and_all(FOLLOWING_410_FR, UNFOLLOW_SELECTORS.sort_button)
    assert first.get("resource-id") == f"{APP}:id/sorting_entry_row_icon"
    assert labels == {"Trier par"}
