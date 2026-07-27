"""Visite QUALIFIEE d'une liste de suggestions, quelle que soit la surface.

Instagram propose des comptes a suivre a deux endroits, et les deux posent le meme
probleme : la liste n'affiche qu'un libelle, pas le compte. Il n'y a donc rien a
reconcilier en base — il faut ouvrir la fiche et la produire.

    zone "Suggestions" du bas de l'ecran Notifications   (servie par l'algorithme)
    ecran "Decouvrir des personnes"                      (surface dediee)

Le sequencage est identique des deux cotes : amener l'ecran, lire les lignes, prendre
la premiere suivable jamais tentee, ouvrir SON PROFIL (le corps de la ligne, jamais le
bouton), lire le @handle, faire tourner le pipeline par-profil de production, revenir.
Ce module le possede une fois. Sans lui, deux boucles de soixante lignes portant les
memes regles fines — deduplication par identite, erreurs dites et non sautees, cadence
entre deux profils — se mettraient a diverger, exactement comme target/hashtag/likers
l'avaient fait sur leur politique d'arret.

Ce qui CHANGE d'une surface a l'autre est isole dans un adaptateur (cf. le contrat
ci-dessous) : la navigation, et elle seule.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, List, Optional


class SuggestionSurface:
    """Contrat qu'une surface de suggestions doit remplir pour etre visitee.

    Neuf gestes, tous de NAVIGATION ou de LECTURE d'ecran : aucune decision metier
    n'appartient a l'adaptateur. Les filtres, l'IA, l'interaction et les ecritures
    vivent dans ``process()``, qui est le pipeline par-profil de production.
    """

    #: Nom court de la surface, pour les logs et le motif d'arret.
    name = "suggestions"

    def reach(self) -> bool:
        """Amener l'ecran a l'etat ou les lignes sont lisibles."""
        raise NotImplementedError

    def scan(self) -> List[Dict[str, Any]]:
        """Lignes visibles, chacune avec au moins ``label`` et ``state``."""
        raise NotImplementedError

    def followable(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Les lignes reellement a suivre (regle metier de la surface)."""
        raise NotImplementedError

    def row_key(self, row: Dict[str, Any]) -> str:
        """Identite d'une ligne d'un dump a l'autre (deduplication)."""
        raise NotImplementedError

    def open_profile(self, row: Dict[str, Any]) -> bool:
        """Taper le corps de la ligne et PROUVER qu'on est sur un profil."""
        raise NotImplementedError

    def read_username(self) -> Optional[str]:
        """Le @handle lu sur le profil ouvert, ou None."""
        raise NotImplementedError

    def process(self, username: str):
        """Pipeline par-profil de production. Rend un ``ProfileProcessingResult``."""
        raise NotImplementedError

    def leave(self) -> bool:
        """Revenir du profil vers la liste."""
        raise NotImplementedError

    def scroll(self) -> None:
        """Descendre d'un ecran dans la liste."""
        raise NotImplementedError

    def already_known(self, row: Dict[str, Any]) -> bool:
        """La ligne designe-t-elle un profil deja traite ?

        Surcharge OPTIONNELLE, et seulement quand la surface expose de quoi le savoir
        sans ouvrir la fiche. Par defaut on ne sait pas, donc on visite : se tromper
        ici couterait une cible, ce qui est pire que de repayer une visite.
        """
        return False

    # -- Sorties (le runner ne connait ni loguru ni le bridge) ----------------
    def log_info(self, message: str) -> None:
        raise NotImplementedError

    def log_warning(self, message: str) -> None:
        raise NotImplementedError

    def notify(self, step: str, status: str, message: str = "", **extra: Any) -> None:
        return None


# Deux dumps d'affilee sans AUCUNE ligne signent la fin de la liste. Un seul ne prouve
# rien : un rendu en cours donne le meme resultat qu'une liste finie.
_EMPTY_DUMP_RUNS = 2


