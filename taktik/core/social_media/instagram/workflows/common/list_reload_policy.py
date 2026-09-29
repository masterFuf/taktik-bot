"""Giving a list that may still be loading its chance, before calling it finished.

A people list that has not finished loading and a people list that has ENDED are the same
screen: zero clickable rows. The bot has no way to tell them apart — there is no network
error state it can read, and Instagram shows none. So it read the first as the second, and
a run stopped mid-source with its budget untouched.

Measured on a real stop, 2026-08-27: the four empty scans that ended the run were spent in
SIX seconds, with 35 profiles of the 67 allowed and 52 minutes of session left. The decision
was a counter of scans, never a duration — which is exactly what a slow link defeats.

This is a SAFETY NET, and its shape says so:
  - it is consulted where the run was about to STOP, never while it is working, so a healthy
    run pays nothing for it;
  - it waits in growing steps and rescans between them, because a link that drops comes back
    on its own schedule, not on ours;
  - a fresh net is earned by INTERACTING again, not by waiting again — without that rule a
    list that keeps coming back empty-handed would buy another wait every lap.

What this module owns is the DECISION (should we wait, and how long). Reading the screen
belongs to the workflow, which alone knows what its own list looks like — the same split as
`private_streak_policy`.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple


#: Growing steps, rescanned between each. The first is short so a micro-drop costs almost
#: nothing; the whole net is bounded so a genuinely finished list is not held hostage.
DEFAULT_WAITS_SECONDS: Tuple[float, ...] = (5.0, 12.0, 25.0)


def _waits_from(value: Any) -> Tuple[float, ...]:
    """Operator input -> ordered waits. Anything unusable falls back to the default."""
    if value is None:
        return DEFAULT_WAITS_SECONDS
    if isinstance(value, (int, float)):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return DEFAULT_WAITS_SECONDS
    waits = []
    for item in value:
        try:
            seconds = float(item)
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            waits.append(seconds)
    return tuple(waits)


@dataclass
class ListReloadPolicy:
    """How long to keep giving a list the benefit of the doubt."""

    waits: Tuple[float, ...] = DEFAULT_WAITS_SECONDS

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]]) -> "ListReloadPolicy":
        """`list_reload_waits: []` (or 0) disarms the net entirely."""
        config = config or {}
        return cls(waits=_waits_from(config.get('list_reload_waits')))

    #: Motives the net deliberately does NOT cover. `end_of_list` is a MEASURED end — the run
    #: saw 95% of a source whose size it knows — so waiting on it would buy nothing and would
    #: tax every healthy run that simply finished its list.
    NOT_COVERED = frozenset({"end_of_list"})

    @property
    def armed(self) -> bool:
        return bool(self.waits)

    def covers(self, reason: Any) -> bool:
        """Is this the kind of ending a slow link could have faked?"""
        if not self.armed:
            return False
        code = getattr(reason, "code", None) or str(reason or "").strip().lower()
        return code not in self.NOT_COVERED

    @property
    def budget_seconds(self) -> float:
        """What one pass costs at worst — the number an operator actually cares about."""
        return sum(self.waits)

    def steps(self) -> Sequence[float]:
        """The waits of ONE pass, in order."""
        return self.waits
