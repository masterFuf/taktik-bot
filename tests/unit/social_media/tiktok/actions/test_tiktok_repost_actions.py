"""Republier une vidéo, et savoir si elle l'est déjà.

Tout ce qui est verrouillé ici vient d'un écran, le 2026-08-30, sur 46.6.3 — et surtout d'une
erreur : la première version lisait l'écran qui suit le tap comme une **confirmation**. Ce n'en est
pas une. Le repost tombe au tap, et ce qui suit est facultatif — au point de ne pas exister du tout
selon la langue :

| Situation                     | Ce que TikTok montre après le tap        |
|-------------------------------|------------------------------------------|
| Première fois, en français    | « Elle apparaîtra sur ton profil » + OK   |
| Fois suivantes, en français   | Composeur de note, `Ajouter` désactivé    |
| En anglais                    | **rien** — la feuille se referme          |

Trois comportements pour une action. C'est la raison d'être de la règle qui traverse ce fichier :
c'est **l'état** qui fait foi, jamais l'écran ni le tap.
"""

import pytest

from taktik.core.social_media.tiktok.actions.atomic.interaction.repost_actions import RepostActions


class _SilentLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)

    def success(self, message):
        pass

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _Node:
    def __init__(self, on_click=None):
        self.text = ""
        self._on_click = on_click

    def click(self):
        if self._on_click:
            self._on_click()


class _Result:
    def __init__(self, nodes):
        self._nodes = nodes

    def all(self):
        return self._nodes

    @property
    def exists(self):
        return bool(self._nodes)

    def click(self):
        if self._nodes:
            self._nodes[0].click()


class _Video:
    """Un écran vidéo dont la feuille de partage et l'état de republication sont indépendants."""

    def __init__(self, *, sheet_opens=True, reposted=False, repost_applies=True):
        self.sheet_open = False
        self.sheet_opens = sheet_opens
        self.reposted = reposted
        self.repost_applies = repost_applies
        self.taps = []

    def _repost(self):
        self.taps.append("repost")
        # Ce que le tap change VRAIMENT. Un écran qui ne l'applique pas ressemble exactement à un
        # écran qui l'applique, du point de vue de l'appelant — d'où ce levier.
        if self.repost_applies:
            self.reposted = True

    def xpath(self, selector):
        if "fxs" in selector or "tv_title" in selector:          # l'indicateur de feuille
            return _Result([_Node()] if self.sheet_open else [])
        if "Partager" in selector or "Share" in selector:         # le bouton qui ouvre la feuille
            return _Result([_Node(on_click=self._open_sheet)])
        if not self.sheet_open:
            return _Result([])
        if "republication" in selector or "Delete repost" in selector:
            return _Result([_Node(on_click=self._undo)] if self.reposted else [])
        if "Republier" in selector or "Repost" in selector:
            return _Result([] if self.reposted else [_Node(on_click=self._repost)])
        if "OK" in selector or "Fermer" in selector or "Close" in selector:
            return _Result([_Node()])
        return _Result([])

    def _open_sheet(self):
        if self.sheet_opens:
            self.sheet_open = True

    def _undo(self):
        self.taps.append("undo")
        self.reposted = False

    def press(self, _key):
        self.sheet_open = False


def _actions(video) -> RepostActions:
    actions = RepostActions.__new__(RepostActions)
    actions.device = video
    actions.logger = _SilentLogger()
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import (
        VIDEO_ENGAGEMENT_SELECTORS,
        VIDEO_SHARE_SELECTORS,
    )
    actions.share_selectors = VIDEO_SHARE_SELECTORS
    actions.engagement_selectors = VIDEO_ENGAGEMENT_SELECTORS
    actions._find_and_click = lambda selectors, timeout=2: _click_first(video, selectors)
    actions._human_like_delay = lambda *_a, **_k: None
    return actions


def _click_first(video, selectors):
    for selector in selectors:
        found = video.xpath(selector).all()
        if found:
            found[0].click()
            return True
    return False


# --- lire l'état ---------------------------------------------------------------------------------


def test_a_video_that_is_reposted_reads_as_reposted():
    assert _actions(_Video(reposted=True)).is_reposted() is True


def test_a_video_that_is_not_reposted_reads_as_not_reposted():
    """La moitié qui sait dire non. Une ancre qui répond toujours oui ne protège de rien."""
    assert _actions(_Video(reposted=False)).is_reposted() is False


def test_an_unreadable_sheet_is_none_and_not_false():
    """« On n'a pas pu regarder » et « ce n'est pas republié » mènent à des actions opposées :
    les confondre fait republier la même vidéo à chaque passage."""
    assert _actions(_Video(sheet_opens=False)).is_reposted() is None


# --- republier -----------------------------------------------------------------------------------


def test_reposting_reports_the_state_not_the_tap():
    video = _Video(reposted=False)
    assert _actions(video).repost_video() is True
    assert video.reposted is True


def test_a_tap_that_did_not_apply_is_a_failure():
    """Le piège central. Le tap réussit toujours ; seul l'état dit si la vidéo est sur le profil."""
    video = _Video(reposted=False, repost_applies=False)

    assert _actions(video).repost_video() is False
    assert video.taps == ["repost"]


def test_an_already_reposted_video_is_a_success_without_a_second_tap():
    """Refuser ici pousserait une boucle de reprise à ne rien faire pour toujours ; retaper
    republierait ce qui est déjà republié."""
    video = _Video(reposted=True)

    assert _actions(video).repost_video() is True
    assert video.taps == []


def test_nothing_is_attempted_when_the_sheet_will_not_open():
    video = _Video(sheet_opens=False)

    assert _actions(video).repost_video() is False
    assert video.taps == []


# --- retirer -------------------------------------------------------------------------------------


def test_undoing_a_repost_reports_the_state():
    video = _Video(reposted=True)

    assert _actions(video).undo_repost() is True
    assert video.reposted is False


def test_undoing_what_was_never_reposted_is_a_success_and_taps_nothing():
    video = _Video(reposted=False)

    assert _actions(video).undo_repost() is True
    assert video.taps == []
