"""Parseurs PURS du dump XML pour les suggestions de comptes Instagram.

Deux surfaces :

- le carousel "Suggested for you" (netego) insere dans le feed — point d'entree
  du mode ;
- l'ecran "Discover people" ouvert par son CTA "See all" — la liste ou l'on
  follow en masse.

Aucun acces device ici : les fonctions prennent une racine lxml (issue de
``dump_hierarchy``) et rendent des dicts simples, donc testables a partir d'un
dump capture. Le matching des resource-id se fait par SOUS-CHAINE parce qu'IG
rend certaines lignes avec un id nu (sans prefixe ``com.instagram.android:id/``)
et d'autres pleinement qualifie — meme strategie que la surface notifications.

Aucune signature UI n'est ecrite en dur : elles arrivent par les catalogues
``FEED_SUGGESTIONS_SELECTORS`` / ``DISCOVER_PEOPLE_SELECTORS``, et les libelles
d'etat du bouton par ``PROFILE_SELECTORS.follow_state_labels_*`` via
``classify_follow_state`` (source de verite unique, partagee avec le header profil).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from taktik.core.shared.device.ui_dump import parse_bounds


def _has_id(node, bare_id: str) -> bool:
    """True si le resource-id du noeud contient ``bare_id`` (nu ou qualifie)."""
    return bare_id in (node.get("resource-id") or "")


def _find_descendant(node, bare_id: str):
    """Premier descendant (ou le noeud lui-meme) dont l'id contient ``bare_id``."""
    for descendant in node.iter():
        if _has_id(descendant, bare_id):
            return descendant
    return None


def _text_of(node) -> str:
    """Texte du noeud, ou a defaut du premier descendant qui en porte un.

    Un dump compresse peut poser le texte sur un TextView enfant alors que le
    resource-id est sur le conteneur parent.
    """
    if node is None:
        return ""
    text = (node.get("text") or "").strip()
    if text:
        return text
    for descendant in node.iter():
        value = (descendant.get("text") or "").strip()
        if value:
            return value
    return ""


def _label_of(node) -> str:
    """Texte du noeud, avec repli sur son ``content-desc`` (bouton icone)."""
    text = _text_of(node)
    if text:
        return text
    if node is None:
        return ""
    return (node.get("content-desc") or "").strip()


def _top_of(node) -> Optional[int]:
    bounds = parse_bounds(node.get("bounds") or "")
    return bounds[1] if bounds else None


# =============================================================================
# Carousel "Suggested for you" dans le feed
# =============================================================================

def parse_feed_suggestions_carousel(root, selectors) -> Dict[str, Any]:
    """Etat du carousel netego dans le dump du feed.

    Returns un dict ``{present, title, cta_bounds, cards}`` — ``cta_bounds`` est
    le 4-tuple du bouton "See all" (a taper pour ouvrir Discover people), et
    ``cards`` la liste des cartes inline ``{name, follow_bounds, state_label}``.
    """
    result: Dict[str, Any] = {
        "present": False,
        "title": "",
        "cta_bounds": None,
        "cards": [],
    }
    if root is None:
        return result

    for node in root.iter("node"):
        if _has_id(node, selectors.carousel_container_id):
            result["present"] = True
            break

    for node in root.iter("node"):
        if _has_id(node, selectors.carousel_title_id):
            result["title"] = _label_of(node)
        elif _has_id(node, selectors.carousel_cta_id):
            result["cta_bounds"] = parse_bounds(node.get("bounds") or "")
        elif _has_id(node, selectors.card_container_id):
            name_node = _find_descendant(node, selectors.card_name_id)
            follow_node = _find_descendant(node, selectors.card_follow_button_id)
            if follow_node is None:
                continue
            result["cards"].append({
                "name": _label_of(name_node),
                "state_label": _label_of(follow_node),
                "follow_bounds": parse_bounds(follow_node.get("bounds") or ""),
            })

    # Un CTA seul sans conteneur (layout serveur alternatif) suffit a considerer
    # le bloc present : c'est lui qu'on tape.
    if result["cta_bounds"] and not result["present"]:
        result["present"] = True
    return result


# =============================================================================
# Ecran "Discover people"
# =============================================================================

