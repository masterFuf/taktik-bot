"""The anti-duplicate guard for the TikTok welcome DM — three states, not two.

`SentDMService.check_already_sent` returns False in two very different situations: nobody was
ever written to, and the question could not be asked. A missing database file, a table that is
not there yet, a query that raises — all of them come back as "never contacted", because the
service catches Exception and answers False. Instagram's cold DM shipped on top of that False
for months: the `sent_dms.platform` column had never been added to existing databases, every
check raised into the swallow, and the outreach had in practice no duplicate protection at all.

So this guard does not ask "already messaged?". It asks "what is known?", and UNKNOWN is one of
the answers. An outreach that cannot check is refused, not sent: messaging the same person twice
costs the account, and a refused run costs a run.

That is why the probes injected here MUST RAISE when they cannot answer. A probe that returns
False on failure hands this guard the exact bug it exists to prevent, and the guard cannot tell
the difference from the outside.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

# What is known about "have we written to this person before".
CONTACTED = "contacted"
CLEAR = "clear"
UNKNOWN = "unknown"

# Why a recipient is skipped. Ordered by cost in `skip_reason`: the free checks first.
SKIP_NO_ACCOUNT = "no_account"
SKIP_NO_RECIPIENT = "no_recipient"
SKIP_ALREADY_DMED = "already_dmed"
SKIP_CONVERSATION_EXISTS = "conversation_exists"
SKIP_GUARD_UNAVAILABLE = "guard_unavailable"

PLATFORM = "tiktok"

# (account_id, handle) -> True when a DM was already sent. Raises when it cannot answer.
SentDmProbe = Callable[[int, str], bool]
# (account_id, handle) -> True when a thread already carries a message WE sent. Raises likewise.
ThreadProbe = Callable[[int, str], bool]


def _noop_log(_level: str, _message: str) -> None:
    return None


class WelcomeDmGuard:
    """Answers "may we write to this person for the first time?" — and admits when it cannot."""

    def __init__(
        self,
        *,
        sent_dm_probe: SentDmProbe,
        thread_probe: Optional[ThreadProbe] = None,
        log: Callable[[str, str], None] = _noop_log,
    ) -> None:
        self._sent_dm_probe = sent_dm_probe
        self._thread_probe = thread_probe
        self._log = log

    def contact_state(self, account_id: Optional[int], recipient: str) -> str:
        """CONTACTED / CLEAR / UNKNOWN for one recipient.

        UNKNOWN is returned for anything that prevents an answer, including a missing account:
        without one, nothing could be recorded afterwards either, so the same welcome would be
        re-sent at every run.
        """
        handle = _clean(recipient)
        if not account_id or not handle:
            return UNKNOWN

        try:
            if self._sent_dm_probe(account_id, handle):
                return CONTACTED
        except Exception as exc:  # noqa: BLE001 — the whole point: a failed check is not a "no"
            self._log("warning", f"[WELCOME] Sent-DM check unavailable for @{handle}: {exc}")
            return UNKNOWN

        if self._thread_probe is None:
            return CLEAR

        # `sent_dms` alone misses a conversation started anywhere else — an inbox reply, a
        # manual answer, the DM read workflow. Welcoming someone we are already talking to
        # reads as a bot to the only person who can report us.
        try:
            if self._thread_probe(account_id, handle):
                return CONTACTED
        except Exception as exc:  # noqa: BLE001
            self._log("warning", f"[WELCOME] DM thread check unavailable for @{handle}: {exc}")
            return UNKNOWN

        return CLEAR

    def skip_reason(self, account_id: Optional[int], recipient: str) -> Optional[str]:
        """Why this recipient must NOT be welcomed, or None to proceed."""
        if not account_id:
            return SKIP_NO_ACCOUNT
        handle = _clean(recipient)
        if not handle:
            return SKIP_NO_RECIPIENT

        try:
            if self._sent_dm_probe(account_id, handle):
                return SKIP_ALREADY_DMED
        except Exception as exc:  # noqa: BLE001
            self._log("warning", f"[WELCOME] Sent-DM check unavailable for @{handle}: {exc}")
            return SKIP_GUARD_UNAVAILABLE

        if self._thread_probe is not None:
            try:
                if self._thread_probe(account_id, handle):
                    return SKIP_CONVERSATION_EXISTS
            except Exception as exc:  # noqa: BLE001
                self._log("warning", f"[WELCOME] DM thread check unavailable for @{handle}: {exc}")
                return SKIP_GUARD_UNAVAILABLE

        return None

    def filter_recipients(
        self, account_id: Optional[int], recipients: Sequence[str]
    ) -> Tuple[List[str], Dict[str, str]]:
        """Split recipients into (allowed, {handle: skip_reason}).

        Runs before any navigation so a refused pass costs nothing on the device, and so the
        operator sees the reasons even when the count ends up at zero.
        """
        allowed: List[str] = []
        skipped: Dict[str, str] = {}
        for recipient in recipients or []:
            handle = _clean(recipient)
            reason = self.skip_reason(account_id, recipient)
            if reason is None:
                allowed.append(handle)
            else:
                skipped[handle or str(recipient)] = reason
        return allowed, skipped

    def as_duplicate_checker(self) -> Callable[..., bool]:
        """The `duplicate_checker` the DM outreach workflow expects: True means SKIP.

        Bound to the same guard the pass already ran, so the last word before a send is the
        same code that filtered the list — and UNKNOWN still means skip down here, where the
        message would actually leave.
        """

        def _checker(account_id: int, recipient: str, platform: str = PLATFORM) -> bool:
            reason = self.skip_reason(account_id, recipient)
            if reason is not None:
                self._log("info", f"[WELCOME] @{_clean(recipient)} non contacté ({reason})")
            return reason is not None

        return _checker


def unknown_states(states: Mapping[str, str]) -> List[str]:
    """Handles whose contact state could not be established, from a {handle: state} map."""
    return [handle for handle, state in states.items() if state == UNKNOWN]


def _clean(value: Any) -> str:
    return str(value or "").strip().lstrip("@").lower()


__all__ = [
    "CLEAR",
    "CONTACTED",
    "PLATFORM",
    "SKIP_ALREADY_DMED",
    "SKIP_CONVERSATION_EXISTS",
    "SKIP_GUARD_UNAVAILABLE",
    "SKIP_NO_ACCOUNT",
    "SKIP_NO_RECIPIENT",
    "SentDmProbe",
    "ThreadProbe",
    "UNKNOWN",
    "WelcomeDmGuard",
    "unknown_states",
]
