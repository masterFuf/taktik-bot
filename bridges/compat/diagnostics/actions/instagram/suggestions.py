"""Suggestions actions for Instagram compat diagnostics (Cartography Lab).

Atomic probes of the feed workflow's suggestions-follow mode, in the order the
workflow meets them: in-feed carousel -> "See all" CTA -> contacts-access modal ->
people discovery screen -> bulk follow.

Each action calls EXACTLY the production method of the feed business object,
already built on the warm device by the diagnostics bundle. No path, no selector
and no screen detection is reimplemented here, so a green run exercises the very
code the real workflow will run.

Every UI signature comes from the centralized catalogs
(``FEED_SUGGESTIONS_SELECTORS`` / ``DISCOVER_PEOPLE_SELECTORS`` /
``POPUP_SELECTORS``) — no resource-id and no label is written here.
"""

from bridges.compat.diagnostics.actions.instagram import action


# What the report must say: why it stopped there, and whether the device came
# back to the feed. The requested cap is the most frequent cause and the least
# obvious one to the eye.
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
    "home_not_reached": "accueil non atteint",
    "discover_screen_lost": "ecran suggestions perdu",
    "zone_not_reached": "zone non atteinte",
    "no_pipeline": "pipeline profil absent",
}


def _follow_summary(res, max_follows, suffix=""):
    """Report message shared by the actions that follow."""
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
    """Is the suggestions carousel present in the current feed?"""
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
    """Light probe (one device access) used by the feed loop on every post."""
    found = a.feed.has_feed_suggestions_carousel()
    return {"success": True, "found": found,
            "message": f"Sonde carousel: {'present' if found else 'absent'}"}


@action("suggestions.open_see_all")
def open_see_all(a, p):
    """Tap the carousel CTA to open the people discovery screen."""
    ok = a.feed.open_suggestions_see_all()
    return {"success": bool(ok),
            "message": "CTA 'See all' tape" if ok else "CTA 'See all' introuvable ou tap echoue"}


@action("suggestions.handle_contacts_dialog")
def handle_contacts_dialog(a, p):
    """Handle the contacts-access modal (``choice`` = deny | allow).

    Returns ``other_dialog`` without tapping anything when the alert shown is NOT the
    contacts request: this is the guard that avoids tapping the primary button of a
    restriction alert carrying the same resource-ids.
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
    """Is the people discovery screen shown? (structural surface proof)"""
    found = a.feed.is_on_discover_people_screen()
    return {"success": True, "found": found,
            "message": f"Ecran suggestions: {'affiche' if found else 'absent'}"}


@action("suggestions.scan_rows")
def scan_rows(a, p):
    """Read the visible suggestion rows and their relationship state."""
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
    """Scroll one screen down in the suggestions list (humanized)."""
    ok = a.feed.scroll_discover_suggestions()
    return {"success": bool(ok), "message": "Scroll liste suggestions" if ok else "Scroll echoue"}


@action("suggestions.follow_visible")
def follow_visible(a, p):
    """Follow from the open list (``max`` = cap, 1 by default).

    Acts only on the buttons whose state is exactly followable: the follow-back rows
    are counted and left untouched, since follow-back belongs to the
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
    """Leave the suggestions screen and come back to the feed.

    Probes the point that blocked the first device run: this screen has no tab bar
    and does not answer the hardware back key. The action-bar arrow is tapped, then
    the return to the home screen is confirmed.
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
    """Scroll the feed until the carousel appears, liking nothing.

    A plain humanized scroll rather than the advance to the next real post: that one
    skips over the non-organic blocks, so over the very target.
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
    """Production suggestions-only run: find the carousel, follow, stop.

    No interaction with the feed itself: no like, no comment, no story.
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
    """Full production pass: carousel -> list -> follows -> back to the feed.

    Caps deliberately low by default, for a single-probe test.
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


# =============================================================================
# QUALIFIED visit, as opposed to the bulk follow above
#
# The list exposes only a label: a suggested account is UNKNOWN, there is nothing
# to reconcile, so its profile is opened and run through the per-profile
# production pipeline, like a target.
# =============================================================================

def _visit_config(p):
    """Interaction config of the visit: acquisition, so follow and nothing else."""
    from taktik.core.social_media.instagram.workflows.management.notifications import (
        DEFAULT_SUGGESTION_INTERACTION_CONFIG,
    )
    return dict(DEFAULT_SUGGESTION_INTERACTION_CONFIG)


