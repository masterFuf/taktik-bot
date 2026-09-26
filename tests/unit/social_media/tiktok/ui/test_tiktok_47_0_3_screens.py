"""TikTok 47.0.3 sur des écrans réels : la rangée d'un résultat de recherche, les compteurs du
profil, l'entrée « Message ».

Relevés sur un Pixel 6a (TikTok 47.0.3, en français), puis anonymisés : structure, ids et bornes
d'origine ; pseudos, noms et nombres fictifs ; tout autre texte de tiers vidé.

Ce qu'un run Abonnés appelait « compteur d'abonnés introuvable » était un profil jamais ouvert. Le
tap sur le résultat de recherche était échantillonné sur toute la rangée, qui fait la largeur de
l'écran et contient le bouton « Suivis » / « Suivre » ; il est tombé sur ce bouton, et l'écran est
resté sur les résultats. Le compteur, lui, est bien là en 47.0.3. Désormais le tap vise le pseudo.

Évalué par le moteur `d.xpath()` de uiautomator2, comme sur le téléphone.
"""

import random

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.behavior.tap import sample_tap_point
from taktik.core.social_media.tiktok.actions.core.utils import first_matching, parse_count
from taktik.core.social_media.tiktok.ui.labels import classify_profile_stat_label
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS


# Onglet Utilisateurs : les deux premières rangées. Profils : l'en-tête, d'un compte suivi puis
# d'un compte qui nous suit sans être suivi.
USERS_TAB = """
<node class="androidx.recyclerview.widget.RecyclerView" resource-id="" clickable="false" bounds="[0,373][1080,2337]" text="" content-desc="">
  <node text="" resource-id="" class="android.widget.Button" content-desc="" clickable="true" bounds="[0,394][1080,589]">
    <node text="" resource-id="com.zhiliaoapp.musically:id/ve6" class="android.widget.RelativeLayout" content-desc="" clickable="true" bounds="[0,394][1080,589]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/ij6" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[29,402][208,581]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/iom" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[29,402][208,581]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/lwz" class="X.05wq" content-desc="" clickable="true" bounds="[45,418][192,565]"/>
        </node>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/mzh" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[226,424][775,558]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/o_m" class="android.view.ViewGroup" content-desc="" clickable="false" bounds="[226,424][775,474]">
          <node text="\u200e\u2068demo_media\u2069" resource-id="com.zhiliaoapp.musically:id/tv_username" class="android.widget.TextView" content-desc="" clickable="false" bounds="[226,424][361,474]"/>
          <node text="" resource-id="com.zhiliaoapp.musically:id/zf0" class="android.widget.ImageView" content-desc="" clickable="false" bounds="[366,431][403,468]"/>
        </node>
        <node text="Demo Media" resource-id="com.zhiliaoapp.musically:id/tv_aweme_id" class="android.widget.TextView" content-desc="" clickable="false" bounds="[226,474][775,516]"/>
        <node text="1,2\xa0M\xa0followers · 10\xa0M j'aime" resource-id="com.zhiliaoapp.musically:id/tv_desc" class="android.widget.TextView" content-desc="" clickable="false" bounds="[226,516][734,558]"/>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/yr4" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[807,447][1038,531]">
        <node text="Suivis" resource-id="com.zhiliaoapp.musically:id/u9f" class="android.widget.Button" content-desc="" clickable="true" bounds="[807,447][1038,531]"/>
      </node>
    </node>
  </node>
  <node text="" resource-id="" class="android.widget.Button" content-desc="" clickable="true" bounds="[0,589][1080,784]">
    <node text="" resource-id="com.zhiliaoapp.musically:id/ve6" class="android.widget.RelativeLayout" content-desc="" clickable="true" bounds="[0,589][1080,784]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/ij6" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[29,597][208,776]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/iom" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[29,597][208,776]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/lwz" class="X.05wq" content-desc="" clickable="true" bounds="[45,613][192,760]"/>
        </node>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/mzh" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[226,619][775,753]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/o_m" class="android.view.ViewGroup" content-desc="" clickable="false" bounds="[226,619][775,669]">
          <node text="\u200e\u2068demo_media_fan\u2069" resource-id="com.zhiliaoapp.musically:id/tv_username" class="android.widget.TextView" content-desc="" clickable="false" bounds="[226,619][565,669]"/>
        </node>
        <node text="Demo Fan" resource-id="com.zhiliaoapp.musically:id/tv_aweme_id" class="android.widget.TextView" content-desc="" clickable="false" bounds="[226,669][775,711]"/>
        <node text="12\xa0followers · 40 j'aime" resource-id="com.zhiliaoapp.musically:id/tv_desc" class="android.widget.TextView" content-desc="" clickable="false" bounds="[226,711][721,753]"/>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/yr4" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[807,642][1038,726]">
        <node text="Suivre" resource-id="com.zhiliaoapp.musically:id/u9f" class="android.widget.Button" content-desc="" clickable="true" bounds="[807,642][1038,726]"/>
      </node>
    </node>
  </node>
</node>"""

