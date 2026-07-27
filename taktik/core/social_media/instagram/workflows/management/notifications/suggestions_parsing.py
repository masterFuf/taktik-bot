"""Parseur PUR de la zone "Suggestions" en bas de l'ecran Notifications.

Cette surface n'est PAS celle de "Discover people". Provenance : dumps reels
device 18171JEC, 2026-07-27 (18:09 puis 19:41). Ce qu'ils montrent, et qui commande
tout le reste :

    'Suggestions'            <- en-tete de section, activity_feed_header_row
    [igds_people_cell]       <- la ligne, cliquable
        'Spa Ec(h)o'         <- nom affiche      (TextView nu)
        '4 ami(e)s en commun'<- contexte social  (TextView nu)
        [igds_button]        <- le bouton, cliquable
            'Suivre'         <- son libelle      (TextView nu)
        [Fermer]             <- ImageView cliquable

**Les CHAMPS ne portent aucun resource-id**, mais la ligne et le bouton en portent un.
La premiere lecture de cette surface avait conclu "aucun resource-id" et reconstitue
les lignes par PROXIMITE VERTICALE seule. Ce chemin reste ici en repli — IG sert des
layouts differents pour un meme APK — mais il n'est plus le chemin principal : sans le
discriminant de la ligne, une notification "X, que vous connaissez peut-etre, est sur
Instagram", qui porte elle aussi un bouton "Suivre", se lit comme une suggestion.

L'ancre est le BOUTON, pas le nom : c'est lui qui porte l'etat de relation, et
son libelle passe par ``classify_follow_state`` — la meme fonction que le header
profil, donc la meme couverture de langues (le francais alterne entre "Suivre"
et "S'abonner", et rend une apostrophe typographique).

Le tap vise les bounds du libelle bien qu'il ne soit pas cliquable : l'ancetre
cliquable recoit l'evenement. Meme mecanique que le bouton "Voir plus" de cet
ecran, deja traite ainsi.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from taktik.core.shared.device.ui_dump import center, parse_bounds, vertical_center

# Ecart vertical entre deux lignes sur les dumps de reference (~198px sur un ecran
# 1080x2400). La bande d'une ligne est prise a la moitie : au-dela, on est chez la
# voisine. Exprime en FRACTION de la hauteur d'ecran, jamais en pixels — la meme
# liste sur un autre device n'a pas le meme pas.
_ROW_PITCH_RATIO = 198 / 2400


def iter_text_nodes(root):
    """Noeuds portant un texte visible, avec leurs bounds parsees."""
    for node in root.iter("node"):
        text = (node.get("text") or "").strip()
        if not text:
            continue
        bounds = parse_bounds(node.get("bounds") or "")
        if bounds:
            yield node, text, bounds


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _has_id(node, resource_id: Optional[str]) -> bool:
    return bool(resource_id) and resource_id in (node.get("resource-id") or "")


def find_suggestions_header_y(root, header_texts: Sequence[str],
                              header_resource_id: Optional[str] = None) -> Optional[int]:
    """Ordonnee du haut de l'en-tete "Suggestions", ou None s'il n'est pas a l'ecran.

    L'en-tete est du TEXTE : il depend donc de la langue, contrairement au reste de ce
    module. C'est la seule raison pour laquelle ce parseur a besoin d'un catalogue
    localise.

    Le libelle est exige **exact**, et porte par un noeud d'en-tete de section quand
    l'appelant fournit son resource-id. Un "contient" sur n'importe quel TextView
    faisait matcher la notification « Suggestions de suivi : taktik-bot, Vic Hernandez
    et 3 autres personnes » (dump 19:41) : l'ancre tombait 950px trop haut et toutes
    les notifications situees dessous — avec leurs propres boutons "Suivre" — etaient
    lues comme des suggestions.
    """
    if root is None:
        return None
    wanted = {_normalize(h) for h in (header_texts or []) if h and h.strip()}
    if not wanted:
        return None
    for node, text, bounds in iter_text_nodes(root):
        if header_resource_id and not _has_id(node, header_resource_id):
            continue
        if _normalize(text) in wanted:
            return bounds[1]
    return None


def _row_from_cell(cell, profile_selectors, classify_state,
                   button_resource_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Une ligne lue comme un SOUS-ARBRE, quand la surface expose sa cellule.

    Le libelle d'etat est cherche dans le sous-arbre du bouton ; a defaut (layout ou
    le bouton n'a pas d'id), dans les textes de la cellule qui se classent. Une ligne
    dont le bouton ne se classe pas est rendue quand meme, avec ``state`` a None :
    c'est un trou de locale, et l'appelant doit pouvoir le dire plutot que de la voir
    disparaitre.
    """
    texts = [(text, bounds) for _node, text, bounds in iter_text_nodes(cell)]
    if not texts:
        return None

    button_nodes = [n for n in cell.iter("node") if _has_id(n, button_resource_id)]
    button_texts = [(text, bounds)
                    for node in button_nodes
                    for _n, text, bounds in iter_text_nodes(node)]

    state_label, button_bounds, state = "", None, None
    for text, bounds in (button_texts or texts):
        resolved = classify_state(text, profile_selectors)
        if resolved is not None or button_texts:
            state_label, button_bounds, state = text, bounds, resolved
            break

    if button_bounds is None:
        return None

    # Tout ce qui n'est pas le bouton : le nom en premier (le plus haut), le contexte
    # social ensuite. Le contexte est optionnel — beaucoup de lignes n'en ont pas.
    others = [(text, bounds) for text, bounds in texts if bounds != button_bounds]
    others.sort(key=lambda item: item[1][1])
    if not others:
        return None

    cell_bounds = parse_bounds(cell.get("bounds") or "")
    return {
        "label": others[0][0],
        "state": state,
        "state_label": state_label,
        "social_context": others[1][0] if len(others) > 1 else "",
        "follow_point": center(button_bounds),
        # Le corps de la ligne : c'est LUI qu'on tape pour ouvrir le profil, quand on
        # veut le @handle et les donnees de profil plutot qu'un follow a l'aveugle
        # depuis la liste. Le libelle n'est pas cliquable, la cellule qui le contient
        # l'est — meme mecanique que le bouton.
        "row_point": center(others[0][1]),
        "row_top": cell_bounds[1] if cell_bounds else others[0][1][1],
    }