def visit_suggestions(surface: SuggestionSurface, *, max_profiles: int = 5,
                      max_scrolls: int = 8, delay_range: tuple = (4, 12),
                      on_profile: Optional[Callable[[Dict[str, Any]], None]] = None,
                      ) -> Dict[str, Any]:
    """Visiter et qualifier jusqu'a ``max_profiles`` comptes proposes.

    Chaque profil traverse le pipeline complet : extraction (bio, photo, stats),
    qualification IA, filtres, follow, ecritures DB. Le libelle affiche ne sert qu'a
    viser la ligne ; c'est le @handle lu SUR le profil qui est persiste.
    """
    result: Dict[str, Any] = {
        "visited": 0, "processed": 0, "follows": 0, "filtered": 0, "skipped_known": 0,
        "errors": 0, "attempts": 0, "scrolls": 0, "skipped_follow_back": 0,
        "profiles": [], "stop_reason": "max_reached",
    }
    if max_profiles <= 0:
        result["stop_reason"] = "disabled"
        return result

    low, high = (delay_range if delay_range and len(delay_range) == 2 else (4, 12))
    attempted: set = set()
    seen_follow_back: set = set()
    empty_dump_streak = 0

    while result["visited"] < max_profiles:
        if not surface.reach():
            result["stop_reason"] = getattr(surface, "reach_failure_reason", "zone_not_reached")
            break

        rows = surface.scan()
        seen_follow_back.update(surface.row_key(row) for row in rows
                                if row.get("state") == "follow_back")
        result["skipped_follow_back"] = len(seen_follow_back)

        candidates = [row for row in surface.followable(rows)
                      if surface.row_key(row) not in attempted]

        if not candidates:
            empty_dump_streak = empty_dump_streak + 1 if not rows else 0
            if empty_dump_streak >= _EMPTY_DUMP_RUNS:
                result["stop_reason"] = "list_exhausted"
                break
            if result["scrolls"] >= max_scrolls:
                result["stop_reason"] = "max_scrolls"
                break
            surface.scroll()
            result["scrolls"] += 1
            continue

        empty_dump_streak = 0
        row = candidates[0]
        label = row.get("label") or "(sans libelle)"
        attempted.add(surface.row_key(row))
        result["attempts"] += 1

        # Deja traite et reconnaissable SANS ouvrir la fiche : la visite et l'appel IA
        # seraient depenses pour un resultat qu'on a deja. Seules les surfaces qui
        # exposent le compte peuvent le savoir ; les autres visitent.
        if surface.already_known(row):
            result["skipped_known"] += 1
            surface.log_info(f"'{label}' deja en base — visite epargnee")
            result["profiles"].append({"label": label, "username": None,
                                       "status": "already_known"})
            continue

        surface.notify("suggestion_visit", "running", label, label=label)

        if not surface.open_profile(row):
            # Ni un profil, ni une erreur silencieuse : le tap a rate sa cible ou la
            # page n'a pas charge. On le dit, on revient, et on passe a la suivante.
            surface.log_warning(f"'{label}': le profil ne s'est pas ouvert")
            surface.notify("suggestion_visit", "failed", f"{label}: profil non ouvert",
                           label=label)
            result["errors"] += 1
            result["profiles"].append({"label": label, "username": None,
                                       "status": "not_opened"})
            surface.leave()
            continue

        result["visited"] += 1
        username = surface.read_username()
        if not username:
            surface.log_warning(f"'{label}': profil ouvert mais @handle illisible")
            surface.notify("suggestion_visit", "failed", f"{label}: @handle illisible",
                           label=label)
            result["errors"] += 1
            result["profiles"].append({"label": label, "username": None,
                                       "status": "no_username"})
            surface.leave()
            continue

        outcome = surface.process(username)
        result["processed"] += 1
        result["follows"] += outcome.follows
        if outcome.was_filtered:
            result["filtered"] += 1
        if outcome.was_error:
            result["errors"] += 1
        entry = {
            "label": label, "username": username, "status": outcome.status,
            "follows": outcome.follows, "reasons": list(outcome.filter_reasons or []),
        }
        result["profiles"].append(entry)
        surface.log_info(f"'{label}' -> @{username}: {outcome.status} "
                         f"({result['visited']}/{max_profiles})")
        surface.notify("suggestion_visit", "done", f"@{username}: {outcome.status}",
                       label=label, username=username, outcome=outcome.status)
        if on_profile:
            try:
                on_profile(entry)
            except Exception as exc:  # noqa: BLE001 — un callback ne casse pas la passe
                surface.log_warning(f"callback de suggestion en echec: {exc}")

        surface.leave()
        # Cadence humaine ENTRE deux profils : le follow est le geste le plus
        # surveille, on ne l'enchaine jamais a vitesse machine.
        if result["visited"] < max_profiles:
            time.sleep(random.uniform(min(low, high), max(low, high)))

    return result


__all__ = ["SuggestionSurface", "visit_suggestions"]