FOLLOWED_PROFILE = """
<node text="" resource-id="com.zhiliaoapp.musically:id/t82" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[0,269][1080,910]">
  <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[0,269][1080,563]">
    <node text="" resource-id="com.zhiliaoapp.musically:id/t5o" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,269][1080,563]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/t5q" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,275][754,542]">
        <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,275][335,375]">
          <node text="Demo Media" resource-id="" class="android.widget.Button" content-desc="" clickable="true" bounds="[42,275][335,375]"/>
        </node>
        <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,380][217,419]">
          <node text="@demo_media" resource-id="com.zhiliaoapp.musically:id/t3y" class="android.widget.Button" content-desc="" clickable="true" bounds="[42,380][186,419]"/>
          <node text="" resource-id="com.zhiliaoapp.musically:id/t3x" class="android.widget.ImageView" content-desc="" clickable="true" bounds="[191,386][217,412]"/>
        </node>
        <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,456][754,542]">
          <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[42,456][129,542]">
            <node text="12" resource-id="com.zhiliaoapp.musically:id/t8_" class="android.widget.TextView" content-desc="" clickable="false" bounds="[42,456][129,506]"/>
            <node text="Suivis" resource-id="com.zhiliaoapp.musically:id/t89" class="android.widget.TextView" content-desc="" clickable="false" bounds="[42,503][129,542]"/>
          </node>
          <node text="" resource-id="" class="android.view.ViewGroup" content-desc="" clickable="true" bounds="[129,456][394,542]">
            <node text="1,2\xa0M" resource-id="com.zhiliaoapp.musically:id/t8_" class="android.widget.TextView" content-desc="" clickable="false" bounds="[192,456][298,503]"/>
            <node text="Followers" resource-id="com.zhiliaoapp.musically:id/t89" class="android.widget.TextView" content-desc="" clickable="false" bounds="[192,503][331,542]"/>
          </node>
          <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[394,456][538,542]">
            <node text="10\xa0M" resource-id="com.zhiliaoapp.musically:id/t8_" class="android.widget.TextView" content-desc="" clickable="false" bounds="[394,456][538,506]"/>
            <node text="J'aime" resource-id="com.zhiliaoapp.musically:id/t89" class="android.widget.TextView" content-desc="" clickable="false" bounds="[394,503][538,542]"/>
          </node>
        </node>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/t4l" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[744,269][1080,563]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/bmh" class="android.widget.FrameLayout" content-desc="" clickable="true" bounds="[744,269][1080,563]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/bni" class="android.widget.RelativeLayout" content-desc="" clickable="false" bounds="[744,269][1080,563]"/>
        </node>
      </node>
    </node>
  </node>
  <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,584][1038,689]">
    <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[42,584][649,689]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/fmk" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,584][649,689]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/fmj" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[214,584][477,689]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/fmr" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[267,584][435,689]">
            <node text="Message" resource-id="com.zhiliaoapp.musically:id/fmp" class="android.widget.TextView" content-desc="" clickable="false" bounds="[267,584][435,689]"/>
          </node>
        </node>
      </node>
    </node>
    <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[670,584][912,689]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/fmk" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[670,584][912,689]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/fmj" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[670,584][912,689]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/fmr" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[723,584][870,689]">
            <node text="Suivis " resource-id="com.zhiliaoapp.musically:id/fmp" class="android.widget.TextView" content-desc="" clickable="false" bounds="[723,584][870,689]"/>
          </node>
        </node>
      </node>
    </node>
    <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[933,584][1038,689]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/fmk" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[933,584][1038,689]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/fmj" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[933,584][1038,689]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/fmo" class="android.widget.RelativeLayout" content-desc="" clickable="false" bounds="[933,584][1038,689]">
            <node text="" resource-id="com.zhiliaoapp.musically:id/fml" class="android.widget.ImageView" content-desc="" clickable="true" bounds="[933,584][1038,689]"/>
          </node>
        </node>
      </node>
    </node>
  </node>
  <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,700][1038,802]">
    <node text="" resource-id="" class="android.widget.FrameLayout" content-desc="" clickable="true" bounds="[42,705][1038,749]">
      <node text="" resource-id="" class="android.widget.Button" content-desc="" clickable="true" bounds="[42,705][442,749]"/>
    </node>
    <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[42,749][1038,802]"/>
  </node>
  <node text="" resource-id="" class="android.widget.HorizontalScrollView" content-desc="" clickable="false" bounds="[0,834][420,910]">
    <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[0,834][420,910]">
      <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[42,834][357,910]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/al_" class="android.widget.ImageView" content-desc="" clickable="false" bounds="[66,856][98,888]"/>
        <node text="" resource-id="com.zhiliaoapp.musically:id/alb" class="android.widget.TextView" content-desc="" clickable="false" bounds="[109,850][333,894]"/>
      </node>
    </node>
  </node>
</node>"""

