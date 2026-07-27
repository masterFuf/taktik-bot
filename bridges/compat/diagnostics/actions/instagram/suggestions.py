"""Suggestions actions for Instagram compat diagnostics (Cartography Lab).

Sondes atomiques du mode "follow des suggestions" du workflow Feed :
carousel netego "Suggested for you" -> CTA "See all" -> modale d'acces aux
contacts -> ecran "Discover people" -> follow de masse.

PROD-ALIGNED : chaque action appelle EXACTEMENT la methode de production du
``FeedBusiness`` (mixin ``FeedSuggestionsMixin``) deja construit sur le device
chaud par le bundle Lab. Aucun chemin, aucun selector et aucune detection
d'ecran ne sont reimplementes ici : un run vert exerce le code que le workflow
reel executera.

Toutes les signatures UI viennent des catalogues centralises
(``FEED_SUGGESTIONS_SELECTORS`` / ``DISCOVER_PEOPLE_SELECTORS`` /
``POPUP_SELECTORS``) — aucun resource-id ni libelle n'est ecrit ici.
"""

from bridges.compat.diagnostics.actions.instagram import action


# Ce que veut lire Kevin dans le rapport : pourquoi ca s'est arrete la, et
# est-ce que le device est revenu sur le feed. Le plafond demande est la cause
# la plus frequente et la moins evidente a l'oeil.
_STOP_LABELS = {
    "max_reached": "plafond demande atteint",
    "list_exhausted": "fin de liste",
    "max_scrolls": "plafond de scrolls atteint",
    "session_limit": "limite de session",
    "scroll_failed": "scroll impossible",
    "carousel_absent": "carousel absent",
    "carousel_not_found": "carousel jamais apparu",
    "cta_tap_failed": "CTA non tape",
    "blocked_by_dialog": "alerte Instagram non reconnue",
    "discover_screen_not_reached": "ecran suggestions jamais atteint",
    "disabled": "plafond a zero",
}


def _follow_summary(res, max_follows, suffix=""):
    """Message de rapport commun aux actions qui follow."""
    follows = res.get("follows", 0)
    stop = res.get("stop_reason", "?")
    parts = [f"{follows}/{max_follows} follow(s)"]
    if suffix:
        parts.append(suffix)
    parts.append(f"arret: {_STOP_LABELS.get(stop, stop)}")
    if res.get("skipped_follow_back"):
        parts.append(f"{res['skipped_follow_back']} 'Follow back' ignore(s)")
    if res.get("returned_to_feed") is False:
        parts.append("RETOUR AU FEED ECHOUE")
    return " — ".join(parts)


@action("suggestions.detect_carousel")
def detect_carousel(a, p):
    """Le carousel de suggestions est-il present dans le feed courant ?"""
    carousel = a.feed.detect_feed_suggestions_carousel()
    cards = carousel.get("cards", [])
    if not carousel.get("present"):
        return {"success": True, "found": False,
                "message": "Carousel de suggestions absent de l'ecran"}
    return {
        "success": True,
        "found": True,
        "message": (f"Carousel '{carousel.get('title') or '?'}' — {len(cards)} carte(s), "
                    f"CTA {'trouve' if carousel.get('cta_bounds') else 'absent'}"),
        "details": carousel,
    }


@action("suggestions.probe_carousel")
def probe_carousel(a, p):
    """Sonde legere (1 acces device) utilisee par la boucle feed a chaque post."""
    found = a.feed.has_feed_suggestions_carousel()
    return {"success": True, "found": found,
            "message": f"Sonde carousel: {'present' if found else 'absent'}"}


@action("suggestions.open_see_all")
def open_see_all(a, p):
    """Taper le CTA "See all" du carousel pour ouvrir l'ecran Discover people."""
    ok = a.feed.open_suggestions_see_all()
    return {"success": bool(ok),
            "message": "CTA 'See all' tape" if ok else "CTA 'See all' introuvable ou tap echoue"}


@action("suggestions.handle_contacts_dialog")
def handle_contacts_dialog(a, p):
    """Traiter la modale d'acces aux contacts (param ``choice`` = deny | allow).

    Rend ``other_dialog`` sans rien taper si l'alerte affichee n'est PAS la
    demande de contacts — c'est la garde qui evite de taper le bouton primaire
    d'une alerte soft-ban portant les memes resource-id.
    """
    choice = str(p.get("choice", "deny"))
    outcome = a.feed.handle_contacts_access_dialog(choice)
    return {
        "success": outcome in ("denied", "allowed", "absent"),
        "found": outcome in ("denied", "allowed"),
        "message": f"Modale contacts: {outcome}",
        "details": {"outcome": outcome, "choice": choice},
    }


@action("suggestions.is_discover_screen")
def is_discover_screen(a, p):
    """L'ecran "Discover people" est-il affiche ? (preuve de surface structurelle)"""
    found = a.feed.is_on_discover_people_screen()
    return {"success": True, "found": found,
            "message": f"Ecran suggestions: {'affiche' if found else 'absent'}"}


