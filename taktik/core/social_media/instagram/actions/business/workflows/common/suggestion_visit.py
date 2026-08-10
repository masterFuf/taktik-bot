"""QUALIFIED visit of a suggestions list, whatever the surface.

Instagram offers accounts to follow in two places, and both raise the same problem: the
list shows only a label, never the account. There is nothing to reconcile in the
database — the profile has to be opened and produced.

    the suggestions zone at the bottom of the activity screen (algorithm-served)
    the dedicated people discovery screen

The sequencing is identical on both sides: bring up the screen, read the rows, take the
first followable one never tried, open ITS PROFILE (the row body, never the button),
read the handle, run the per-profile production pipeline, come back. This module owns
that once. Without it, two sixty-line loops would carry the same fine rules — identity
dedup, errors reported rather than skipped, pacing — and would drift apart, exactly as
they already did on their stop policy.

What CHANGES from one surface to the other is isolated in an adapter, described by the
contract below: the navigation, and nothing else.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, List, Optional


class SuggestionSurface:
    """Contract a suggestions surface must fulfil to be visited.

    Nine gestures, all NAVIGATION or screen READING: no business decision belongs to the
    adapter. Filters, AI, interaction and writes all live in ``process()``, which is the
    per-profile production pipeline.
    """

    #: Short name of the surface, for logs and the stop reason.
    name = "suggestions"

    def reach(self) -> bool:
        """Bring the screen to the state where the rows are readable."""
        raise NotImplementedError

    def scan(self) -> List[Dict[str, Any]]:
        """Visible rows, each with at least ``label`` and ``state``."""
        raise NotImplementedError

    def followable(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """The rows actually to be followed (the surface business rule)."""
        raise NotImplementedError

    def row_key(self, row: Dict[str, Any]) -> str:
        """Identity of a row from one dump to the next (dedup)."""
        raise NotImplementedError

    def open_profile(self, row: Dict[str, Any]) -> bool:
        """Tap the row body and PROVE we are on a profile."""
        raise NotImplementedError

    def read_username(self) -> Optional[str]:
        """The handle read on the opened profile, or None."""
        raise NotImplementedError

    def process(self, username: str):
        """Per-profile production pipeline. Returns a ``ProfileProcessingResult``."""
        raise NotImplementedError

    def leave(self) -> bool:
        """Come back from the profile to the list."""
        raise NotImplementedError

    def scroll(self) -> None:
        """Scroll one screen down in the list."""
        raise NotImplementedError

    def already_known(self, row: Dict[str, Any]) -> bool:
        """Does the row designate an already-handled profile?

        OPTIONAL override, and only when the surface exposes enough to know it without
        opening the profile. By default we do not know, so we visit: being wrong here
        would cost a target, which is worse than paying for a visit twice.
        """
        return False

    # -- Outputs (the runner knows neither the logger nor the bridge) ---------
    def log_info(self, message: str) -> None:
        raise NotImplementedError

    def log_warning(self, message: str) -> None:
        raise NotImplementedError

    def notify(self, step: str, status: str, message: str = "", **extra: Any) -> None:
        return None


    # Two consecutive dumps with NO row at all end the list. One proves nothing: a render
    # in progress looks exactly like a finished list.
_EMPTY_DUMP_RUNS = 2


def visit_suggestions(surface: SuggestionSurface, *, max_profiles: int = 5,
                      max_scrolls: int = 8, delay_range: tuple = (4, 12),
                      on_profile: Optional[Callable[[Dict[str, Any]], None]] = None,
                      ) -> Dict[str, Any]:
    """Visiter et qualifier jusqu'a ``max_profiles`` comptes proposes.

    Each profile walks the full pipeline: extraction, AI qualification, filters, follow,
    database writes. The displayed label only serves to aim at the row; it is the handle
    read ON the profile that is persisted.
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

            # Already handled and recognisable WITHOUT opening the profile: the visit and
            # the AI call would be spent on a result we already have. Only the surfaces
            # that expose the account can know it; the others visit.
        if surface.already_known(row):
            result["skipped_known"] += 1
            surface.log_info(f"'{label}' deja en base — visite epargnee")
            result["profiles"].append({"label": label, "username": None,
                                       "status": "already_known"})
            continue

        surface.notify("suggestion_visit", "running", label, label=label)

        if not surface.open_profile(row):
                # Neither a profile nor a silent error: the tap missed its target or the
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
            except Exception as exc:  # noqa: BLE001 — a callback never breaks the pass
                surface.log_warning(f"callback de suggestion en echec: {exc}")

        surface.leave()
            # Human pace BETWEEN two profiles: the follow is the most watched
        # surveille, on ne l'enchaine jamais a vitesse machine.
        if result["visited"] < max_profiles:
            time.sleep(random.uniform(min(low, high), max(low, high)))

    return result


__all__ = ["SuggestionSurface", "visit_suggestions"]
