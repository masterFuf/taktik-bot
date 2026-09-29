"""On 46.9.3 the DM send arrow is an ImageView with no content-desc, shown only once the composer
holds text; the 46.9.3 override finds it by its place after the stickers button. With an empty
composer the same slot holds the "+" Button, and the search bar's "Plus" follows no Button.

The screens are captures of TikTok 46.9.3 in French (Pixel 6a), anonymized: a conversation whose
composer holds a draft, the same kind of conversation with an empty composer, and the Top results
of a search. One is derived and says so: the empty composer with its "+" drawn as an ImageView, the
shape the override must still refuse (an empty field is its placeholder). Evaluated by
uiautomator2's own `d.xpath()` engine.
"""

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
TYPED = (FIXTURES / "tt4693_fr_dm_composer_typed.xml").read_text(encoding="utf-8")
EMPTY = (FIXTURES / "tt4693_fr_dm_conversation.xml").read_text(encoding="utf-8")
SEARCH = (FIXTURES / "tt4693_fr_search_results.xml").read_text(encoding="utf-8")


def _plus_drawn_as_an_image(xml):
    tree = etree.fromstring(xml.encode("utf-8"))
    field = tree.xpath('//node[@class="android.widget.EditText"]')[0]
    plus = field.getparent().getparent().xpath('.//node')[-1]
    assert plus.get("class") == "android.widget.Button" and plus.get("clickable") == "true"
    plus.set("class", "android.widget.ImageView")
    return etree.tostring(tree, encoding="unicode")


EMPTY_WITH_IMAGE_SLOT = _plus_drawn_as_an_image(EMPTY)


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


def _found(xml):
    device = _Device(xml)
    return [el for sel in CONVERSATION_SELECTORS.send_button for el in device.xpath(sel).all()]


@pytest.fixture
def on_46_9_3():
    set_active_locale("fr")
    apply_version_overrides("tiktok", "46.9.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")
    set_active_locale(None)


def test_the_baseline_does_not_find_the_unlabelled_arrow():
    set_active_locale("fr")
    try:
        assert _found(TYPED) == []
    finally:
        set_active_locale(None)


def test_on_46_9_3_the_arrow_is_found_once_the_composer_holds_text(on_46_9_3):
    found = _found(TYPED)
    assert len(found) == 1
    assert found[0].elem.tag == "android.widget.ImageView"


@pytest.mark.parametrize("xml", [EMPTY, EMPTY_WITH_IMAGE_SLOT, SEARCH], ids=["plus", "empty", "search"])
def test_on_46_9_3_nothing_else_is_taken_for_the_arrow(on_46_9_3, xml):
    assert _found(xml) == []
