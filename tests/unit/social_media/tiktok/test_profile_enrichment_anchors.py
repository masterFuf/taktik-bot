"""Ce qu'un profil TikTok laisse vraiment lire — bio, site, vérifié, privé.

Mesuré le 2026-08-30 sur les deux versions et sur huit profils capturés. La base de production
disait la vérité avant même qu'on regarde l'écran : 783 profils TikTok, **68** biographies,
**0** site web, **0** compte vérifié. Trois causes distinctes, toutes silencieuses :

1. la bio n'était lue que par `string-length(@text) > 40` — or TikTok plafonne les bios à
   80 caractères, donc la règle jetait la majorité d'entre elles ;
2. `website` était extrait correctement puis perdu deux fois, par le mapping du workflow ET par
   le repository, dont l'INSERT ne citait pas la colonne ;
3. `is_verified` / `is_private` étaient lus avec deux mots anglais écrits en dur — sur un
   téléphone français l'entrée de locale correspondante était **vide**, ce qui n'est pas neutre :
   la liste de sélecteurs devenait vide et la réponse était « non » pour tout le monde.

Les fixtures reproduisent la hiérarchie réelle, en tenant compte du renommage de balises que fait
uiautomator2 (`<node class="X">` devient `<X>`), et gardent le PIÈGE mesuré : @marvin porte la
même icône `ss1` que le badge vérifié, pour le marqueur « Compte non recommandé », sous un autre
parent. Une ancre qui ne sait pas la refuser n'est pas un indicateur.
"""

import pytest
from lxml import etree

from taktik.core.shared.actions.utils import parse_count
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class _Screen:
    """Un arbre uiautomator2, interrogé par les sélecteurs RÉELS du catalogue."""

    def __init__(self, xml: str):
        self._tree = etree.fromstring(xml.encode("utf-8"))

    def first_text(self, selectors):
        for selector in selectors:
            for node in self._tree.xpath(selector):
                text = (node.get("text") or "").strip()
                if text:
                    return text
        return ""

    def matches(self, selectors):
        return any(self._tree.xpath(selector) for selector in selectors)


def _profile(handle, *, display="Quelqu'un", bio=None, verified=False,
             website=None, not_recommended=False, own=False):
    """Un en-tête de profil TikTok 46.6.3, dans la forme que le téléphone envoie."""
    badge = '<android.widget.ImageView resource-id="com.zhiliaoapp.musically:id/ss1" text=""/>' if verified else ""
    warning = (
        '<android.widget.LinearLayout>'
        '<android.widget.ImageView resource-id="com.zhiliaoapp.musically:id/ss1" text=""/>'
        '<android.widget.TextView text="Compte non recommandé"/>'
        '</android.widget.LinearLayout>'
    ) if not_recommended else ""
    # Sur notre PROPRE profil, TikTok pose un bouton « Edit » entre le handle et la bio. C'est
    # lui que « le premier bouton après le handle » attrapait.
    edit = '<android.widget.Button text="Edit" clickable="true" long-clickable="false"/>' if own else ""
    bio_node = (
        f'<android.widget.Button text="{bio}" clickable="true" long-clickable="true"/>'
    ) if bio else ""
    site = f'<android.widget.TextView text="{website}"/>' if website else ""
    return (
        '<hierarchy>'
        '<android.widget.FrameLayout>'
        f'<android.widget.Button text="{display}" clickable="true" long-clickable="false"/>'
        '<android.widget.LinearLayout>'
        f'<android.widget.Button resource-id="com.zhiliaoapp.musically:id/ss2" text="{handle}"'
        ' clickable="true" long-clickable="false"/>'
        f'{badge}'
        '</android.widget.LinearLayout>'
        f'{warning}'
        '<android.widget.TextView resource-id="com.zhiliaoapp.musically:id/fij" text="Message"/>'
        f'{edit}{bio_node}{site}'
        '</android.widget.FrameLayout>'
        '</hierarchy>'
    )


@pytest.fixture(autouse=True)
def _french_phone():
    """Les trois téléphones sont fr-FR, et c'est dans ce mode que les deux sondes étaient mortes.

    Lire avec la langue INCONNUE prendrait l'union des langues et masquerait exactement le bug.
    """
    set_active_locale("fr")
    yield
    set_active_locale(None)


# --- la bio -----------------------------------------------------------------------------------


