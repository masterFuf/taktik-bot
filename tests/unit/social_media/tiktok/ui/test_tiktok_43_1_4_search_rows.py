"""TikTok 43.1.4, la version de référence : sur l'onglet Utilisateurs, le tap vise le pseudo.

Relevé sur un Pixel 3a (TikTok 43.1.4, en français), puis anonymisé : structure, ids et bornes
d'origine ; pseudos, noms et sous-titres fictifs ; tout autre texte de tiers vidé.

La rangée d'un résultat (`Button` sur `sh2`) fait toute la largeur et contient le bouton `rdh`
« Suivre ». Les anciennes entrées de rangée (`lnp`, `sh2`, `ye2`, `rdh`) résolvaient toutes cette
rangée, et un tap humain échantillonné dessus tombait sur le bouton environ une fois sur douze. Le
pseudo porte `ye2` ; la rangée cliquable dessous reçoit le tap.

Évalué par le moteur `d.xpath()` de uiautomator2, comme sur le téléphone.
"""

import random

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.shared.behavior.tap import sample_tap_point
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS

# Les deux premières rangées ; la seconde est celle d'un compte en LIVE, dont l'avatar ouvre le LIVE.
USERS_TAB_43_1_4 = """
<node class="androidx.recyclerview.widget.RecyclerView" resource-id="com.zhiliaoapp.musically:id/lnp" clickable="false" bounds="[0,330][1080,2088]" text="" content-desc="">
  <node text="" resource-id="" class="android.widget.Button" content-desc="" clickable="true" bounds="[0,352][1080,555]">
    <node text="" resource-id="com.zhiliaoapp.musically:id/sh2" class="android.widget.RelativeLayout" content-desc="" clickable="true" bounds="[0,352][1080,555]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/h6i" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[30,360][217,547]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/han" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[30,360][217,547]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/k9u" class="X.13er" content-desc="" clickable="true" bounds="[46,376][200,530]"/>
        </node>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/l6w" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[236,375][761,532]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/m_u" class="android.view.ViewGroup" content-desc="" clickable="false" bounds="[236,375][761,427]">
          <node text="\u200e\u2068demo_media\u2069" resource-id="com.zhiliaoapp.musically:id/ye2" class="android.widget.TextView" content-desc="" clickable="false" bounds="[236,375][381,427]"/>
          <node text="" resource-id="com.zhiliaoapp.musically:id/w5l" class="android.widget.ImageView" content-desc="" clickable="false" bounds="[387,382][426,421]"/>
        </node>
        <node text="Demo Media" resource-id="com.zhiliaoapp.musically:id/x8i" class="android.widget.TextView" content-desc="" clickable="false" bounds="[236,427][761,471]"/>
        <node text="" resource-id="com.zhiliaoapp.musically:id/nk5" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[236,477][681,532]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/nk4" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[236,477][681,532]">
            <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[236,477][681,532]">
              <node text="Suivi(e) par Demo Friend " resource-id="com.zhiliaoapp.musically:id/xf0" class="android.widget.TextView" content-desc="" clickable="false" bounds="[236,482][615,526]"/>
              <node text="" resource-id="com.zhiliaoapp.musically:id/re8" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[626,477][681,532]">
                <node text="" resource-id="com.zhiliaoapp.musically:id/b3v" class="android.widget.ImageView" content-desc="" clickable="false" bounds="[626,477][681,532]"/>
              </node>
            </node>
          </node>
        </node>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/vki" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[794,407][1036,495]">
        <node text="Suivre" resource-id="com.zhiliaoapp.musically:id/rdh" class="android.widget.Button" content-desc="" clickable="true" bounds="[794,407][1036,495]"/>
      </node>
    </node>
  </node>
  <node text="" resource-id="" class="android.widget.Button" content-desc="" clickable="true" bounds="[0,555][1080,758]">
    <node text="" resource-id="com.zhiliaoapp.musically:id/sh2" class="android.widget.RelativeLayout" content-desc="" clickable="true" bounds="[0,555][1080,758]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/h6i" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[30,563][217,750]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/k3h" class="android.view.View" content-desc="" clickable="false" bounds="[30,563][217,750]"/>
        <node text="" resource-id="com.zhiliaoapp.musically:id/han" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[30,563][217,750]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/k9u" class="android.widget.Button" content-desc="Regarder le LIVE" clickable="true" bounds="[51,584][195,728]">
            <node text="LIVE" resource-id="" class="android.widget.TextView" content-desc="" clickable="false" bounds="[84,584][161,615]"/>
          </node>
        </node>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/l6w" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[236,586][761,726]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/m_u" class="android.view.ViewGroup" content-desc="" clickable="false" bounds="[236,586][761,638]">
          <node text="\u200e\u2068demo_media_fan\u2069" resource-id="com.zhiliaoapp.musically:id/ye2" class="android.widget.TextView" content-desc="" clickable="false" bounds="[236,586][478,638]"/>
        </node>
        <node text="Demo Fan" resource-id="com.zhiliaoapp.musically:id/x8i" class="android.widget.TextView" content-desc="" clickable="false" bounds="[236,638][761,682]"/>
        <node text="12\xa0followers · 40 j'aime" resource-id="com.zhiliaoapp.musically:id/xf0" class="android.widget.TextView" content-desc="" clickable="false" bounds="[236,682][748,726]"/>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/vki" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[794,610][1036,698]">
        <node text="Suivre" resource-id="com.zhiliaoapp.musically:id/rdh" class="android.widget.Button" content-desc="" clickable="true" bounds="[794,610][1036,698]"/>
      </node>
    </node>
  </node>
</node>"""