def _attach_session(a, session_id):
    """Attach the feed workflow to the open session.

    The account is bound for the whole bundle before the action runs. The session is
    opened per action, so it is attached here — and without it the interactions belong to
    nothing and never surface in the history.
    """
    from taktik.core.social_media.instagram.workflows.management.session import SessionManager

    if a.feed.session_manager is None:
        a.feed.session_manager = SessionManager({"session_settings": {}})
    a.feed.session_manager.session_id = session_id
    return a.feed.active_account_id


def _visit_summary(res, max_profiles):
    stop = res.get("stop_reason", "?")
    parts = [f"{res.get('visited', 0)}/{max_profiles} profil(s) visite(s)",
             f"{res.get('follows', 0)} follow(s)",
             f"{res.get('filtered', 0)} filtre(s)"]
    if res.get("skipped_known"):
        parts.append(f"{res['skipped_known']} deja en base (visite epargnee)")
    if res.get("errors"):
        parts.append(f"{res['errors']} erreur(s)")
    parts.append(f"arret: {_STOP_LABELS.get(stop, stop)}")
    return " — ".join(parts)


@action("suggestions.open_profile")
def open_profile(a, p):
    """Open the PROFILE of the first followable row of the open list.

    Taps the NAME and never the centre of the row: the follow button occupies its
    right side, and aiming at the middle would follow from the list, which is
    exactly what this visit replaces.
    """
    from taktik.core.social_media.instagram.actions.business.workflows.feed.suggestions_parsing import (
        followable_rows,
    )
    rows = followable_rows(a.feed.scan_discover_suggestions())
    if not rows:
        return {"success": False, "message": "Aucune ligne suivable a l'ecran"}
    row = rows[0]
    label = row.get("label") or "?"
    if not a.feed.open_discover_profile(row):
        return {"success": False, "message": f"'{label}' n'a pas ouvert de profil"}
    username = a.feed.detection_actions.get_username_from_profile()
    return {"success": True,
            "message": f"'{label}' -> @{username or '?'}",
            "details": {"label": label, "username": username}}


@action("suggestions.back_to_list")
def back_to_list(a, p):
    """Come back from the profile to the suggestions list (arrow, then back key)."""
    ok = a.feed.leave_discover_profile()
    return {"success": bool(ok),
            "message": ("Retour a la liste confirme" if ok
                        else "Liste de suggestions non retrouvee")}


@action("suggestions.visit_visible")
def visit_visible(a, p):
    """Qualified visit from the ALREADY-open list (``max``, 1 by default).

    For each row: open the profile, extract, qualify, filter, follow, write, then
    come back to the list.
    """
    from bridges.compat.diagnostics.actions.instagram.notifications import lab_suggestion_session

    max_profiles = int(p.get("max", 1))
    with lab_suggestion_session(p, "discover_people") as session_id:
        _attach_session(a, session_id)
        res = a.feed.visit_discover_suggestions(
            _visit_config(p), max_profiles=max_profiles,
            max_scrolls=int(p.get("max_scrolls", 8)),
            delay_range=(float(p.get("delay_min", 2)), float(p.get("delay_max", 5))),
        )
    res["session_id"] = session_id
    return {"success": res.get("processed", 0) > 0,
            "message": _visit_summary(res, max_profiles)
                       + f" — session {session_id or 'aucune'}",
            "details": res}


@action("suggestions.run_visit_pass")
def run_visit_pass(a, p):
    """Full qualified pass: home -> carousel -> list -> visits -> back to the feed."""
    from bridges.compat.diagnostics.actions.instagram.notifications import lab_suggestion_session

    max_profiles = int(p.get("max", 1))
    with lab_suggestion_session(p, "discover_people") as session_id:
        _attach_session(a, session_id)
        res = a.feed.run_discover_visit_pass(
            _visit_config(p), max_profiles=max_profiles,
            max_carousel_scrolls=int(p.get("max_carousel_scrolls", 12)),
            max_scrolls=int(p.get("max_scrolls", 8)),
            delay_range=(float(p.get("delay_min", 2)), float(p.get("delay_max", 5))),
        )
    res["session_id"] = session_id
    if not res.get("entered"):
        stop = res.get("stop_reason", "?")
        return {"success": False,
                "message": f"Passe non entree — {_STOP_LABELS.get(stop, stop)}",
                "details": res}
    return {"success": True,
            "message": _visit_summary(res, max_profiles)
                       + f" — modale contacts: {res.get('contacts_dialog')}"
                       + f" — session {session_id or 'aucune'}",
            "details": res}
