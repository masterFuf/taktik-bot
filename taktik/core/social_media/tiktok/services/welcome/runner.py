"""The qualification pass over a scraped new-followers list. Decides; acts on nothing.

Split from the acting on purpose. Following back and writing a DM are two different device
journeys with two different costs, and a pass that decided and acted in the same loop could
only be tested with a phone in hand. Here the device shows up as two injected callables
(`visit_profile`, `qualify`), so the whole decision path — including the branches nobody wants
to reproduce on a real account — is exercised without one.

`visit_profile` is expected to be the production navigation
(`NavigationActions.navigate_to_user_profile`), which already answers ARRIVAL rather than
click: it checks the screen is a profile at all, then that the handle is the one asked for. A
False from it means we did not land where we meant to, and a verdict taken there would describe
a stranger's profile while being filed under our follower's name.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional, Sequence

from taktik.core.social_media.tiktok.services.welcome.decision import (
    REASON_AI_OFF,
    REASON_PROFILE_UNREACHABLE,
    REASON_UNREADABLE_HANDLE,
    WelcomeDecision,
    WelcomePolicy,
    decide_for_new_follower,
)

VisitProfile = Callable[[str], bool]
Qualify = Callable[[str], Optional[dict]]


def _noop_log(_level: str, _message: str) -> None:
    return None


class NewFollowerWelcomePass:
    """Walk the scraped followers, qualify each one, return one decision per follower."""

    def __init__(
        self,
        *,
        policy: WelcomePolicy,
        visit_profile: VisitProfile,
        qualify: Qualify,
        log: Callable[[str, str], None] = _noop_log,
    ) -> None:
        self.policy = policy
        self._visit_profile = visit_profile
        self._qualify = qualify
        self._log = log

    def decide(self, followers: Sequence[Any]) -> List[WelcomeDecision]:
        """One decision per follower, in the order they were listed.

        Every follower produces a row, including the ones nothing happened to. A pass that
        dropped its skipped rows would report "0 welcomed" identically whether the AI rejected
        everyone or the navigation never arrived once.
        """
        decisions: List[WelcomeDecision] = []
        if not self.policy.enabled:
            for follower in followers or []:
                decisions.append(WelcomeDecision(_handle_of(follower), reason=REASON_AI_OFF))
            return decisions

        for follower in followers or []:
            handle = _handle_of(follower)
            if not handle:
                decisions.append(WelcomeDecision("", reason=REASON_UNREADABLE_HANDLE))
                continue

            arrived = False
            try:
                arrived = bool(self._visit_profile(handle))
            except Exception as exc:  # noqa: BLE001 — one unreachable profile is not a failed run
                self._log("warning", f"[WELCOME] Navigation vers @{handle} impossible: {exc}")

            if not arrived:
                # Not "no verdict": we never got to the screen the verdict would describe.
                decisions.append(WelcomeDecision(handle, reason=REASON_PROFILE_UNREACHABLE))
                continue

            verdict = None
            try:
                verdict = self._qualify(handle)
            except Exception as exc:  # noqa: BLE001
                self._log("warning", f"[WELCOME] Verdict IA indisponible pour @{handle}: {exc}")

            decision = decide_for_new_follower(handle, verdict, self.policy)
            self._log(
                "info",
                f"[WELCOME] @{handle}: follow_back={decision.follow_back} "
                f"welcome_dm={decision.welcome_dm} ({decision.reason})",
            )
            decisions.append(decision)

        return decisions


def _handle_of(follower: Any) -> str:
    """The handle of a scraped row, whatever shape the caller had.

    `read_new_followers` yields dicts; a caller replaying a list of names passes strings. Both
    are accepted, neither is guessed at: anything else returns "" and is reported as unreadable.
    """
    if isinstance(follower, str):
        return follower.strip().lstrip("@")
    if isinstance(follower, dict):
        return str(follower.get("username") or "").strip().lstrip("@")
    return ""


__all__ = ["NewFollowerWelcomePass", "Qualify", "VisitProfile"]