FOLLOWER_PROFILE = """
<node text="" resource-id="com.zhiliaoapp.musically:id/t82" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[0,269][1080,689]">
  <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[0,269][1080,563]">
    <node text="" resource-id="com.zhiliaoapp.musically:id/t5o" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,269][1080,563]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/t5q" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,275][754,542]">
        <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,275][520,375]">
          <node text="Demo Follower" resource-id="" class="android.widget.Button" content-desc="" clickable="true" bounds="[42,275][520,375]"/>
        </node>
        <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,380][239,419]">
          <node text="@demo_follower" resource-id="com.zhiliaoapp.musically:id/t3y" class="android.widget.Button" content-desc="" clickable="true" bounds="[42,380][239,419]"/>
        </node>
        <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,456][754,542]">
          <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[42,456][129,542]">
            <node text="12" resource-id="com.zhiliaoapp.musically:id/t8_" class="android.widget.TextView" content-desc="" clickable="false" bounds="[42,456][129,506]"/>
            <node text="Suivis" resource-id="com.zhiliaoapp.musically:id/t89" class="android.widget.TextView" content-desc="" clickable="false" bounds="[42,503][129,542]"/>
          </node>
          <node text="" resource-id="" class="android.view.ViewGroup" content-desc="" clickable="true" bounds="[129,456][379,542]">
            <node text="1,2\xa0M" resource-id="com.zhiliaoapp.musically:id/t8_" class="android.widget.TextView" content-desc="" clickable="false" bounds="[192,456][210,503]"/>
            <node text="Follower" resource-id="com.zhiliaoapp.musically:id/t89" class="android.widget.TextView" content-desc="" clickable="false" bounds="[192,503][316,542]"/>
          </node>
          <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[379,456][474,542]">
            <node text="10\xa0M" resource-id="com.zhiliaoapp.musically:id/t8_" class="android.widget.TextView" content-desc="" clickable="false" bounds="[379,456][474,506]"/>
            <node text="J'aime" resource-id="com.zhiliaoapp.musically:id/t89" class="android.widget.TextView" content-desc="" clickable="false" bounds="[379,503][474,542]"/>
          </node>
        </node>
      </node>
      <node text="" resource-id="com.zhiliaoapp.musically:id/t4l" class="android.widget.FrameLayout" content-desc="" clickable="false" bounds="[744,269][1080,563]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/bmh" class="android.widget.FrameLayout" content-desc="" clickable="true" bounds="[744,269][1080,563]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/bni" class="android.widget.RelativeLayout" content-desc="" clickable="false" bounds="[744,269][1080,563]"/>
        </node>
      </node>
    </node>
  </node>
  <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,584][1038,689]">
    <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[42,584][912,689]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/fmk" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,584][912,689]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/fmj" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,584][912,689]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/fmr" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[42,584][912,689]">
            <node text="Suivre en retour" resource-id="com.zhiliaoapp.musically:id/fmp" class="android.widget.TextView" content-desc="" clickable="false" bounds="[42,584][912,689]"/>
          </node>
        </node>
      </node>
    </node>
    <node text="" resource-id="" class="android.widget.LinearLayout" content-desc="" clickable="true" bounds="[933,584][1038,689]">
      <node text="" resource-id="com.zhiliaoapp.musically:id/fmk" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[933,584][1038,689]">
        <node text="" resource-id="com.zhiliaoapp.musically:id/fmj" class="android.widget.LinearLayout" content-desc="" clickable="false" bounds="[933,584][1038,689]">
          <node text="" resource-id="com.zhiliaoapp.musically:id/fmo" class="android.widget.RelativeLayout" content-desc="" clickable="false" bounds="[933,584][1038,689]">
            <node text="" resource-id="com.zhiliaoapp.musically:id/fml" class="android.widget.ImageView" content-desc="" clickable="true" bounds="[933,584][1038,689]"/>
          </node>
        </node>
      </node>
    </node>
  </node>
</node>"""


