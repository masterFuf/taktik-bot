"""TikTok marks an ad two ways on 46.9.3, in French and in English: a label button ("Publicité",
"Ad"), and a promoted sound ("Musique promotionnelle", "Promoted Music"), which a promoted series
carries even without the button.

The screens reproduce the shape of the captures (every element a <node>, the widget type an
attribute), evaluated by uiautomator2's own `d.xpath()` engine. Brands and counts are invented.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.state import VIDEO_STATE_SELECTORS

PKG = "com.zhiliaoapp.musically:id/"


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _n(cls, text="", desc="", rid=""):
    return (f'<node class="android.widget.{cls}" text="{text}" content-desc="{desc}" '
            f'resource-id="{rid}" clickable="true" bounds="[0,0][10,10]" />')


def _video(sound, *extra):
    body = "".join((
        _n("Button", desc="Profil Marque Demo"),
        _n("TextView", "Marque Demo"),
        _n("TextView", "Une publicité, ça se voit ? #publicité"),
        _n("Button", desc="Partager une vidéo. 3 partages"),
        _n("Button", desc=sound, rid=PKG + "pmi"),
        *extra,
    ))
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{body}</hierarchy>'


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


def test_the_publicite_button_marks_an_ad():
    xml = _video("Son : Musique promotionnelle par Marque Demo",
                 _n("Button", "Publicité", rid=PKG + "i8p"))
    assert _is_ad(xml)


def test_a_promoted_series_without_the_button_is_still_an_ad():
    assert _is_ad(_video("Son : Musique promotionnelle par Serie Demo"))


def test_an_organic_video_is_not_an_ad_even_when_its_caption_says_publicite():
    assert not _is_ad(_video("Son : son original - demo_author par Demo"))


def test_the_english_ad_button_and_promoted_sound_mark_an_ad():
    set_active_locale("en")
    try:
        with_button = _video("Sound: Promoted Music by Brand Demo", _n("Button", "Ad", rid=PKG + "i8p"))
        sound_only = _video("Sound: Promoted Music by Brand Demo")
        organic = _video("Sound: original sound - demo_author by Demo")
        assert _is_ad(with_button)
        assert _is_ad(sound_only)
        assert not _is_ad(organic)
    finally:
        set_active_locale("fr")
