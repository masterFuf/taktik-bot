"""Revenir à l'accueil depuis une liste d'abonnés atteinte par la recherche.

Constaté sur le Pixel 6a (TikTok 47.0.3) au passage d'une cible à la suivante d'un run Abonnés :
la liste avait été ouverte par recherche -> onglet Utilisateurs -> profil -> compteur. Trois retours
(liste, profil, puis onglet Utilisateurs -> onglet Top) épuisaient le budget, la page de résultats
n'a pas de barre du bas, et la réinitialisation abandonnait là. `open_search` ne trouvait ensuite
aucune loupe et la seconde cible n'était jamais visitée.

Sur 46.9.3, un retour depuis un onglet de résultats autre que Top ramène à Top, Top ramène à la
page du champ de recherche (clavier ouvert), et celle-ci au fil.

Le faux téléphone tient la pile de retour de l'application et répond aux vrais sélecteurs par le
moteur xpath de uiautomator2. Les écrans sont des captures réelles de 47.0.3 en français (Pixel 6a),
anonymisées : le fil, la page du champ de recherche (clavier ouvert, 2026-09-27), les résultats
Top et Utilisateurs, le profil d'une cible et sa liste d'abonnés (2026-09-26) ; et les résultats
Top de 43.1.4 (Pixel 3a) pour la base.
"""

from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.services.navigation import reset
from taktik.core.social_media.tiktok.services.navigation.reset import return_to_tiktok_home
from taktik.core.social_media.tiktok.ui.selectors.locales import active_locale, set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SEARCH_SELECTORS

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _capture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


FEED = _capture("tt4703_fr_home.xml")
SEARCH_FIELD = _capture("tt4703_fr_search_field.xml")
RESULTS_TOP = _capture("tt4703_fr_search_top_results.xml")
RESULTS_USERS = _capture("tt4703_fr_search_users.xml")
TARGET_PROFILE = _capture("tt4703_fr_profile_followed.xml")
FOLLOWERS_LIST = _capture("tt4703_fr_followers_list.xml")
RESULTS_TOP_43_1_4 = _capture("tt4314_fr_search_top_results.xml")


class _Phone:
    """The app's back stack: back pops the top screen, and nothing else moves."""

    wait_timeout = 0.0

    def __init__(self, *stack):
        self.stack = list(stack)
        self.xpath = XPathEntry(self)
        self.presses = []
        self.clicks = []

    def dump_hierarchy(self, *_a, **_k):
        return self.stack[-1]

    def press(self, key):
        self.presses.append(key)
        if key == "back" and len(self.stack) > 1:
            self.stack.pop()

    def click(self, x, y):
        self.clicks.append((x, y))


def _followers_run_stack():
    """What a Followers target leaves behind, the feed at the bottom."""
    return (FEED, SEARCH_FIELD, RESULTS_TOP, RESULTS_USERS, TARGET_PROFILE, FOLLOWERS_LIST)


@pytest.fixture(autouse=True)
def _french_no_sleep(monkeypatch):
    monkeypatch.setattr(reset.time, "sleep", lambda _seconds: None)
    previous = active_locale()
    set_active_locale("fr")
    yield
    set_active_locale(previous)


@pytest.fixture
def on_47_0_3():
    apply_version_overrides("tiktok", "47.0.3")
    yield
    apply_version_overrides("tiktok", "43.1.4")


# --- the run that stopped on the results page ---------------------------------------------------


def test_from_a_follow_list_reached_by_search_it_gets_back_to_the_feed(on_47_0_3):
    phone = _Phone(*_followers_run_stack())

    assert return_to_tiktok_home(phone)
    assert phone.stack == [FEED]
    assert phone.presses == ["back"] * 5
    assert phone.clicks == []


def test_the_search_exit_does_not_eat_the_budget_of_the_screens_before_it(on_47_0_3):
    """The follow list and the profile spend the whole ordinary budget; the results page and the
    search field page after it are backed out of on their own."""
    phone = _Phone(*_followers_run_stack())

    assert reset.return_to_tiktok_shell(phone, max_back_presses=2)
    assert phone.stack == [FEED]


def test_a_results_page_that_does_not_let_go_stops_at_the_cap_without_a_click(on_47_0_3):
    phone = _Phone(RESULTS_TOP)  # back changes nothing

    assert not return_to_tiktok_home(phone)
    assert phone.presses == ["back"] * reset.SEARCH_EXIT_BACK_PRESSES
    assert phone.clicks == []


def test_an_unknown_screen_still_gets_only_the_ordinary_budget(on_47_0_3):
    phone = _Phone(TARGET_PROFILE)  # back changes nothing, and it is no search page

    assert not return_to_tiktok_home(phone, back_presses=3)
    assert phone.presses == ["back"] * 3
    assert phone.clicks == []


# --- the selector: results pages, and nothing else ----------------------------------------------


def _is_results(xml):
    phone = _Phone(xml)
    return any(phone.xpath(s).exists for s in SEARCH_SELECTORS.results_page)


def test_on_47_0_3_the_results_page_is_recognised_on_any_tab(on_47_0_3):
    assert _is_results(RESULTS_USERS)
    assert _is_results(RESULTS_TOP)


@pytest.mark.parametrize("xml", [SEARCH_FIELD, FEED, FOLLOWERS_LIST, TARGET_PROFILE],
                         ids=["search_field", "feed", "followers_list", "target_profile"])
def test_on_47_0_3_no_other_screen_passes_for_a_results_page(on_47_0_3, xml):
    assert not _is_results(xml)


def test_the_baseline_recognises_the_43_1_4_results_page():
    assert _is_results(RESULTS_TOP_43_1_4)
    assert not _is_results(RESULTS_TOP)  # the 46.6.3 id is not the baseline's


def test_the_47_0_3_override_comes_from_the_46_6_3_entry():
    """An override key applies to its version and every later one."""
    apply_version_overrides("tiktok", "46.6.3")
    try:
        on_46_6_3 = list(SEARCH_SELECTORS.results_page)
        apply_version_overrides("tiktok", "47.0.3")
        assert SEARCH_SELECTORS.results_page == on_46_6_3
        assert any("viewpager_search" in s for s in on_46_6_3)
    finally:
        apply_version_overrides("tiktok", "43.1.4")
