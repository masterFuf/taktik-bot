from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger


PAUSE_STRATEGIES = {
    "idle_in_app",
    "close_app",
    "lock_screen",
    "switch_workflow",
    "observe_content",
    "disabled",
}

PROFILE_IDS = {
    "natural",
    "strict_test",
    "balanced",
    "careful",
    "slow_reader",
    "fast",
    "fast_debug",
}


@dataclass(frozen=True)
class ResumePolicy:
    reentry: str = "from_home"
    rotate_context: bool = True


@dataclass(frozen=True)
class PausePolicy:
    enabled: bool = False
    after_actions: Optional[int] = None
    duration_min_seconds: Optional[float] = None
    duration_max_seconds: Optional[float] = None
    strategy: str = "idle_in_app"
    interruptible: bool = True
    resume: Optional[ResumePolicy] = None


@dataclass(frozen=True)
class BehaviorPolicy:
    profile_id: str = "natural"
    seed: Optional[int] = None
    strict_regression: bool = False
    pause: Optional[PausePolicy] = None
    typing_raw: Optional[dict[str, Any]] = None
    tap_raw: Optional[dict[str, Any]] = None
    scroll_raw: Optional[dict[str, Any]] = None


def parse_behavior_policy(config: dict[str, Any] | None) -> Optional[BehaviorPolicy]:
    """Parse optional Electron behaviorPolicy payloads without runtime effects.

    Missing or invalid payloads return None or safe defaults. Unknown fields are
    ignored for forward compatibility.
    """
    if not isinstance(config, dict):
        return None

    raw = config.get("behaviorPolicy")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        logger.warning("[BehaviorPolicy] Ignoring non-object behaviorPolicy payload")
        return None

    profile_id = _profile_id(raw.get("profileId"))
    strict_regression = _bool(raw.get("strictRegression"), False)

    return BehaviorPolicy(
        profile_id=profile_id,
        seed=_optional_int(raw.get("seed")),
        strict_regression=strict_regression,
        pause=_parse_pause_policy(raw.get("pausePolicy")),
        typing_raw=_optional_dict(raw.get("typingPolicy")),
        tap_raw=_optional_dict(raw.get("tapPolicy")),
        scroll_raw=_optional_dict(raw.get("scrollPolicy")),
    )


def _parse_pause_policy(raw: Any) -> Optional[PausePolicy]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        logger.warning("[BehaviorPolicy] Ignoring non-object pausePolicy payload")
        return None

    return PausePolicy(
        enabled=_bool(raw.get("enabled"), False),
        after_actions=_optional_int(raw.get("afterActions")),
        duration_min_seconds=_optional_float(raw.get("durationMinSeconds")),
        duration_max_seconds=_optional_float(raw.get("durationMaxSeconds")),
        strategy=_pause_strategy(raw.get("strategy")),
        interruptible=_bool(raw.get("interruptible"), True),
        resume=_parse_resume_policy(raw.get("resume")),
    )


def _parse_resume_policy(raw: Any) -> Optional[ResumePolicy]:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        logger.warning("[BehaviorPolicy] Ignoring non-object resume payload")
        return None

    reentry = raw.get("reentry")
    if reentry != "from_home":
        if reentry is not None:
            logger.warning("[BehaviorPolicy] Unsupported resume.reentry '{}', using from_home", reentry)
        reentry = "from_home"

    return ResumePolicy(
        reentry=reentry,
        rotate_context=_bool(raw.get("rotateContext"), True),
    )


def _profile_id(value: Any) -> str:
    if isinstance(value, str) and value in PROFILE_IDS:
        return value
    if value is not None:
        logger.warning("[BehaviorPolicy] Unsupported profileId '{}', using natural", value)
    return "natural"


def _pause_strategy(value: Any) -> str:
    if isinstance(value, str) and value in PAUSE_STRATEGIES:
        return value
    if value is not None:
        logger.warning("[BehaviorPolicy] Unsupported pause strategy '{}', using idle_in_app", value)
    return "idle_in_app"


def _bool(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _optional_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _optional_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _optional_dict(value: Any) -> Optional[dict[str, Any]]:
    return value if isinstance(value, dict) else None