@action("suggestions.scan_rows")
def scan_rows(a, p):
    """Lire les lignes de suggestion visibles et leur etat de relation."""
    rows = a.feed.scan_discover_suggestions()
    if not rows:
        return {"success": False, "found": False,
                "message": "Aucune ligne de suggestion lue sur cet ecran"}
    by_state = {}
    for row in rows:
        by_state[row.get("state") or "inconnu"] = by_state.get(row.get("state") or "inconnu", 0) + 1
    summary = ", ".join(f"{count} {state}" for state, count in sorted(by_state.items()))
    return {
        "success": True,
        "found": True,
        "message": f"{len(rows)} ligne(s): {summary}",
        "details": {"rows": rows, "by_state": by_state},
    }


@action("suggestions.scroll_list")
def scroll_list(a, p):
    """Descendre d'un ecran dans la liste de suggestions (scroll humanise)."""
    ok = a.feed.scroll_discover_suggestions()
    return {"success": bool(ok), "message": "Scroll liste suggestions" if ok else "Scroll echoue"}


@action("suggestions.follow_visible")
def follow_visible(a, p):
    """Follow depuis la liste ouverte (param ``max`` = plafond, 1 par defaut).

    N'agit que sur les boutons dont l'etat est exactement 'Follow' : les
    'Follow back' sont comptes et laisses intacts (le follow-back appartient au
    workflow Notifications).
    """
    max_follows = int(p.get("max", 1))
    delay_low = float(p.get("delay_min", 2))
    delay_high = float(p.get("delay_max", 5))
    max_scrolls = int(p.get("max_scrolls", 8))
    res = a.feed.follow_discover_suggestions(
        max_follows=max_follows,
        delay_range=(delay_low, delay_high),
        max_scrolls=max_scrolls,
    )
    return {
        "success": res.get("follows", 0) > 0,
        "message": _follow_summary(res, max_follows,
                                   f"{res.get('scrolls', 0)} scroll(s) dans la liste"),
        "details": res,
    }


@action("suggestions.back_to_feed")
def back_to_feed(a, p):
    """Quitter l'ecran de suggestions et revenir au feed.

    Sonde du point qui avait bloque le premier run device : cet ecran n'a pas de
    barre d'onglets et ne repond pas a la touche back materielle. On tape la
    fleche de la barre d'action, puis on confirme le retour sur l'accueil.
    """
    ok = a.feed._return_to_feed()
    still_there = a.feed.is_on_discover_people_screen()
    return {
        "success": bool(ok),
        "message": ("Retour au feed confirme" if ok
                    else ("Toujours sur l'ecran suggestions" if still_there
                          else "Ecran quitte mais accueil non confirme")),
        "details": {"returned": bool(ok), "still_on_suggestions": still_there},
    }


@action("suggestions.find_carousel")
def find_carousel(a, p):
    """Scroller le feed jusqu'a faire apparaitre le carousel (sans rien liker).

    Scroll humanise simple et non l'avance "vers le prochain vrai post" : cette
    derniere saute par-dessus les blocs non-organiques, donc par-dessus la cible.
    """
    max_scrolls = int(p.get("max_scrolls", 12))
    res = a.feed.find_feed_suggestions_carousel(max_scrolls)
    return {
        "success": bool(res.get("found")),
        "found": bool(res.get("found")),
        "message": (f"Carousel trouve apres {res.get('scrolls', 0)} scroll(s)"
                    if res.get("found")
                    else f"Aucun carousel apres {res.get('scrolls', 0)} scroll(s)"),
        "details": res,
    }


@action("suggestions.run_only")
def run_only(a, p):
    """Run "suggestions seules" de production : chercher le carousel, follow, s'arreter.

    Aucune interaction avec le fil (ni like, ni commentaire, ni story).
    """
    max_follows = int(p.get("max", 2))
    config = {
        "max_suggestion_follows": max_follows,
        "suggestions_contacts_choice": str(p.get("choice", "deny")),
        "suggestion_follow_delay_range": (float(p.get("delay_min", 2)),
                                          float(p.get("delay_max", 5))),
        "max_suggestion_scrolls": int(p.get("max_scrolls", 8)),
        "max_carousel_scrolls": int(p.get("max_carousel_scrolls", 12)),
        "max_suggestion_passes": 1,
    }
    res = a.feed.run_suggestions_only(config)
    return {
        "success": res.get("follows", 0) > 0,
        "message": _follow_summary(res, max_follows,
                                   f"apres {res.get('carousel_scrolls', 0)} scroll(s) de recherche"),
        "details": res,
    }


@action("suggestions.run_pass")
def run_pass(a, p):
    """Passe complete de production : carousel -> liste -> follows -> retour feed.

    Plafonds volontairement bas par defaut pour un test unitaire au Lab.
    """
    max_follows = int(p.get("max", 2))
    config = {
        "max_suggestion_follows": max_follows,
        "suggestions_contacts_choice": str(p.get("choice", "deny")),
        "suggestion_follow_delay_range": (float(p.get("delay_min", 2)),
                                          float(p.get("delay_max", 5))),
        "max_suggestion_scrolls": int(p.get("max_scrolls", 8)),
    }
    res = a.feed.run_feed_suggestions_pass(config)
    if not res.get("entered"):
        stop = res.get("stop_reason", "?")
        return {"success": False,
                "message": f"Passe non entree — {_STOP_LABELS.get(stop, stop)}",
                "details": res}
    return {
        "success": True,
        "message": _follow_summary(res, max_follows,
                                   f"modale contacts: {res.get('contacts_dialog')}"),
        "details": res,
    }
