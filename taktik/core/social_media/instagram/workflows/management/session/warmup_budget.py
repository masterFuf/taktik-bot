"""The warmup budget of an Instagram run: the caps the desktop computed for the account's day,
counted against what the account did today.

One counter for every Instagram run that writes: the automation (`SessionManager` holds one) and
the Taktik Agent (its launcher hands it one). The desktop app computes the caps from the account's
age and sends only numbers (`warmupPolicy` of the run's file); the bot never sees the curve. The
day is read from the ledger (`daily_stats`, through `get_today_totals`), where every gesture a
run files lands: a check made after a gesture sees it.

What the caps do, the same for both runs:
- the day's actions (likes + follows + comments + story likes) and this run's written actions
  (likes + follows + comments) STOP the run when reached;
- the day's follows and comments DISABLE their own gesture (`WarmupCheck.exhausted_intents`), the
  run goes on;
- the day's unfollows are a budget of their own (`unfollow_room`);
- the pace floor (`min_action_gap_seconds`) lengthens the pause after an action (`action_gap`):
  between two steps of the automation, after each gesture of the Agent.

Without caps (standalone, the CLI) nothing applies. A day that can no longer be read is not "no
cap": after a few failures in a row, the run stops (`daily_budget_unreadable`).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, Mapping, Optional, Set, Tuple

from loguru import logger

from taktik.core.database import get_db_service
from taktik.core.shared.behavior.sampling import sample_within

from . import stop_reasons

log = logger.bind(module="warmup-budget")

#: Consecutive failures of the day's read before the budget stops the run.
#: Not one: reads fail transiently, and a run must not die for that. Not never either, which is
#: what "continue without cap" amounted to -- a persistent condition (a locked DB, a schema that
#: moved) switched the protection off for good, with nothing but a log line to say so.
DAILY_USAGE_FAILURES_BEFORE_STOP = 3

#: The caps on the wire (`warmupPolicy`, what the desktop's `warmupPolicyForBot` sends) and the
#: names the budget keeps them under.
_WIRE_KEYS = (
    ("maxActionsPerDay", "max_actions_per_day", int),
    ("maxFollowsPerDay", "max_follows_per_day", int),
    ("maxCommentsPerDay", "max_comments_per_day", int),
    # A budget of its own: unfollows do not spend the like/follow/comment budget.
    ("maxUnfollowsPerDay", "max_unfollows_per_day", int),
    ("minActionGapSeconds", "min_action_gap_seconds", float),
    ("maxActionsPerSession", "max_actions_per_session", int),
)


def warmup_policy_from_payload(warmup: Any) -> Optional[Dict[str, Any]]:
    """The caps of a run's `warmupPolicy`, by the budget's names; None when the file has none.

    0 or absent on an axis: no cap on it."""
    if not isinstance(warmup, Mapping):
        return None
    return {name: kind(warmup.get(wire, 0) or 0) for wire, name, kind in _WIRE_KEYS}


@dataclass(frozen=True)
class WarmupCheck:
    """What the caps say on one read of the day: the reason that ends the run (empty to go on) and
    the gestures whose daily quota is spent."""

    stop_reason: str
    exhausted_intents: FrozenSet[str]


class WarmupBudget:
    """The caps of one run, and the account's day they are counted against.

    Like a Symfony service built per run: the caps come in the constructor, the day's totals from
    an injected reader (`set_daily_usage_provider`, or `count_against_account` for the ledger).
    """

    def __init__(self, policy: Optional[Mapping[str, Any]] = None):
        self._policy: Dict[str, Any] = dict(policy or {})
        # TODAY's totals of the account (keys total/follows/comments/unfollows). None: the day is
        # not read, and no cap is evaluated -- standalone.
        self._daily_usage_provider: Optional[Callable[[], Dict[str, int]]] = None
        # Consecutive failures of that read. One is transient and changes nothing; reaching the
        # threshold means the cap can no longer be evaluated, which is not "no cap".
        self._daily_usage_failures = 0

    # -------------------------------------------------------------------------- configuration

    @property
    def policy(self) -> Dict[str, Any]:
        return self._policy

    def set_policy(self, policy: Optional[Mapping[str, Any]]) -> None:
        """New caps (a config swap); the day's reader is kept, it carries the account."""
        self._policy = dict(policy or {})

    def set_daily_usage_provider(self, provider: Optional[Callable[[], Dict[str, int]]]) -> None:
        """Inject the callable returning TODAY's totals of the account."""
        self._daily_usage_provider = provider

    def count_against_account(self, account_id: Callable[[], Optional[int]]) -> None:
        """Read the day from the ledger of the account `account_id()` names, at each check.

        A reader, not a value: the account is resolved after the run started. Before it is,
        the day is empty (no cap trips); a failed read is left to `read_daily_usage` to count.
        """

        def today() -> Dict[str, int]:
            current = account_id()
            if not current:
                return {}
            return get_db_service().get_today_totals(current)

        self._daily_usage_provider = today

    def cap(self, name: str) -> float:
        """One cap of the policy; 0 when absent (no cap)."""
        return self._policy.get(name, 0) or 0

    # ------------------------------------------------------------------------------ the day

    @property
    def daily_usage_failures(self) -> int:
        return self._daily_usage_failures

    def read_daily_usage(self) -> Optional[Dict[str, int]]:
        """The account's totals for today, or None when there is nothing to enforce.

        `None` covers three situations that are NOT the same: standalone (no provider), no caps,
        and a read that failed. Only the third is an anomaly, and only it is counted -- the streak
        resets on the first successful read, so a transient failure leaves no trace.
        """
        provider = self._daily_usage_provider
        if provider is None or not self._policy:
            return None
        try:
            usage = provider() or {}
        except Exception as exc:  # noqa: BLE001 — the guard must never fail a run
            self._daily_usage_failures += 1
            log.warning(f"Daily-budget provider failed ({self._daily_usage_failures} in a row): {exc}")
            return None
        self._daily_usage_failures = 0
        return usage

    def _unreadable(self) -> bool:
        return self._daily_usage_failures >= DAILY_USAGE_FAILURES_BEFORE_STOP

    # ---------------------------------------------------------------------------- the checks

    def check(self, session_actions: int) -> WarmupCheck:
        """What a gesture asks just before it is made, on ONE read of the day: does a cap end the
        run, and which gestures have spent their daily quota.

        Asking whether the run ends, then which gestures are spent, read the day twice per
        gesture. On a base the synchronisation holds, each failed read counts toward
        `daily_budget_unreadable`: the run could stop at its second gesture. The Agent asks it
        before each gesture; the automation's loop asks it once per profile, and the profile's
        plan takes its spent gestures from that read (`SessionManager.exhausted_intents`).
        """
        usage = self.read_daily_usage()
        return WarmupCheck(
            stop_reason=self._stop_reason_on(usage, session_actions),
            exhausted_intents=frozenset(self._exhausted_on(usage)),
        )

    def stop_reason(self, session_actions: int, *, day_budget: bool = True) -> str:
        """Does a cap end the run? The reason, or empty to go on.

        `session_actions` is this run's written actions (likes + follows + comments). The day's
        budget first (not for an unfollow run, `day_budget=False`: it spends none of it, and the
        day is not read), then the run's own cap, which spreads the day over several gentle
        sessions rather than one dump.
        """
        usage = self.read_daily_usage() if day_budget else None
        return self._stop_reason_on(usage, session_actions, day_budget=day_budget)

    def _stop_reason_on(self, usage: Optional[Dict[str, int]], session_actions: int, *,
                        day_budget: bool = True) -> str:
        """`stop_reason` on a day already read (`usage`, None when not read or unreadable)."""
        if day_budget:
            if usage is None:
                if self._unreadable():
                    return stop_reasons.daily_budget_unreadable(self._daily_usage_failures)
            else:
                max_actions = int(self.cap("max_actions_per_day"))
                total = int(usage.get("total", 0))
                if max_actions > 0 and total >= max_actions:
                    return stop_reasons.daily_budget(total, max_actions)

        max_per_session = int(self.cap("max_actions_per_session"))
        if max_per_session > 0 and session_actions >= max_per_session:
            return stop_reasons.session_action_cap(session_actions, max_per_session)
        return ""

    def actions_left(self, session_actions: int) -> Optional[int]:
        """Written actions left before a cap ends the run; None when no cap applies."""
        left = []
        max_actions = int(self.cap("max_actions_per_day"))
        if max_actions > 0:
            usage = self.read_daily_usage()
            if usage is not None:
                left.append(max_actions - int(usage.get("total", 0)))
        max_per_session = int(self.cap("max_actions_per_session"))
        if max_per_session > 0:
            left.append(max_per_session - session_actions)
        return max(min(left), 0) if left else None

    def _exhausted_on(self, usage: Optional[Dict[str, int]]) -> Set[str]:
        """The gestures whose daily quota is spent (`follow`, `comment`) on a day already read
        (`usage`): they are disabled, the run goes on. Empty without caps, and when the day is not
        read or unreadable (`usage` None: fail-open, like the rest of the guard)."""
        spent: Set[str] = set()
        if usage is None:
            return spent
        max_follows = int(self.cap("max_follows_per_day"))
        if max_follows > 0 and int(usage.get("follows", 0)) >= max_follows:
            spent.add("follow")
        max_comments = int(self.cap("max_comments_per_day"))
        if max_comments > 0 and int(usage.get("comments", 0)) >= max_comments:
            spent.add("comment")
        return spent

    def unfollow_room(self) -> Tuple[Optional[int], Optional[str]]:
        """The day's unfollow budget: (room, stop_reason). room is None without that cap."""
        daily_cap = int(self.cap("max_unfollows_per_day"))
        if daily_cap <= 0:
            return None, None
        usage = self.read_daily_usage()
        # A day budget that can no longer be read is not "no budget" (same rule as the action
        # budget): after a few failed reads in a row, the unfollow stops.
        if usage is None:
            if self._unreadable():
                return 0, stop_reasons.daily_budget_unreadable(self._daily_usage_failures)
            return None, None
        today = int(usage.get("unfollows", 0) or 0)
        room = max(daily_cap - today, 0)
        if room == 0:
            return 0, stop_reasons.daily_unfollow_budget(today, daily_cap)
        return room, None

    def min_action_gap_seconds(self) -> float:
        """The pace floor between two actions; 0 for none."""
        return float(self.cap("min_action_gap_seconds"))

    def action_gap(self, low: float, high: float) -> float:
        """The pause after an action: a draw in [low, high] seconds, never under the pace floor.

        The one place the floor applies, for the automation (after a step) and the Agent (after a
        gesture). A draw under the floor is drawn again. When the whole range sits under it, the
        pause keeps the range's own spread above the floor: raising every gap to exactly the floor
        made the cadence a metronome, the very regularity the floor is there to break. No floor
        (zero, standalone): the range as it is.
        """
        floor = self.min_action_gap_seconds()
        if floor <= 0:
            return random.uniform(low, high)
        spread = max(abs(high - low), 0.1 * floor)
        return sample_within(lambda: random.uniform(low, high), floor, float("inf"), edge_band=spread)


__all__ = [
    "DAILY_USAGE_FAILURES_BEFORE_STOP",
    "WarmupBudget",
    "WarmupCheck",
    "warmup_policy_from_payload",
]
