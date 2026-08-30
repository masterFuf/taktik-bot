"""Ce que le composeur affiche n'est pas ce qu'on y a tapé.

`_focus_and_type` confirmait son propre travail par une **égalité exacte** entre le texte envoyé
et le texte relu dans le dump XML. Or uiautomator2 sérialise la hiérarchie via
`AccessibilityNodeInfoDumper` d'AOSP, dont `stripInvalidXMLChars` parcourt les unités UTF-16 et
remplace chaque unité illégale par un point : un emoji astral, qui est une PAIRE de surrogates,
revient donc en exactement deux points.

Mesuré sur appareil le 2026-08-30 : `Bien vu 😂 vraiment` tapé, `Bien vu .. vraiment` relu —
U+1F602 remplacé par U+002E U+002E, rien d'autre n'a bougé.

Les deux sens étaient cassés, et en sens opposés :

- à la **frappe**, l'égalité ne pouvait jamais tenir, donc `_focus_and_type` rendait False sur un
  commentaire qu'il venait de taper correctement — **sans journaliser**, ce chemin-là étant muet.
  Un commentaire IA porte presque toujours un emoji : ils partaient tous en brouillon abandonné
  pendant que le run rapportait zéro commentaire ;
- à l'**envoi**, le même écart se lit « le composeur s'est vidé », donc un commentaire resté dans
  le champ aurait été enregistré comme publié.

C'est la même cicatrice que `Neydi..`, `Allocin(gl)és` ou `lena...situations` dans les captures :
des emoji devenus des points.
"""

import pytest

from taktik.core.shared.text import as_xml_dumped, text_lost_emoji


# --- la projection --------------------------------------------------------------------------


@pytest.mark.parametrize("typed,dumped", [
    ("Bien vu 😂 vraiment", "Bien vu .. vraiment"),      # mesuré sur appareil
    ("😂", ".."),
    ("😂😂", "...."),                                     # deux points PAR emoji, pas par texte
    ("sans emoji", "sans emoji"),
    ("", ""),
])
def test_an_astral_character_becomes_exactly_two_dots(typed, dumped):
    assert as_xml_dumped(typed) == dumped


@pytest.mark.parametrize("text", [
    "La vérité sur mon business ⤵️",   # U+2935 + sélecteur de variation : BMP, survit
    "cœur ♥ nuage ☁ puce •",
    "accents: éàüçñ",
])
def test_everything_inside_the_bmp_survives_untouched(text):
    """La règle n'est pas « les symboles disparaissent » : une unité UTF-16 légale passe. Croire
    l'inverse ferait rejeter des textes parfaitement relus."""
    assert as_xml_dumped(text) == text


def test_the_projection_agrees_with_the_detector():
    """`text_lost_emoji` répond « ce texte a été abîmé ? », la projection répond « que lira-t-on
    si j'écris ceci ? ». Les deux décrivent la même cicatrice et doivent se rejoindre."""
    assert text_lost_emoji(as_xml_dumped("Bravo 😂"))
    assert not text_lost_emoji(as_xml_dumped("Bravo"))


# --- la vérification du composeur -------------------------------------------------------------


class _Element:
    def __init__(self, text):
        self.text = text


class _Composer:
    """Un device dont le champ de commentaire renvoie ce que le DUMP montrerait."""

    def __init__(self, shown):
        self.shown = shown

    def xpath(self, selector):
        shown = self.shown

        class _Query:
            @staticmethod
            def all():
                return [_Element(shown)] if shown is not None else []

        return _Query()


def _actions(shown):
    from taktik.core.social_media.tiktok.actions.atomic.comment_actions import CommentActions

    actions = CommentActions.__new__(CommentActions)
    actions.device = _Composer(shown)
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import COMMENT_SELECTORS

    actions.comment_selectors = COMMENT_SELECTORS
    return actions


def test_a_comment_carrying_an_emoji_is_recognised_in_the_field():
    """Le cas qui perdait tous les commentaires IA."""
    actions = _actions("Bien vu .. vraiment")

    assert actions._composer_holds("Bien vu 😂 vraiment")


def test_a_plain_comment_is_still_recognised():
    assert _actions("Trop bien")._composer_holds("Trop bien")


def test_a_different_text_is_not_taken_for_ours():
    """L'autre versant : une vérification qui dit toujours oui ne vérifie rien. C'est aussi ce
    qui décide qu'un envoi est parti — le champ doit s'être vidé, pas juste avoir changé."""
    assert not _actions("un tout autre commentaire")._composer_holds("Bien vu 😂 vraiment")


def test_an_emptied_field_does_not_hold_the_comment():
    """La preuve d'envoi : `post_comment` conclut quand le composeur ne tient plus le texte."""
    assert not _actions("")._composer_holds("Bien vu 😂 vraiment")


def test_a_field_that_cannot_be_read_is_not_a_confirmation():
    assert not _actions(None)._composer_holds("Bien vu 😂 vraiment")
