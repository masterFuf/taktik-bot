"""Shared behavior contracts and the cross-platform humanization toolkit.

- `policy`: optional behavior-policy payload parsing (opt-in; standalone-safe).
- `gesture`: human swipe-trajectory sampler + recorded calibration (`sample_swipe`, …).
- `gesture_primitives`: `GestureMixin` — real-fling flick / 1:1 drag / curved swipe input.
- `dwell`: content-aware dwell model (`content_dwell`, `caption_prose_chars`).

Reusable by every platform (Instagram feed, TikTok, …); platform-specific perception/selectors
stay in `social_media/<platform>`.
"""

from .policy import BehaviorPolicy, PausePolicy, ResumePolicy, parse_behavior_policy
from .gesture import sample_swipe, sample_burst_gap, sample_reading_pause, load_calibration
from .gesture_primitives import GestureMixin
from .dwell import content_dwell, caption_prose_chars

__all__ = [
    "BehaviorPolicy",
    "PausePolicy",
    "ResumePolicy",
    "parse_behavior_policy",
    "sample_swipe",
    "sample_burst_gap",
    "sample_reading_pause",
    "load_calibration",
    "GestureMixin",
    "content_dwell",
    "caption_prose_chars",
]