class _Screen:
    wait_timeout = 0.0

    def __init__(self, xml):
        self._xml = f'<hierarchy rotation="0">{xml}</hierarchy>'
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return self._xml


def _tapped(screen, selectors):
    """Ce que `_find_and_click` taperait : le premier sélecteur qui existe, son premier nœud."""
    for selector in selectors:
        found = screen.xpath(selector)
        if found.exists:
            return found.get(timeout=0)
    return None


def _lands_on_a_follow_button(bounds, samples=3000):
    """Un tap humain échantillonné dans `bounds` tombe-t-il jamais sur un bouton Suivre/Suivis ?"""
    buttons = [el.bounds for el in _Screen(USERS_TAB).xpath('//*[contains(@resource-id, ":id/u9f")]').all()]
    rng = random.Random(0)
    for _ in range(samples):
        x, y = sample_tap_point(bounds, rng=rng)
        if any(left <= x <= right and top <= y <= bottom for left, top, right, bottom in buttons):
            return True
    return False


def _resource(element):
    return element.attrib.get("resource-id", "").rsplit("/", 1)[-1]


@pytest.fixture(autouse=True)
def _french():
    previous = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(previous)


@pytest.fixture
def on_47_0_3():
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


# --- La rangée d'un résultat de recherche -----------------------------------------------------


def test_the_row_is_as_wide_as_the_screen_and_holds_the_follow_button():
    """Pourquoi le tap ne vise plus la rangée : échantillonné sur elle, il atteint le bouton."""
    row = _tapped(_Screen(USERS_TAB), [
        '//*[contains(@resource-id, ":id/tv_username")]/ancestor::*[@clickable="true"][1]',
    ])
    assert row.bounds[0] == 0 and row.bounds[2] == 1080
    assert _lands_on_a_follow_button(row.bounds)