def is_discover_people_screen(root, selectors) -> bool:
    """Preuve de surface : au moins une ligne de recommandation AVEC son bouton.

    Volontairement structurel (pas de texte) : le titre de la barre d'action est
    langue-dependant et la liste reste reconnaissable une fois scrollee, quand le
    titre a disparu du dump.
    """
    if root is None:
        return False
    has_row = False
    has_button = False
    for node in root.iter("node"):
        if _has_id(node, selectors.row_container_id):
            has_row = True
        elif _has_id(node, selectors.row_follow_button_id):
            has_button = True
        if has_row and has_button:
            return True
    return False


def read_screen_title(root) -> str:
    """Titre de la barre d'action, pour l'observabilite (log / rapport Lab)."""
    if root is None:
        return ""
    for node in root.iter("node"):
        if _has_id(node, "action_bar_title"):
            return _label_of(node)
    return ""


def parse_section_headers(root, selectors) -> List[Dict[str, Any]]:
    """En-tetes de section de la liste, ordonnes par position verticale."""
    headers: List[Dict[str, Any]] = []
    if root is None:
        return headers
    for node in root.iter("node"):
        if not _has_id(node, selectors.section_header_id):
            continue
        top = _top_of(node)
        headers.append({"label": _label_of(node), "top": top if top is not None else 0})
    headers.sort(key=lambda item: item["top"])
    return headers


def parse_suggestion_rows(root, selectors, profile_selectors,
                          classify_state) -> List[Dict[str, Any]]:
    """Lignes de suggestion visibles, de haut en bas.

    Chaque ligne est un sous-arbre ``recommended_user_row_content_identifier``
    qui contient deja son libelle, son bouton et son contexte social : aucun
    appariement par proximite verticale n'est necessaire.

    Chaque dict expose :

    - ``label``   : le texte affiche par IG (souvent le nom complet, parfois le
      handle — la surface n'expose PAS le @username de facon fiable) ;
    - ``state``   : 'follow' | 'follow_back' | 'following' | 'requested' | None,
      lu par ``classify_state`` sur le texte du bouton ;
    - ``section`` : l'en-tete de section au-dessus de la ligne, s'il est visible ;
    - ``follow_bounds`` / ``row_bounds`` : geometrie reelle pour un tap humanise.

    Les lignes d'accroche "Connect to Facebook" / "Connect contacts" ne sont pas
    des suggestions et sont ignorees.
    """
    rows: List[Dict[str, Any]] = []
    if root is None:
        return rows

    headers = parse_section_headers(root, selectors)

    def _section_for(top: Optional[int]) -> str:
        if top is None:
            return ""
        label = ""
        for header in headers:
            if header["top"] <= top:
                label = header["label"]
            else:
                break
        return label

    for node in root.iter("node"):
        if not _has_id(node, selectors.row_container_id):
            continue
        if any(_has_id(node, connect_id) for connect_id in selectors.connect_row_ids):
            continue

        follow_node = _find_descendant(node, selectors.row_follow_button_id)
        if follow_node is None:
            continue

        name_node = _find_descendant(node, selectors.row_username_id)
        context_node = _find_descendant(node, selectors.row_social_context_id)
        row_bounds = parse_bounds(node.get("bounds") or "")
        state_label = _label_of(follow_node)

        rows.append({
            "label": _label_of(name_node),
            "state": classify_state(state_label, profile_selectors),
            "state_label": state_label,
            "social_context": _label_of(context_node),
            "section": _section_for(row_bounds[1] if row_bounds else None),
            "follow_bounds": parse_bounds(follow_node.get("bounds") or ""),
            "row_bounds": row_bounds,
        })

    rows.sort(key=lambda row: row["row_bounds"][1] if row["row_bounds"] else 0)
    return rows


def followable_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sous-ensemble des lignes reellement a follow.

    Regle metier (arbitrage Kevin) : on ne fait ici NI follow-back NI acceptation
    de demande de suivi — ces deux flux appartiennent au workflow Notifications.
    Seul un bouton dont l'etat est exactement 'follow' est tape ; 'follow_back',
    'following' et 'requested' sont laisses tels quels. Une ligne sans libelle
    exploitable est ignoree plutot que tapee a l'aveugle.
    """
    return [row for row in rows
            if row.get("state") == "follow" and row.get("follow_bounds")]


__all__ = [
    "parse_feed_suggestions_carousel",
    "is_discover_people_screen",
    "read_screen_title",
    "parse_section_headers",
    "parse_suggestion_rows",
    "followable_rows",
]