def _rows_from_geometry(nodes, profile_selectors, classify_state,
                        screen_height: Optional[int],
                        screen_width: Optional[int]) -> List[Dict[str, Any]]:
    """Repli : reconstituer les lignes par proximite verticale, sans cellule.

    Conserve pour les layouts qui ne rendent pas ``igds_people_cell`` — IG sert des
    layouts differents pour un meme APK, et perdre la zone entiere sur un layout
    inconnu serait pire que de la lire avec une heuristique.
    """
    rows: List[Dict[str, Any]] = []
    pitch = int((screen_height or 2400) * _ROW_PITCH_RATIO)
    band = max(pitch // 2, 1)

    # Le bouton vit dans la COLONNE DE DROITE ; le nom et le contexte a gauche. Sans
    # cette borne, un compte reellement nomme "Suivi" ou "Follow" se lisait comme un
    # bouton et fabriquait une ligne fantome. Exprimee en fraction de la largeur, jamais
    # en pixels — la meme liste n'a pas la meme grille sur un autre device.
    right_column = (screen_width or 1080) * 0.55
    buttons = [(text, bounds) for text, bounds in nodes
               if bounds[0] >= right_column
               and classify_state(text, profile_selectors) is not None]

    for state_label, button_bounds in buttons:
        state = classify_state(state_label, profile_selectors)
        button_y = vertical_center(button_bounds)

        # Les textes de CETTE ligne : meme bande verticale, et pas le bouton lui-meme.
        siblings = [
            (text, bounds) for text, bounds in nodes
            if bounds is not button_bounds
            and abs(vertical_center(bounds) - button_y) <= band
            and bounds[0] < right_column
        ]
        siblings.sort(key=lambda item: item[1][1])
        if not siblings:
            continue

        rows.append({
            "label": siblings[0][0],
            "state": state,
            "state_label": state_label,
            "social_context": siblings[1][0] if len(siblings) > 1 else "",
            "follow_point": center(button_bounds),
            "row_point": center(siblings[0][1]),
            "row_top": button_bounds[1],
        })
    return rows


def parse_notification_suggestions(
    root,
    header_texts: Sequence[str],
    profile_selectors,
    classify_state: Callable[[str, Any], Optional[str]],
    screen_height: Optional[int] = None,
    screen_width: Optional[int] = None,
    header_resource_id: Optional[str] = None,
    row_resource_id: Optional[str] = None,
    button_resource_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Lignes de suggestion visibles sous l'en-tete, de haut en bas.

    Chaque dict expose ``label``, ``state``, ``state_label``, ``social_context``,
    ``follow_point`` (le bouton) et ``row_point`` (le corps de la ligne, a taper pour
    ouvrir le profil).

    Deux chemins, dans cet ordre : par CELLULE (``row_resource_id``) quand la surface
    en expose — c'est le seul moyen sur de ne pas confondre une suggestion avec une
    notification qui porte elle aussi un bouton "Suivre" — puis par geometrie en repli.
    """
    if root is None:
        return []

    header_y = find_suggestions_header_y(root, header_texts, header_resource_id)
    if header_y is None:
        return []

    if row_resource_id:
        cells = []
        for node in root.iter("node"):
            if not _has_id(node, row_resource_id):
                continue
            bounds = parse_bounds(node.get("bounds") or "")
            # Strictement SOUS l'en-tete : au-dessus, ce sont les notifications.
            if bounds and bounds[1] > header_y:
                cells.append((bounds[1], node))
        if cells:
            cells.sort(key=lambda item: item[0])
            rows = [_row_from_cell(node, profile_selectors, classify_state, button_resource_id)
                    for _top, node in cells]
            return [row for row in rows if row]

    nodes = [(text, bounds) for _node, text, bounds in iter_text_nodes(root)
             if bounds[1] > header_y]
    rows = _rows_from_geometry(nodes, profile_selectors, classify_state,
                               screen_height, screen_width)
    rows.sort(key=lambda row: row["row_top"])
    return rows


def followable_suggestions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Les lignes reellement a suivre.

    Meme regle metier que depuis le feed (arbitrage Kevin) : seul un bouton dont
    l'etat est exactement 'follow' est tape. Un 'follow_back' appartient au flux
    de follow-back, un 'following' est deja fait.
    """
    return [row for row in rows if row.get("state") == "follow" and row.get("follow_point")]


__all__ = [
    "find_suggestions_header_y",
    "iter_text_nodes",
    "parse_notification_suggestions",
    "followable_suggestions",
]