def test_the_named_row_is_tapped_on_its_handle():
    handle = _tapped(_Screen(USERS_TAB), SEARCH_SELECTORS.user_result_selectors_for_username("demo_media"))
    assert _resource(handle) == "tv_username"
    assert handle.text.endswith("⁨demo_media⁩")
    assert not _lands_on_a_follow_button(handle.bounds)


def test_the_prefixed_account_is_still_refused_on_the_real_screen():
    screen = _Screen(USERS_TAB)
    found = [el for sel in SEARCH_SELECTORS.user_result_selectors_for_username("demo_media")
             for el in screen.xpath(sel).all()]
    assert [el.text for el in found] == ["‎⁨demo_media⁩"]


@pytest.mark.parametrize("catalogue", ["first_user_result", "user_search_item"])
def test_the_followers_workflow_taps_the_first_handle(catalogue):
    handle = _tapped(_Screen(USERS_TAB), getattr(FOLLOWERS_SELECTORS, catalogue))
    assert _resource(handle) == "tv_username"
    assert handle.text.endswith("⁨demo_media⁩")
    assert not _lands_on_a_follow_button(handle.bounds)


# --- Les compteurs du profil ------------------------------------------------------------------


@pytest.mark.parametrize("xml", [FOLLOWED_PROFILE, FOLLOWER_PROFILE], ids=["followed", "follower"])
def test_the_followers_counter_is_on_the_47_0_3_profile(xml):
    """Le compteur que le run disait introuvable : présent et cliquable, sur les deux profils."""
    counter = _tapped(_Screen(xml), FOLLOWERS_SELECTORS.followers_counter)
    assert counter is not None
    assert counter.attrib.get("clickable") == "true"
    assert any((node.get("text") or "").startswith("Follower") for node in counter.elem.iter())


def test_the_baseline_stat_ids_resolve_nothing_on_47_0_3():
    screen = _Screen(FOLLOWED_PROFILE)
    for selector in PROFILE_SELECTORS._stat_value_base + PROFILE_SELECTORS._stat_label_base:
        assert not screen.xpath(selector).exists


@pytest.mark.parametrize("xml", [FOLLOWED_PROFILE, FOLLOWER_PROFILE], ids=["followed", "follower"])
def test_on_47_0_3_the_stats_are_read_by_their_ids(on_47_0_3, xml):
    screen = _Screen(xml)
    values = first_matching(screen, PROFILE_SELECTORS.stat_value)
    labels = first_matching(screen, PROFILE_SELECTORS.stat_label)

    assert [_resource(v) for v in values] == ["t8_"] * 3
    assert [_resource(label) for label in labels] == ["t89"] * 3
    read = {classify_profile_stat_label(label.text): parse_count(value.text)
            for value, label in zip(values, labels)}
    assert read == {"following": 12, "followers": 1_200_000, "likes": 10_000_000}


def test_the_stat_ids_are_not_found_on_the_search_results():
    """L'autre versant : `t8_` / `t89` ne tirent pas sur une liste de résultats."""
    apply_version_overrides("tiktok", "47.0.3")
    try:
        screen = _Screen(USERS_TAB)
        for selector in PROFILE_SELECTORS._stat_value_base + PROFILE_SELECTORS._stat_label_base:
            assert not screen.xpath(selector).exists
    finally:
        apply_version_overrides("tiktok", "43.1.4")


# --- L'entrée « Message » ---------------------------------------------------------------------


def test_the_message_button_is_found_on_a_followed_account():
    button = _tapped(_Screen(FOLLOWED_PROFILE), PROFILE_SELECTORS.message_button)
    assert button is not None and button.text == "Message"


def test_an_account_we_do_not_follow_offers_no_message_entry():
    """47.0.3, compte qui nous suit sans être suivi : « Suivre en retour » et l'icône des comptes
    suggérés, rien d'autre. Le DM à froid n'a pas d'entrée sur ce profil ; « Message button
    introuvable » y est la bonne réponse, pas un sélecteur à corriger."""
    assert _tapped(_Screen(FOLLOWER_PROFILE), PROFILE_SELECTORS.message_button) is None