@pytest.mark.parametrize("bio", [
    "Paris",                                    # 5 caractères : perdue par l'ancienne règle
    "Coach sportif",                            # 13
    "J'enseigne comment construire un business rentable",   # 50, mesurée
])
def test_a_short_bio_is_not_lost(bio):
    """La règle de longueur jetait tout ce qui faisait moins de 40 caractères, sans rien dire.

    Sur TikTok la bio est plafonnée à 80 caractères : la règle ne gardait donc pas les cas rares,
    elle gardait la minorité."""
    screen = _Screen(_profile("@quelquun", bio=bio))
    assert screen.first_text(PROFILE_SELECTORS.bio_text) == bio


def test_an_account_without_a_bio_reads_as_empty():
    """Le deuxième versant : une ancre qui trouve toujours quelque chose n'indique rien."""
    screen = _Screen(_profile("@neydi0920"))
    assert screen.first_text(PROFILE_SELECTORS.bio_text) == ""


def test_the_edit_button_of_our_own_profile_is_not_a_bio():
    """« Le premier bouton après le handle » ramenait « Edit » sur notre propre profil — un
    libellé d'action enregistré comme biographie."""
    screen = _Screen(_profile("@keo2edit", own=True, bio="SVJ, Huracan Perf, Urus Novitec"))
    assert screen.first_text(PROFILE_SELECTORS.bio_text) == "SVJ, Huracan Perf, Urus Novitec"


def test_what_separates_the_bio_from_a_button_is_that_it_can_be_copied():
    """La bio est du texte sélectionnable (`long-clickable`), un bouton d'action ne l'est pas.
    C'est le seul attribut qui les distingue : ni l'un ni l'autre ne porte de resource-id."""
    screen = _Screen(_profile("@quelquun", own=True))
    assert screen.first_text(PROFILE_SELECTORS.bio_text) == ""


# --- le badge vérifié -------------------------------------------------------------------------


def test_a_verified_account_is_seen_as_verified():
    """Rien sur l'écran ne DIT « vérifié » : le balayage de toute la hiérarchie d'un compte
    vérifié ne rend aucun nœud portant le mot, dans aucun attribut. Le badge est une petite
    ImageView sans libellé, posée en frère immédiat du handle."""
    assert _Screen(_profile("@charlidamelio", verified=True)).matches(PROFILE_SELECTORS.verified_badge)


def test_an_ordinary_account_is_not_called_verified():
    assert not _Screen(_profile("@neydi0920")).matches(PROFILE_SELECTORS.verified_badge)


def test_the_not_recommended_icon_is_refused():
    """Le piège mesuré : @marvin.ndiaye.extraits porte la MÊME icône `ss1`, pour le marqueur
    « Compte non recommandé », sous un autre parent. S'ancrer sur l'id d'icône aurait déclaré
    ce compte vérifié."""
    screen = _Screen(_profile("@marvin.ndiaye.extraits", not_recommended=True))
    assert not screen.matches(PROFILE_SELECTORS.verified_badge)


def test_the_badge_anchor_does_not_depend_on_the_language():
    """Une ancre structurelle ne doit pas changer de réponse quand la langue change — c'est tout
    l'intérêt de ne pas l'écrire avec un mot."""
    xml = _profile("@charlidamelio", verified=True)
    for locale in ("fr", "en", None):
        set_active_locale(locale)
        assert _Screen(xml).matches(PROFILE_SELECTORS.verified_badge), locale


# --- les compteurs français -------------------------------------------------------------------


@pytest.mark.parametrize("text,expected", [
    ("12,3 Md", 12_300_000_000),   # @charlidamelio, enregistrée avec 0 j'aime
    ("2,1Md", 2_100_000_000),
    ("12.3B", 12_300_000_000),     # la même chose en anglais, qui marchait déjà
    ("159,3 M", 159_300_000),
    ("166 K", 166_000),
    ("1 439", 1439),
])
def test_the_french_billion_is_a_number(text, expected):
    """« Md » commence par « M » : testé après lui, il rendait 0 — et 0 ressemble à un compte
    vide, pas à une panne. Le parseur est partagé, donc chaque profil français au-dessus du
    milliard lisait zéro sur les DEUX plateformes."""
    assert parse_count(text) == expected


def test_the_suffix_table_is_ordered_longest_first():
    """La garde qui empêche que quelqu'un rajoute un suffixe au mauvais endroit."""
    from taktik.core.shared.actions.utils import _COUNT_MULTIPLIERS

    suffixes = [suffix for suffix, _ in _COUNT_MULTIPLIERS]
    for index, suffix in enumerate(suffixes):
        for later in suffixes[index + 1:]:
            assert not suffix.endswith(later), (
                f"{later!r} est testé après {suffix!r} alors qu'il en est un suffixe"
            )
