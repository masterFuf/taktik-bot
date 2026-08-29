"""Revenir au fil sans sortir de l'application.

Ce fichier affirmait auparavant `device.presses == ["back", "back", "back"]` : il verrouillait
donc le bug plutôt que le contrat. Mesuré le 2026-08-30 sur le Pixel 6a, depuis le fil, le
**deuxième** « back » atterrit déjà sur le lanceur. Trois pressions à l'aveugle quittaient donc
TikTok, l'onglet Accueil était ensuite cherché sur le lanceur, et la fonction rendait False avec
l'application fermée.

Aucun appelant ne s'arrêtait pour autant : `target_profiles` enchaînait sur
`navigate_to_user_profile`, ne trouvait pas la loupe — puisqu'il était sur le bureau Android — et
rapportait `skip_not_found` pour ses trois cibles sans avoir vu TikTok une seule fois. Followers
et Search appellent la même fonction entre deux cibles : une seule réinitialisation suffisait à
couler le reste du run.
"""

import pytest

from taktik.core.social_media.tiktok.services.navigation.reset import (
    return_to_tiktok_home,
    return_to_tiktok_shell,
)
from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NAVIGATION_SELECTORS


class _FakeXPath:
    def __init__(self, selector, device):
        self.selector = selector
        self.device = device

    @property
    def exists(self):
        return self.selector in self.device.present

    def click_exists(self, timeout):
        self.device.click_timeouts.append(timeout)
        if self.selector in self.device.present:
            self.device.clicked.append(self.selector)
            self.device.present |= set(self.device.reveals_on_click)
            return True
        return False


class _FakeScreen:
    """Un écran où l'on déclare ce qui est présent, et ce qu'un « back » ramène.

    `back_reveals` reproduit ce que fait vraiment le téléphone : sortir d'une page plein écran
    fait réapparaître la barre du bas.
    """

    def __init__(self, present=(), back_reveals=(), reveals_on_click=()):
        self.present = set(present)
        self.back_reveals = list(back_reveals)
        self.reveals_on_click = list(reveals_on_click)
        self.presses = []
        self.clicked = []
        self.click_timeouts = []

    def press(self, key):
        self.presses.append(key)
        if self.back_reveals:
            self.present |= set(self.back_reveals.pop(0))

    def xpath(self, selector):
        return _FakeXPath(selector, self)


SHELL = NAVIGATION_SELECTORS.profile_tab[0]
HOME = NAVIGATION_SELECTORS.home_tab[0]
HOME_SELECTED = NAVIGATION_SELECTORS.home_tab_selected[0]


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.social_media.tiktok.services.navigation.reset.time.sleep",
        lambda _seconds: None,
    )


# --- ne pas sortir de l'application -----------------------------------------------------------


def test_from_the_feed_it_presses_nothing_at_all():
    """Le cas qui fermait l'app. Depuis le fil, la barre du bas est déjà là : il n'y a rien à
    quitter, et le deuxième « back » aurait atterri sur le lanceur."""
    screen = _FakeScreen(present={SHELL, HOME, HOME_SELECTED})

    assert return_to_tiktok_home(screen)
    assert screen.presses == []


def test_from_a_visited_profile_it_backs_out_exactly_once():
    """Un profil visité est une page plein écran sans barre du bas : un seul « back » suffit, et
    un deuxième serait déjà de trop."""
    screen = _FakeScreen(present=set(), back_reveals=[{SHELL, HOME, HOME_SELECTED}])

    assert return_to_tiktok_home(screen)
    assert screen.presses == ["back"]


def test_it_refuses_to_click_when_the_shell_was_never_reached():
    """Sans la barre du bas, taper « Accueil » ne tape rien — et l'appelant lit ça comme
    « l'onglet a disparu » au lieu de « on n'est pas là où les onglets existent »."""
    screen = _FakeScreen(present=set())

    assert not return_to_tiktok_home(screen, back_presses=2)
    assert screen.clicked == []


# --- vérifier l'arrivée, pas le clic ----------------------------------------------------------


def test_a_tab_that_swallows_the_tap_is_not_an_arrival():
    """L'onglet est présent, le clic « réussit », et la sélection ne bouge pas : c'est ce que fait
    une barre du bas pendant qu'une vidéo est en transition."""
    screen = _FakeScreen(present={SHELL, HOME})  # HOME_SELECTED jamais atteint

    assert not return_to_tiktok_home(screen)
    assert screen.clicked == [HOME]


def test_a_real_arrival_is_reported_as_one():
    screen = _FakeScreen(present={SHELL, HOME}, reveals_on_click=[HOME_SELECTED])

    assert return_to_tiktok_home(screen)
    assert screen.clicked == [HOME]


def test_being_already_on_home_costs_no_click():
    screen = _FakeScreen(present={SHELL, HOME, HOME_SELECTED})

    assert return_to_tiktok_home(screen)
    assert screen.clicked == []


# --- le retour au shell, isolément ------------------------------------------------------------


def test_the_shell_reset_is_a_no_op_when_the_bar_is_there():
    screen = _FakeScreen(present={SHELL})

    assert return_to_tiktok_shell(screen)
    assert screen.presses == []


def test_the_shell_reset_gives_up_rather_than_pressing_forever():
    screen = _FakeScreen(present=set())

    assert not return_to_tiktok_shell(screen, max_back_presses=3)
    assert screen.presses == ["back", "back", "back"]
