"""Parseur PUR de la zone "Suggestions" en bas de l'ecran Notifications.

Cette surface n'est PAS celle de "Discover people". Provenance : dumps reels
device 18171JEC, 2026-07-27. Ce qu'ils montrent, et qui commande tout le reste :

    'Suggestions'            <- en-tete de section, TEXTE seul
    'Spa Ec(h)o'             <- nom affiche
    '4 ami(e)s en commun'    <- contexte social
    'Suivre'                 <- TextView NON cliquable
    [Fermer]                 <- ImageView cliquable

**Aucun resource-id.** Ni sur les lignes, ni sur les champs. Impossible donc de
lire une ligne comme un sous-arbre : on regroupe par PROXIMITE VERTICALE, comme
le fait deja l'appariement Confirmer/Supprimer des demandes de suivi.

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


def _iter_text_nodes(root):
    """Noeuds portant un texte visible, avec leurs bounds parsees."""
    for node in root.iter("node"):
        text = (node.get("text") or "").strip()
        if not text:
            continue
        bounds = parse_bounds(node.get("bounds") or "")
        if bounds:
            yield node, text, bounds


def find_suggestions_header_y(root, header_texts: Sequence[str]) -> Optional[int]:
    """Ordonnee du haut de l'en-tete "Suggestions", ou None s'il n'est pas a l'ecran.

    L'en-tete est du TEXTE : il depend donc de la langue, contrairement a tout le
    reste de ce module. C'est la seule raison pour laquelle ce parseur a besoin
    d'un catalogue localise.
    """
    if root is None:
        return None
    wanted = [h.strip().lower() for h in (header_texts or []) if h and h.strip()]
    if not wanted:
        return None
    for _node, text, bounds in _iter_text_nodes(root):
        lowered = text.lower()
        if any(w == lowered or w in lowered for w in wanted):
            return bounds[1]
    return None


def parse_notification_suggestions(
    root,
    header_texts: Sequence[str],
    profile_selectors,
    classify_state: Callable[[str, Any], Optional[str]],
    screen_height: Optional[int] = None,
    screen_width: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Lignes de suggestion visibles sous l'en-tete, de haut en bas.

    Chaque dict expose ``label``, ``state``, ``state_label``, ``social_context``
    et ``follow_point`` (le centre du libelle du bouton, a taper).

    Une ligne n'est retenue que si son bouton se classe : un libelle illisible
    signifierait un trou de locale, et suivre a l'aveugle un bouton qu'on ne sait
    pas lire pourrait tout aussi bien etre un "Se desabonner".
    """
    rows: List[Dict[str, Any]] = []
    if root is None:
        return rows

    header_y = find_suggestions_header_y(root, header_texts)
    if header_y is None:
        return rows

    nodes = [
        (text, bounds)
        for _node, text, bounds in _iter_text_nodes(root)
        # Strictement SOUS l'en-tete : au-dessus, ce sont les notifications.
        if bounds[1] > header_y
    ]

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

        # Le nom est le plus haut de la bande, le contexte social ce qui suit.
        label = siblings[0][0] if siblings else ""
        social_context = siblings[1][0] if len(siblings) > 1 else ""

        rows.append({
            "label": label,
            "state": state,
            "state_label": state_label,
            "social_context": social_context,
            "follow_point": center(button_bounds),
            "row_top": button_bounds[1],
        })

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
    "parse_notification_suggestions",
    "followable_suggestions",
]
