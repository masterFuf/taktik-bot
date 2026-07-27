"""Zone "Suggestions" en bas de l'ecran Notifications.

Extrait ANONYMISE d'une capture reelle (18171JEC, Instagram FR, 2026-07-27). Ce que
le dump a impose, et que ce test verrouille : cette surface ne porte **aucun
resource-id** — ni sur les lignes, ni sur les champs. Une ligne ne peut donc pas se
lire comme un sous-arbre, elle se reconstitue par proximite verticale autour de son
bouton.

Le pas mesure entre deux lignes est de ~198px sur un ecran de 2400 : le test rejoue
cette geometrie exacte.
"""

import pytest

from lxml import etree

from taktik.core.social_media.instagram.actions.atomic.interaction.profile_interaction import (
    classify_follow_state,
)
from taktik.core.social_media.instagram.ui.selectors import (
    NOTIFICATION_SELECTORS,
    PROFILE_SELECTORS,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.workflows.management.notifications.suggestions_parsing import (
    find_suggestions_header_y,
    followable_suggestions,
    parse_notification_suggestions,
)


def _text(value, x1, y1, x2, y2):
    """Un TextView nu, comme les rend cette surface : pas de resource-id."""
    return (f'<node class="android.widget.TextView" text="{value}" resource-id=""'
            f' bounds="[{x1},{y1}][{x2},{y2}]"/>')


def _row(top, name, button_label, context):
    """Une ligne telle qu'elle apparait : nom, contexte, bouton, sur la meme bande."""
    return (
        _text(name, 231, top, 425, top + 46)
        + _text(context, 306, top + 64, 609, top + 103)
        + _text(button_label, 780, top - 31, 897, top + 15)
    )


def _screen(rows_xml, header="Suggestions", header_y=1383):
    return (
        "<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
        # Au-dessus de l'en-tete : de vraies notifications, qui ne doivent JAMAIS
        # etre prises pour des suggestions.
        + _text("a_liké votre publication", 231, 900, 700, 946)
        + _text(header, 44, header_y, 306, header_y + 53)
        + rows_xml
        + "</hierarchy>"
    )


def _root(xml):
    return etree.fromstring(xml.encode("utf-8"))


def _parse(xml, height=2400):
    return parse_notification_suggestions(
        _root(xml), NOTIFICATION_SELECTORS.suggestions_header_texts,
        PROFILE_SELECTORS, classify_follow_state, screen_height=height,
    )


@pytest.fixture(autouse=True)
def french_locale():
    set_active_locale('fr')
    yield
    set_active_locale(None)


def test_rows_are_rebuilt_from_geometry_without_any_resource_id():
    xml = _screen(
        _row(1701, "Spa Echo", "Suivre", "4 ami(e)s en commun")
        + _row(1899, "BrowLash Lounge", "Suivre", "2 ami(e)s en commun")
    )
    rows = _parse(xml)
    assert [row["label"] for row in rows] == ["Spa Echo", "BrowLash Lounge"]
    assert [row["social_context"] for row in rows] == [
        "4 ami(e)s en commun", "2 ami(e)s en commun",
    ]
    # Le point tape est le centre du libelle du bouton, bien qu'il ne soit pas
    # cliquable : l'ancetre cliquable recoit l'evenement.
    assert rows[0]["follow_point"] == (838, 1693)


def test_notifications_above_the_header_are_never_read_as_suggestions():
    rows = _parse(_screen(_row(1701, "Spa Echo", "Suivre", "4 ami(e)s en commun")))
    assert [row["label"] for row in rows] == ["Spa Echo"]


def test_without_the_header_nothing_is_read():
    """Pas d'en-tete a l'ecran = on n'est pas descendu assez bas. Ne rien inventer."""
    xml = ("<?xml version='1.0' encoding='UTF-8'?><hierarchy>"
           + _row(1701, "Spa Echo", "Suivre", "4 ami(e)s en commun") + "</hierarchy>")
    assert find_suggestions_header_y(_root(xml), NOTIFICATION_SELECTORS.suggestions_header_texts) is None
    assert _parse(xml) == []


def test_only_plain_follow_rows_are_followable():
    """Meme regle que depuis le feed : ni follow-back, ni deja suivi."""
    xml = _screen(
        _row(1701, "Me suit", "S’abonner en retour", "3 ami(e)s en commun")
        + _row(1899, "Inconnu", "Suivre", "2 ami(e)s en commun")
        + # Nom volontairement piegeux : il CONTIENT un libelle d'etat.
        _row(2097, "Suivi de pres", "Abonné", "1 ami(e) en commun")
    )
    rows = _parse(xml)
    assert [row["state"] for row in rows] == ["follow_back", "follow", "following"]
    assert [row["label"] for row in followable_suggestions(rows)] == ["Inconnu"]


def test_an_unreadable_button_is_not_followed_blindly():
    """Un libelle qu'on ne sait pas classer peut tout aussi bien etre 'Se desabonner'."""
    xml = _screen(_row(1701, "Compte", "Ne plus suivre", "1 ami(e) en commun"))
    assert followable_suggestions(_parse(xml)) == []
