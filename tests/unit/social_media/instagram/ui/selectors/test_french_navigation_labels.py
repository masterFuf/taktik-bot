"""The French entries of the tab bar, the explore search bar and a message thread, read on real screens.

`L(key)` has no fallback: an entry empty in French is a control the bot cannot reach on a French
phone. These entries were empty while English had them; each is now read on a screen of Instagram
410 in French (Pixel 3a, switched by the production language change, then back), anonymized: the
home feed with its tab bar, the explore tab with its search bar, a message thread.

The callers ask uiautomator2 by `description=` (exact), `descriptionContains=` and `text=` (exact),
behind the resource-id they try first; the XPath here asks the same of the dump.

The last test is a ratchet: the properties still empty in French and full in English are only the
ones measured as unreachable, each with its reason.
"""

import importlib
import inspect
import pkgutil

import pytest

import taktik.core.social_media.instagram.ui.selectors.flows as flows
import taktik.core.social_media.instagram.ui.selectors.shell as shell
import taktik.core.social_media.instagram.ui.selectors.support as support
import taktik.core.social_media.instagram.ui.selectors.surfaces as surfaces
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
PKG = "com.instagram.android"

#: Empty in French and full in English, measured: none can be written without inventing a label.
STILL_EMPTY_IN_FRENCH = {
    # Logged-out home: reaching it takes a logout, and no French capture of it exists.
    "AuthSelectors.home_logged_out_screen_indicators",
    # "Review this account before following": Instagram shows it when it decides; never captured.
    "PopupSelectors.review_account_popup_indicators",
    # No 410 post viewer has a next-post control, in any language (the English "Next" is the
    # creation flow's button); the grid's property has no caller.
    "PostSelectors.next_post_button_selectors",
    "PostGridSelectors.next_post_button_selectors",
    # Creation strings that no code reads.
    "ContentCreationSelectors.caption_placeholder_texts",
    "ContentCreationSelectors.location_button_texts",
    "ContentCreationSelectors.post_type_texts",
}


def _screen(name):
    return parse_ui_dump((FIXTURES / name).read_text(encoding="utf-8"))


HOME = _screen("ig410_fr_home_feed_tab_bar.xml")
EXPLORE = _screen("ig410_fr_explore_search_bar.xml")
THREAD = _screen("ig410_fr_dm_thread.xml")


@pytest.fixture
def french():
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)


def _instagram_ids(root, xpath):
    return [node.get("resource-id") for node in root.xpath(xpath) if node.get("package") == PKG]


def test_the_home_tab_is_found_by_its_french_description(french):
    assert NAVIGATION_SELECTORS.home_tab_descriptions
    for label in NAVIGATION_SELECTORS.home_tab_descriptions:
        assert _instagram_ids(HOME, f'//*[@content-desc="{label}"]') == [f"{PKG}:id/feed_tab"]
    for label in NAVIGATION_SELECTORS.home_tab_description_contains:
        assert _instagram_ids(HOME, f'//*[contains(@content-desc, "{label}")]') == [f"{PKG}:id/feed_tab"]
    assert NAVIGATION_SELECTORS.home_tab_description_contains


def test_the_search_tab_is_found_by_its_french_description(french):
    assert NAVIGATION_SELECTORS.search_tab_descriptions
    for label in NAVIGATION_SELECTORS.search_tab_descriptions:
        assert _instagram_ids(HOME, f'//*[@content-desc="{label}"]') == [f"{PKG}:id/search_tab"]
    assert NAVIGATION_SELECTORS.search_tab_description_contains
    for label in NAVIGATION_SELECTORS.search_tab_description_contains:
        assert _instagram_ids(HOME, f'//*[contains(@content-desc, "{label}")]') == [f"{PKG}:id/search_tab"]


def test_the_explore_search_bar_is_found_by_its_french_text(french):
    assert NAVIGATION_SELECTORS.explore_search_bar_texts
    for label in NAVIGATION_SELECTORS.explore_search_bar_texts:
        assert _instagram_ids(EXPLORE, f'//*[@text="{label}"]') == [f"{PKG}:id/action_bar_search_edit_text"]


def test_the_back_button_of_a_thread_is_found_by_its_french_description(french):
    assert DM_SELECTORS.conversation_back_descriptions
    for label in DM_SELECTORS.conversation_back_descriptions:
        assert _instagram_ids(THREAD, f'//*[@content-desc="{label}"]') == [f"{PKG}:id/header_left_button"]


def _properties(locale):
    locales.set_active_locale(locale)
    values = {}
    for package in (shell, surfaces, flows, support):
        modules = [importlib.import_module(name)
                   for _, name, _ in pkgutil.walk_packages(package.__path__, f"{package.__name__}.")]
        for module in modules:
            for class_name, cls in inspect.getmembers(module, inspect.isclass):
                if not class_name.endswith("Selectors") or cls.__module__ != module.__name__:
                    continue
                instance = cls()
                for name, _ in inspect.getmembers(cls, lambda member: isinstance(member, property)):
                    value = getattr(instance, name)
                    if isinstance(value, (list, tuple)):
                        values[f"{class_name}.{name}"] = list(value)
    return values


def test_only_the_measured_properties_stay_empty_in_french():
    before = locales.active_locale()
    try:
        french, english = _properties("fr"), _properties("en")
    finally:
        locales.set_active_locale(before)
    empty_in_french = {key for key, value in english.items() if value and not french.get(key)}
    assert empty_in_french <= STILL_EMPTY_IN_FRENCH, sorted(empty_in_french - STILL_EMPTY_IN_FRENCH)
