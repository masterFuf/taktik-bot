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


# ---------------------------------------------------------------------------
# Structure REELLE de la surface (dump 18171JEC 19:41, 2026-07-27, anonymise).
#
# La premiere lecture avait conclu que rien ne portait de resource-id. C'est vrai des
# CHAMPS, faux de la ligne et du bouton — et cette nuance decide tout : l'ecran melange
# des suggestions et des NOTIFICATIONS qui portent, elles aussi, un bouton "Suivre".
# ---------------------------------------------------------------------------

def _cell(top, name, button_label, context=None):
    """Une ligne de suggestion telle qu'IG la rend : une cellule, un bouton."""
    ctx = _text(context, 231, top + 108, 534, top + 147) if context else ""
    return (
        f'<node class="android.view.View" resource-id="igds_people_cell" clickable="true"'
        f' text="" bounds="[0,{top}][1080,{top + 198}]">'
        + _text(name, 231, top + 51, 443, top + 97)
        + ctx
        + f'<node class="android.view.View" resource-id="igds_button" clickable="true"'
          f' text="" bounds="[589,{top + 33}][970,{top + 165}]">'
        + _text(button_label, 633, top + 76, 926, top + 122)
        + "</node></node>"
    )


def _notification(top, text, button_label):
    """Une NOTIFICATION avec son propre bouton — le piege de cet ecran."""
    return (
        f'<node class="android.view.View" resource-id="activity_feed_newsfeed_story_row"'
        f' clickable="true" text="" bounds="[0,{top}][1080,{top + 210}]">'
        + _text(text, 253, top + 32, 739, top + 178)
        + f'<node class="android.view.View" resource-id="igds_button" clickable="true"'
          f' text="" bounds="[772,{top + 23}][1036,{top + 155}]">'
        + _text(button_label, 846, top + 66, 963, top + 112)
        + "</node></node>"
    )


def _header(text, top):
    return (f'<node class="android.widget.TextView" resource-id="activity_feed_header_row"'
            f' text="{text}" bounds="[44,{top}][306,{top + 53}]"/>')


def _real_screen(body):
    return "<?xml version='1.0' encoding='UTF-8'?><hierarchy>" + body + "</hierarchy>"


def _parse_real(xml):
    return parse_notification_suggestions(
        _root(xml), NOTIFICATION_SELECTORS.suggestions_header_texts,
        PROFILE_SELECTORS, classify_follow_state,
        screen_height=2340, screen_width=1080,
        header_resource_id=NOTIFICATION_SELECTORS.notification_section_header_resource_id,
        row_resource_id=NOTIFICATION_SELECTORS.suggestion_row_resource_id,
        button_resource_id=NOTIFICATION_SELECTORS.suggestion_button_resource_id,
    )


def test_a_notification_mentioning_suggestions_is_not_the_header():
    """« Suggestions de suivi : X, Y et 3 autres personnes » CONTIENT « Suggestions ».

    Un ancrage par sous-chaine tombait dessus 950px trop haut, et tout ce qui se
    trouvait dessous — donc de vraies notifications — devenait des suggestions.
    """
    xml = _real_screen(
        _notification(495, "Suggestions de suivi\u00a0: taktik-bot, Vic H. et 3 autres personnes", "Suivre")
        + _header("Suggestions", 1498)
        + _cell(1573, "Nina", "Suivre")
    )
    assert find_suggestions_header_y(
        _root(xml), NOTIFICATION_SELECTORS.suggestions_header_texts,
        NOTIFICATION_SELECTORS.notification_section_header_resource_id,
    ) == 1498


def test_notifications_carrying_their_own_follow_button_are_not_suggestions():
    """Sous l'en-tete, seules les CELLULES sont des suggestions.

    « lafontaine.zoe, que vous connaissez peut-etre, est sur Instagram » porte un
    bouton « Suivre » : sans le discriminant de la ligne, elle se lit comme une
    suggestion et le bot ouvre une notification en croyant ouvrir un profil suggere.
    """
    xml = _real_screen(
        _header("Suggestions", 1000)
        + _notification(1034, "lafontaine.zoe, que vous connaissez peut-\u00eatre, est sur Instagram", "Suivre")
        + _cell(1573, "Nina", "Suivre")
    )
    assert [row["label"] for row in _parse_real(xml)] == ["Nina"]


def test_a_cell_is_read_as_a_subtree_not_by_proximity():
    xml = _real_screen(
        _header("Suggestions", 1498)
        + _cell(1573, "koulou6649", "Suivre en retour", "1\u00a0ami(e) en commun")
        + _cell(1771, "Nina", "Suivre")
    )
    rows = _parse_real(xml)
    assert [(row["label"], row["state"]) for row in rows] == [
        ("koulou6649", "follow_back"), ("Nina", "follow"),
    ]
    # Une ligne sans contexte social n'invente rien.
    assert rows[1]["social_context"] == ""
    assert [row["label"] for row in followable_suggestions(rows)] == ["Nina"]


def test_a_cell_above_the_header_is_ignored():
    """Les cellules existent aussi ailleurs sur cet ecran : la borne reste l'en-tete."""
    xml = _real_screen(
        _cell(600, "Deja vu ailleurs", "Suivre")
        + _header("Suggestions", 1498)
        + _cell(1573, "Nina", "Suivre")
    )
    assert [row["label"] for row in _parse_real(xml)] == ["Nina"]


def test_an_unreadable_button_inside_a_cell_is_surfaced_not_dropped():
    """Un trou de locale doit SE VOIR, pas disparaitre.

    Une ligne dont le bouton ne se classe pas (ici un libelle d'une langue absente du
    catalogue) remonte avec ``state=None`` : l'appelant peut alors le dire dans les
    logs. La faire disparaitre du resultat rendrait un ecran entier d'illisibles
    indiscernable d'un ecran sans suggestions.
    """
    xml = _real_screen(_header("Suggestions", 1498) + _cell(1573, "Compte", "Seguir"))
    rows = _parse_real(xml)
    assert [row["state"] for row in rows] == [None]
    assert [row["label"] for row in rows] == ["Compte"]
    assert followable_suggestions(rows) == []


def test_an_unfollow_button_inside_a_cell_is_never_followable():
    """« Ne plus suivre » CONTIENT « Suivre » : le piege deja rencontre, cote cellule."""
    xml = _real_screen(_header("Suggestions", 1498) + _cell(1573, "Compte", "Ne plus suivre"))
    rows = _parse_real(xml)
    assert [row["state"] for row in rows] == ["following"]
    assert followable_suggestions(rows) == []
