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

Les écrans sont de vraies captures anonymisées, en français, lues comme `d.xpath()` les lit
(`parse_ui_dump`) : TikTok 43.1.4 (Pixel 3a : un compte média certifié, notre propre profil) et
47.0.3 (Pixel 6a : le même compte certifié, un compte sans bio, notre propre profil). Le PIÈGE
mesuré y est réel : sur 47.0.3, notre propre profil porte le marqueur « Compte non recommandé »,
dont l'icône a le MÊME id (`t3x`) que le badge vérifié du compte certifié, sous un autre parent
(sur 46.6.3, c'était `ss1`). Une ancre qui ne sait pas la refuser n'est pas un indicateur.
"""

import pytest

from taktik.core.shared.actions.utils import parse_count
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS
from unit.paths import CORE

FIXTURES = CORE / "tests/unit/social_media/tiktok/fixtures"

#: Un compte média certifié, sa bio courte (43.1.4 et 47.0.3).
CERTIFIED = {"43.1.4": "tt4314_fr_profile.xml", "47.0.3": "tt4703_fr_profile_followed.xml"}
#: Notre propre profil, avec sa bio (43.1.4) ; avec sa bio et « Compte non recommandé » (47.0.3).
OWN = {"43.1.4": "tt4314_fr_own_profile.xml", "47.0.3": "tt4703_fr_own_profile_not_recommended.xml"}
#: Un compte sans bio, ni certifié (47.0.3).
PLAIN = "tt47_fr_profile_follows_us_no_message_entry.xml"


class _Screen:
    """Un vrai écran, interrogé par les sélecteurs RÉELS du catalogue, sur l'arbre de `d.xpath()`."""

    def __init__(self, name: str, xml: str = ""):
        self.xml = xml or (FIXTURES / name).read_text(encoding="utf-8")
        self._tree = parse_ui_dump(self.xml)

    def first_text(self, selectors):
        for selector in selectors:
            for node in self._tree.xpath(selector):
                text = (node.get("text") or "").strip()
                if text:
                    return text
        return ""

    def matches(self, selectors):
        return any(self._tree.xpath(selector) for selector in selectors)

    def nodes(self, xpath):
        return self._tree.xpath(xpath)


@pytest.fixture(autouse=True)
def _french_phone():
    """Les trois téléphones sont fr-FR, et c'est dans ce mode que les deux sondes étaient mortes.

    Lire avec la langue INCONNUE prendrait l'union des langues et masquerait exactement le bug.
    """
    set_active_locale("fr")
    yield
    set_active_locale(None)


# --- la bio -----------------------------------------------------------------------------------


@pytest.mark.parametrize("version, bio", [
    ("43.1.4", "name_3 name_4 name_5 name_6 .. .. .."),
    ("47.0.3", "name_12 name_13 name_14 name_15 .. .. .."),
])
def test_a_short_bio_is_not_lost(version, bio):
    """La règle de longueur jetait tout ce qui faisait 40 caractères ou moins, sans rien dire.

    Sur TikTok la bio est plafonnée à 80 caractères : la règle ne gardait donc pas les cas rares,
    elle gardait la minorité. La bio du compte certifié en fait 36 et 40."""
    assert len(bio) <= 40
    assert _Screen(CERTIFIED[version]).first_text(PROFILE_SELECTORS.bio_text) == bio


def test_an_account_without_a_bio_reads_as_empty():
    """Le deuxième versant : une ancre qui trouve toujours quelque chose n'indique rien. Le
    compte a un nom affiché et « Suivre en retour », aucune bio."""
    screen = _Screen(PLAIN)
    assert screen.nodes('//*[@text="Suivre en retour"]')
    assert screen.first_text(PROFILE_SELECTORS.bio_text) == ""


@pytest.mark.parametrize("version, bio", [
    ("43.1.4", ".. name_9 name_10 name_11 les plus name_12 & les plus name_13, name_14 name_15 name_16"),
    ("47.0.3", "name_16 comment name_17 name_18 name_19 name_20"),
])
def test_our_own_profile_gives_its_bio_not_an_action_button(version, bio):
    """« Le premier bouton après le handle » ramenait un libellé d'action sur notre propre
    profil. Sur le vrai profil, des boutons sans texte (photo, story, un bouton vide en 43.1.4)
    suivent le handle avant la bio : c'est la bio qui est lue."""
    assert _Screen(OWN[version]).first_text(PROFILE_SELECTORS.bio_text) == bio


#: The unlabelled button that follows the handle on our own 43.1.4 profile.
UNLABELLED_BUTTON = 'NAF="true" index="0" text="" resource-id="" class="android.widget.Button"'


def test_a_labelled_action_button_after_the_handle_is_not_a_bio():
    """On 46.6.3 our own profile carried an « Edit » button between the handle and the bio, and
    « the first button after the handle » recorded it as the biography. No phone of the bench runs
    46.6.3: the real 43.1.4 own profile, its unlabelled button after the handle given that label
    (derived), keeps giving the bio, because only the bio can be copied."""
    real = _Screen(OWN["43.1.4"]).xml
    assert real.count(UNLABELLED_BUTTON) == 1
    labelled = UNLABELLED_BUTTON.replace('text=""', 'text="Edit"')
    screen = _Screen(OWN["43.1.4"], xml=real.replace(UNLABELLED_BUTTON, labelled))
    assert screen.nodes('//android.widget.Button[@text="Edit"]')
    assert screen.first_text(PROFILE_SELECTORS.bio_text).startswith(".. name_9 name_10")


@pytest.mark.parametrize("name", [CERTIFIED["43.1.4"], OWN["47.0.3"], PLAIN])
def test_what_separates_the_bio_from_a_button_is_that_it_can_be_copied(name):
    """La bio est du texte sélectionnable (`long-clickable`), un bouton d'action ne l'est pas.
    C'est le seul attribut qui les distingue : ni l'un ni l'autre ne porte de resource-id. Sur
    chaque vrai profil, le texte lu est celui du seul bouton copiable, ou rien."""
    screen = _Screen(name)
    copiable = [n.get("text") for n in screen.nodes('//android.widget.Button[@long-clickable="true"]')
                if (n.get("text") or "").strip()]
    assert screen.first_text(PROFILE_SELECTORS.bio_text) == (copiable[0] if copiable else "")
    assert screen.nodes('//android.widget.Button[@long-clickable="false"][string-length(@text) > 0]')


# --- le badge vérifié -------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["43.1.4", "47.0.3"])
def test_a_verified_account_is_seen_as_verified(version):
    """Le badge est une petite ImageView posée en frère immédiat du handle. Sur 47.0.3 (comme sur
    46.6.3), rien sur l'écran ne DIT « vérifié » : aucun nœud ne porte le mot. Sur 43.1.4, la
    description du badge le dit (« <nom> vérifié ») : l'ancre structurelle lit les deux."""
    screen = _Screen(CERTIFIED[version])
    says_it = [n.get("content-desc") for n in screen.nodes('//*[contains(@content-desc, "vérifié")]')]
    assert says_it == ({"43.1.4": ["name_2 vérifié"], "47.0.3": []}[version])
    assert screen.matches(PROFILE_SELECTORS.verified_badge)


@pytest.mark.parametrize("name", [PLAIN, OWN["43.1.4"]])
def test_an_ordinary_account_is_not_called_verified(name):
    assert not _Screen(name).matches(PROFILE_SELECTORS.verified_badge)


def test_the_not_recommended_icon_is_refused():
    """Le piège mesuré : notre compte (47.0.3) porte la MÊME icône `t3x` que le badge du compte
    certifié, pour le marqueur « Compte non recommandé », sous un autre parent. S'ancrer sur
    l'id d'icône aurait déclaré ce compte vérifié."""
    marked = _Screen(OWN["47.0.3"])
    certified = _Screen(CERTIFIED["47.0.3"])
    icon = '//android.widget.ImageView[contains(@resource-id, ":id/t3x")]'
    assert marked.nodes('//*[@text="Compte non recommandé"]')
    assert marked.nodes(icon) and certified.nodes(icon)
    assert not marked.matches(PROFILE_SELECTORS.verified_badge)


def test_the_badge_anchor_does_not_depend_on_the_language():
    """Une ancre structurelle ne doit pas changer de réponse quand la langue change — c'est tout
    l'intérêt de ne pas l'écrire avec un mot."""
    for locale in ("fr", "en", None):
        set_active_locale(locale)
        assert _Screen(CERTIFIED["43.1.4"]).matches(PROFILE_SELECTORS.verified_badge), locale
        assert not _Screen(OWN["47.0.3"]).matches(PROFILE_SELECTORS.verified_badge), locale


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
