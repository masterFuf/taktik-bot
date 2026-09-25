"""The hashtag search finds the search bar on Instagram 447, where it is a Button until tapped.

Measured on a Pixel 6a (IG 447, 2026-09-24): every entry of the list required an EditText, found
nothing, and the hashtag run ended at once on "sources exhausted" with no like. The structure below
follows that screen (the explore grid under the search bar); texts are Instagram's own. The 447 entry
is a version override (compat/data/overrides/instagram.yaml), applied here as the patcher does.
"""

from pathlib import Path

import pytest
import yaml
from uiautomator2.xpath import PageSource, XPathSelector

from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.locales import active_locale, set_active_locale

IG = "com.instagram.android:id"
OVERRIDES = Path(__file__).resolve().parents[5] / "taktik" / "core" / "compat" / "data" / "overrides" / "instagram.yaml"


@pytest.fixture
def ig_447(monkeypatch):
    entries = yaml.safe_load(OVERRIDES.read_text(encoding="utf-8"))["versions"]["447.0.0.0"]
    monkeypatch.setattr(DETECTION_SELECTORS, "_hashtag_search_bar_selectors_base",
                        entries["detection._hashtag_search_bar_selectors_base"])


def _search_screen(bar_class):
    return (
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
        '<node index="0" text="" resource-id="" class="android.widget.FrameLayout" bounds="[0,0][1080,2400]">'
        f'<node index="0" text="" resource-id="{IG}/action_bar_search_hints_text_layout" '
        'class="android.widget.FrameLayout" clickable="false" bounds="[32,130][940,222]">'
        f'<node index="0" text="Rechercher" resource-id="{IG}/action_bar_search_edit_text" '
        f'class="{bar_class}" content-desc="Rechercher" clickable="true" bounds="[140,140][930,212]" />'
        '</node>'
        f'<node index="3" text="" resource-id="{IG}/search_tab" class="android.widget.FrameLayout" '
        'content-desc="Rechercher et explorer" clickable="true" bounds="[648,2210][864,2330]" />'
        '</node></hierarchy>'
    )


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
    assert _first_match(_search_screen("android.widget.EditText")) == f"{IG}/action_bar_search_edit_text"


def test_the_first_entry_is_the_bar_itself_not_the_search_tab(ig_447):
    """"Rechercher" is also the search TAB's description: tapping it would not open the field."""
    assert DETECTION_SELECTORS.hashtag_search_bar_selectors[0].endswith(
        'action_bar_search_edit_text"]')
