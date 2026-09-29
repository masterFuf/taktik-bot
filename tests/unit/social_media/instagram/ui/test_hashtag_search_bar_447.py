"""The hashtag search finds the search bar on Instagram 447, where it is a Button until tapped.

Measured on a Pixel 6a (IG 447, 2026-09-24): every entry of the list required an EditText, found
nothing, and the hashtag run ended at once on "sources exhausted" with no like. The screens are real
dumps, anonymized, all in French: that very screen (the explore grid under a Button search bar), a
447 hashtag page whose bar holds the hashtag (an EditText by then), and the explore grid of 410
(Pixel 3a), whose bar is an EditText from the start. The 447 entry is a version override
(compat/data/overrides/instagram.yaml), applied here as the patcher does.
"""

import pytest
import yaml
from uiautomator2.xpath import PageSource, XPathSelector

from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale
from unit.paths import CORE

IG = "com.instagram.android:id"
OVERRIDES = CORE / "taktik/core/compat/data/overrides/instagram.yaml"


@pytest.fixture
def ig_447(monkeypatch):
    entries = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8"))["versions"]["447.0.0.0"]
    monkeypatch.setattr(DETECTION_SELECTORS, "_hashtag_search_bar_selectors_base",
                        entries["detection._hashtag_search_bar_selectors_base"])


FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREENS = {
    "android.widget.Button": "ig447_fr_explore_grid.xml",
    "android.widget.EditText": "ig447_fr_hashtag_page.xml",
}


def _search_screen(bar_class, name=None):
    xml = (FIXTURES / (name or SCREENS[bar_class])).read_text(encoding="utf-8")
    assert f'resource-id="{IG}/action_bar_search_edit_text" class="{bar_class}"' in xml
    return xml


@pytest.fixture(autouse=True)
def _french():
    before = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(before)


def _first_match(xml):
    source = PageSource(xml)
    for selector in DETECTION_SELECTORS.hashtag_search_bar_selectors:
        found = XPathSelector(selector).all(source)
        if found:
            return found[0].attrib.get("resource-id")
    return None


@pytest.mark.parametrize("bar_class", ["android.widget.Button", "android.widget.EditText"])
def test_the_search_bar_is_found_whatever_its_class(ig_447, bar_class):
    assert _first_match(_search_screen(bar_class)) == f"{IG}/action_bar_search_edit_text"


def test_the_410_baseline_keeps_the_edit_text():
    xml = _search_screen("android.widget.EditText", "ig410_fr_explore_grid.xml")
    assert _first_match(xml) == f"{IG}/action_bar_search_edit_text"


def test_the_first_entry_is_the_bar_itself_not_the_search_tab(ig_447):
    """"Rechercher" is also the search TAB's description: tapping it would not open the field."""
    assert DETECTION_SELECTORS.hashtag_search_bar_selectors[0].endswith(
        'action_bar_search_edit_text"]')
