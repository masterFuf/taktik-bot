"""TikTok marks an ad two ways on 46.9.3, in French and in English: a label button ("Publicité",
"Ad"), and a promoted sound ("Musique promotionnelle", "Promoted Music"), which a promoted series
carries even without the button.

The screens are real captures of TikTok 46.9.3 (Pixel 6a), anonymized, evaluated by uiautomator2's
own `d.xpath()` engine: in French an ad with its button, a promoted video without it, and an
organic video opened from a search; in English the same three kinds, the organic one from the For
You feed. The organic video whose caption says "#publicité" is the French one with that word added
to its caption (derived: no capture shows such a caption).
"""

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.state import VIDEO_STATE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"
CAPTION_ID = "com.zhiliaoapp.musically:id/desc"


def _screen(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


FR_AD = _screen("tt4693_fr_ad_with_label.xml")
FR_PROMOTED = _screen("tt4693_fr_ad_promoted_sound_only.xml")
FR_ORGANIC = _screen("tt4693_fr_search_result_video.xml")
EN_AD = _screen("tt4693_en_ad_with_label.xml")
EN_PROMOTED = _screen("tt4693_en_ad_promoted_sound_only.xml")
EN_ORGANIC = _screen("tt4693_en_for_you_video.xml")


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


def _is_ad(xml):
    device = _Device(xml)
    return any(device.xpath(sel).exists for sel in VIDEO_STATE_SELECTORS.ad_label)


def _texts(xml):
    return {node.get("text") for node in etree.fromstring(xml.encode("utf-8")).iter("node")}


def _descriptions(xml):
    return [node.get("content-desc") for node in etree.fromstring(xml.encode("utf-8")).iter("node")]


def _caption_says_publicite(xml):
    root = etree.fromstring(xml.encode("utf-8"))
    caption = next(node for node in root.iter("node") if node.get("resource-id") == CAPTION_ID)
    caption.set("text", caption.get("text") + " #publicité")
    return etree.tostring(root, encoding="unicode")


def test_the_publicite_button_marks_an_ad():
    assert "Publicité" in _texts(FR_AD)
    assert _is_ad(FR_AD)


def test_a_promoted_series_without_the_button_is_still_an_ad():
    assert "Publicité" not in _texts(FR_PROMOTED)
    assert any(d.startswith("Son : Musique promotionnelle") for d in _descriptions(FR_PROMOTED))
    assert _is_ad(FR_PROMOTED)


def test_an_organic_video_is_not_an_ad_even_when_its_caption_says_publicite():
    assert not _is_ad(FR_ORGANIC)
    assert not _is_ad(_caption_says_publicite(FR_ORGANIC))


def test_the_english_ad_button_and_promoted_sound_mark_an_ad():
    set_active_locale("en")
    try:
        assert "Ad" in _texts(EN_AD) and "Ad" not in _texts(EN_PROMOTED)
        assert _is_ad(EN_AD)
        assert _is_ad(EN_PROMOTED)
        assert not _is_ad(EN_ORGANIC)
    finally:
        set_active_locale("fr")
