"""On 46.9.3 the DM send arrow is an ImageView with no content-desc, shown only once the composer
holds text; the 46.9.3 override finds it by its place after the stickers button. With an empty
composer the same slot holds the "+" Button, and the search bar's "Plus" follows no Button.

Shapes follow the 46.9.3 captures; evaluated by uiautomator2's own `d.xpath()` engine. Texts are
invented.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.conversation import CONVERSATION_SELECTORS

STICKERS = "Ouvrir les stickers, les GIF et les émojis"


def _n(cls, attrs="", children=""):
    return f'<node class="android.widget.{cls}" resource-id="" bounds="[0,0][10,10]" {attrs}>{children}</node>'


def _composer(text, hint, last_slot):
    field = _n("FrameLayout", children=_n("EditText", f'text="{text}" hint="{hint}" clickable="true"'))
    actions = _n("LinearLayout", children=(
        _n("FrameLayout", children=_n("Button", f'content-desc="{STICKERS}" clickable="true"'))
        + _n("FrameLayout", children=last_slot)))
    return f'<hierarchy rotation="0">{_n("ViewGroup", children=field + actions)}</hierarchy>'


TYPED = _composer("Bonjour", "", _n("ImageView", 'content-desc="" clickable="true"'))
EMPTY = _composer("Message…", "Message…", _n("Button", 'content-desc="" clickable="true"'))
EMPTY_WITH_IMAGE_SLOT = _composer("Message…", "Message…", _n("ImageView", 'content-desc="" clickable="true"'))
SEARCH = ('<hierarchy rotation="0">' + _n("RelativeLayout", children=(
    _n("FrameLayout", children=_n("ImageView", 'clickable="true"'))
    + _n("FrameLayout", children=_n("EditText", 'text="cinema" hint="" clickable="true"')
         + _n("ImageView", 'content-desc="Effacer le champ de recherche" clickable="true"'))
    + _n("FrameLayout", children=_n("LinearLayout", children=_n(
        "ImageView", 'content-desc="Plus" clickable="true"'))))) + "</hierarchy>")


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
