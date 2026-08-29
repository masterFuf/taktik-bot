"""What happens to a brand-new TikTok follower: followed back, welcomed, or left alone.

The rule the callers keep getting wrong is that an AI verdict has THREE states, not two:
relevant, not relevant, and *the model did not answer*. Folding the third into "not relevant"
costs a follow-back; folding it into "relevant" sends a private message to a stranger on the
strength of a call that failed. Both branches are named below (`no_verdict`, `unscored_verdict`)
so nobody has to read the code to find out which one an absent verdict took.

Nothing here composes a message. The welcome texts are written upstream by the app, which holds
the account's persona; the bot picks one and types it. A canned sentence living in the bot would
go out in the account's name without the account knowing — the same rule Instagram's welcome DM
already follows.

Off by default, twice: the run's `ai.enabled` master switch AND an explicit
`ai.newFollowers.enabled`. A run that says nothing about the welcome pass behaves exactly as it
did before this file existed, even when AI is on for another reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Mapping, Optional, Sequence

# Why a follower got what it got. Stable strings: they are logged, and the front will read them.
REASON_AI_OFF = "ai_off"
REASON_UNREADABLE_HANDLE = "unreadable_handle"
REASON_PROFILE_UNREACHABLE = "profile_unreachable"
REASON_NO_VERDICT = "no_verdict"
REASON_UNSCORED = "unscored_verdict"
REASON_NOT_RELEVANT = "not_relevant"
REASON_BELOW_THRESHOLD = "below_threshold"
REASON_AI_DECLINED_FOLLOW = "ai_declined_follow"
REASON_NO_MESSAGE = "no_welcome_message"
REASON_RELEVANT = "ai_relevant"

DEFAULT_MIN_SCORE = 0.6
DEFAULT_MAX_DMS = 10
# Wider than the cold-DM default (30-60s) for the same reason Instagram's welcome DM is:
# a burst of private messages is the fastest way to get an account reported, and this flow
# walks profile -> conversation -> home between two of them anyway.
DEFAULT_DELAY_MIN = 30
DEFAULT_DELAY_MAX = 70


@dataclass(frozen=True)
class WelcomePolicy:
    """What the run is ALLOWED to do to a new follower. Everything defaults to off."""

    enabled: bool = False
    follow_back: bool = False
    welcome_dm: bool = False
    min_score: float = DEFAULT_MIN_SCORE
    dm_requires_follow_back: bool = True
    max_dms: int = DEFAULT_MAX_DMS
    delay_min: int = DEFAULT_DELAY_MIN
    delay_max: int = DEFAULT_DELAY_MAX
    messages: tuple = field(default_factory=tuple)

    @property
    def dm_requested_without_message(self) -> bool:
        """A run that asked for welcome DMs and shipped no text to send.

        Worth naming: it looks identical, in the stats, to a run where the AI rejected everyone.
        """
        return self.welcome_dm and not self.messages


@dataclass(frozen=True)
class WelcomeDecision:
    """One follower, one decision, and the reason it can be defended afterwards."""

    username: str
    follow_back: bool = False
    welcome_dm: bool = False
    reason: str = REASON_AI_OFF
    score: Optional[float] = None
    relevant: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "follow_back": self.follow_back,
            "welcome_dm": self.welcome_dm,
            "reason": self.reason,
            "score": self.score,
            "relevant": self.relevant,
        }


def parse_welcome_policy(ai_config: Optional[Mapping[str, Any]]) -> WelcomePolicy:
    """Read the run's `ai.newFollowers` block. Anything missing means OFF.

    Two switches on purpose. `ai.enabled` is already sent by every AI-capable TikTok run (the
    Followers workflow uses it for the relevance verdict), so gating on it alone would turn a
    profile-qualification run into an outreach run the day the front starts sending it here.
    """
    if not ai_config or not ai_config.get("enabled"):
        return WelcomePolicy()

    block = ai_config.get("newFollowers") or ai_config.get("new_followers") or {}
    if not isinstance(block, Mapping) or not block.get("enabled"):
        return WelcomePolicy()

    return WelcomePolicy(
        enabled=True,
        follow_back=bool(block.get("followBack", block.get("follow_back", True))),
        # Writing to someone privately is never a default.
        welcome_dm=bool(block.get("welcomeDm", block.get("welcome_dm", False))),
        min_score=_as_threshold(block.get("minScore", block.get("min_score", DEFAULT_MIN_SCORE))),
        dm_requires_follow_back=bool(
            block.get("dmRequiresFollowBack", block.get("dm_requires_follow_back", True))
        ),
        max_dms=_as_positive_int(block.get("maxDms", block.get("max_dms", DEFAULT_MAX_DMS)), DEFAULT_MAX_DMS),
        delay_min=_as_positive_int(block.get("delayMin", block.get("delay_min", DEFAULT_DELAY_MIN)), DEFAULT_DELAY_MIN),
        delay_max=_as_positive_int(block.get("delayMax", block.get("delay_max", DEFAULT_DELAY_MAX)), DEFAULT_DELAY_MAX),
        messages=_clean_messages(block.get("messages")),
    )


def decide_for_new_follower(
    username: str,
    verdict: Optional[Mapping[str, Any]],
    policy: WelcomePolicy,
) -> WelcomeDecision:
    """Turn one AI verdict into one decision. Pure: no device, no database, no clock."""
    handle = (username or "").strip().lstrip("@")
    if not handle:
        return WelcomeDecision("", reason=REASON_UNREADABLE_HANDLE)
    if not policy.enabled:
        return WelcomeDecision(handle, reason=REASON_AI_OFF)

    # No verdict is not a verdict. The AI was asked and did not answer (provider error, black
    # screenshot, classification without an engagement block) — acting on that would be acting
    # on nothing, which is exactly how 310 profiles once got a niche off a blank screen.
    if not isinstance(verdict, Mapping):
        return WelcomeDecision(handle, reason=REASON_NO_VERDICT)

    relevant = bool(verdict.get("relevant"))
    score = _as_score(verdict.get("score"))

    if not relevant:
        return WelcomeDecision(handle, reason=REASON_NOT_RELEVANT, score=score, relevant=False)
    if policy.min_score > 0 and score is None:
        # Relevant, but the threshold the operator set cannot be checked. Refusing keeps the
        # setting meaningful; letting it through would make `minScore` decorative.
        return WelcomeDecision(handle, reason=REASON_UNSCORED, score=None, relevant=True)
    if score is not None and score < policy.min_score:
        return WelcomeDecision(handle, reason=REASON_BELOW_THRESHOLD, score=score, relevant=True)

    ai_follow = bool(verdict.get("follow"))
    follow_back = policy.follow_back and ai_follow
    welcome_dm = policy.welcome_dm and bool(policy.messages)
    if policy.dm_requires_follow_back and not follow_back:
        welcome_dm = False

    if follow_back or welcome_dm:
        reason = REASON_RELEVANT
    elif not ai_follow:
        reason = REASON_AI_DECLINED_FOLLOW
    elif policy.dm_requested_without_message:
        reason = REASON_NO_MESSAGE
    else:
        reason = REASON_RELEVANT

    return WelcomeDecision(
        handle,
        follow_back=follow_back,
        welcome_dm=welcome_dm,
        reason=reason,
        score=score,
        relevant=True,
    )


def follow_back_targets(decisions: Sequence[WelcomeDecision]) -> List[str]:
    """Handles the pass decided to follow back, in the order they were met."""
    return [decision.username for decision in decisions if decision.follow_back and decision.username]


def welcome_dm_targets(decisions: Sequence[WelcomeDecision]) -> List[str]:
    """Handles the pass decided to welcome. The anti-duplicate guard still runs after this."""
    return [decision.username for decision in decisions if decision.welcome_dm and decision.username]


def summarize(decisions: Iterable[WelcomeDecision]) -> dict:
    """Counts per reason + per action, for the end-of-run line.

    A run that decided nothing and a run that was never asked to decide read the same in a
    "0 sent" summary; the reason breakdown is what tells them apart.
    """
    reasons: dict = {}
    follow_back = 0
    welcome_dm = 0
    for decision in decisions:
        reasons[decision.reason] = reasons.get(decision.reason, 0) + 1
        follow_back += 1 if decision.follow_back else 0
        welcome_dm += 1 if decision.welcome_dm else 0
    return {"reasons": reasons, "follow_back": follow_back, "welcome_dm": welcome_dm}


def _as_score(value: Any) -> Optional[float]:
    """The verdict's score as a float, or None when it is absent or unusable.

    A bool is rejected on purpose: `True` is a valid float in Python and would silently become
    a score of 1.0 — a perfect score nobody measured.
    """
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_threshold(value: Any) -> float:
    score = _as_score(value)
    if score is None:
        return DEFAULT_MIN_SCORE
    return min(max(score, 0.0), 1.0)


def _as_positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed >= 0 else fallback


def _clean_messages(raw: Any) -> tuple:
    if isinstance(raw, str):
        text = raw.strip()
        return (text,) if text else ()
    if isinstance(raw, (list, tuple, set)):
        return tuple(str(item).strip() for item in raw if str(item).strip())
    return ()


__all__ = [
    "DEFAULT_MAX_DMS",
    "DEFAULT_MIN_SCORE",
    "REASON_AI_DECLINED_FOLLOW",
    "REASON_AI_OFF",
    "REASON_BELOW_THRESHOLD",
    "REASON_NOT_RELEVANT",
    "REASON_NO_MESSAGE",
    "REASON_NO_VERDICT",
    "REASON_PROFILE_UNREACHABLE",
    "REASON_RELEVANT",
    "REASON_UNREADABLE_HANDLE",
    "REASON_UNSCORED",
    "WelcomeDecision",
    "WelcomePolicy",
    "decide_for_new_follower",
    "follow_back_targets",
    "parse_welcome_policy",
    "summarize",
    "welcome_dm_targets",
]