#: The row entries 43.1.4 used to carry, kept here only to show what they resolved to.
FORMER_ROW_ENTRIES = [
    '(//androidx.recyclerview.widget.RecyclerView[contains(@resource-id, ":id/lnp")]//android.widget.Button[@clickable="true"])[1]',
    '(//android.widget.Button[@clickable="true"][.//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")]])[1]',
    '(//android.widget.Button[@clickable="true"][.//android.widget.TextView[contains(@resource-id, ":id/ye2")]])[1]',
    '(//android.widget.RelativeLayout[contains(@resource-id, ":id/sh2")][@clickable="true"])[1]',
    '//android.widget.Button[@clickable="true"][.//android.widget.Button[contains(@resource-id, ":id/rdh")]]',
]


class _Screen:
    wait_timeout = 0.0

    def __init__(self, xml):
        self._xml = f'<hierarchy rotation="0">{xml}</hierarchy>'
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self._xml


def _tapped(selectors):
    """Ce que `_find_and_click` taperait : le premier sélecteur qui existe, son premier nœud."""
    screen = _Screen(USERS_TAB_43_1_4)
    for selector in selectors:
        found = screen.xpath(selector)
        if found.exists:
            return found.get(timeout=0)
    return None


def _bounds_of(selector):
    return [el.bounds for el in _Screen(USERS_TAB_43_1_4).xpath(selector).all()]


def _lands_on(bounds, targets, samples=3000):
    rng = random.Random(0)
    for _ in range(samples):
        x, y = sample_tap_point(bounds, rng=rng)
        if any(left <= x <= right and top <= y <= bottom for left, top, right, bottom in targets):
            return True
    return False


FOLLOW_BUTTONS = _bounds_of('//*[contains(@resource-id, ":id/rdh")]')
AVATARS = _bounds_of('//*[contains(@resource-id, ":id/k9u")]')


@pytest.mark.parametrize("selector", FORMER_ROW_ENTRIES)
def test_every_former_row_entry_resolved_the_full_width_row(selector):
    row = _tapped([selector])
    assert row.bounds[0] == 0 and row.bounds[2] == 1080
    assert _lands_on(row.bounds, FOLLOW_BUTTONS)


@pytest.mark.parametrize("catalogue", ["first_user_result", "user_search_item"])
def test_the_followers_workflow_taps_the_first_handle(catalogue):
    handle = _tapped(getattr(FOLLOWERS_SELECTORS, catalogue))
    assert handle.attrib.get("resource-id", "").endswith(":id/ye2")
    assert handle.text.endswith("⁨demo_media⁩")
    assert not _lands_on(handle.bounds, FOLLOW_BUTTONS + AVATARS)


def test_the_named_row_is_tapped_on_its_handle():
    handle = _tapped(SEARCH_SELECTORS.user_result_selectors_for_username("demo_media"))
    assert handle.attrib.get("resource-id", "").endswith(":id/ye2")
    assert not _lands_on(handle.bounds, FOLLOW_BUTTONS + AVATARS)


def test_the_live_account_row_is_tapped_on_its_handle_not_its_avatar():
    """L'avatar d'un compte en LIVE ouvre le LIVE : le tap reste sur le pseudo."""
    handle = _tapped(SEARCH_SELECTORS.user_result_selectors_for_username("demo_media_fan"))
    assert handle.text.endswith("⁨demo_media_fan⁩")
    assert not _lands_on(handle.bounds, FOLLOW_BUTTONS + AVATARS)


def test_the_prefixed_account_is_refused():
    screen = _Screen(USERS_TAB_43_1_4)
    found = [el for sel in SEARCH_SELECTORS.user_result_selectors_for_username("demo_media")
             for el in screen.xpath(sel).all()]
    assert [el.text for el in found] == ["‎⁨demo_media⁩"]
