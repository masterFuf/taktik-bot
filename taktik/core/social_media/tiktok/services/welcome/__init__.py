"""TikTok new-follower welcome services: the decision, the guard, and the pass that runs them.

The three pieces are deliberately separate. `decision` is pure policy, `duplicate_guard` is the
only thing allowed to say whether someone may be written to, and `runner` walks a list without
ever acting on it. Acting (follow back, send) stays with the workflows and the bridge that own
the device.
"""

from taktik.core.social_media.tiktok.services.welcome.decision import (
    WelcomeDecision,
    WelcomePolicy,
    decide_for_new_follower,
    follow_back_targets,
    parse_welcome_policy,
    summarize,
    welcome_dm_targets,
)
from taktik.core.social_media.tiktok.services.welcome.duplicate_guard import (
    CLEAR,
    CONTACTED,
    UNKNOWN,
    WelcomeDmGuard,
)
from taktik.core.social_media.tiktok.services.welcome.runner import NewFollowerWelcomePass

__all__ = [
    "CLEAR",
    "CONTACTED",
    "NewFollowerWelcomePass",
    "UNKNOWN",
    "WelcomeDecision",
    "WelcomeDmGuard",
    "WelcomePolicy",
    "decide_for_new_follower",
    "follow_back_targets",
    "parse_welcome_policy",
    "summarize",
    "welcome_dm_targets",
]
