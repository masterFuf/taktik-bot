"""Threads workflows (search/interact, feed/interact, follow, posting, ...).

Concrete workflows are added incrementally as UI selectors are captured from
real devices.
"""

from .feed_and_interact import (
    FeedInteractConfig,
    run_feed_and_interact,
)
from .search_and_interact import (
    ActionProbabilities,
    InteractStats,
    ProfileFilters,
    SearchInteractConfig,
    run_search_and_interact,
)
from .agent_handler import (
    THREADS_AUTOMATION_WORKFLOW_IDS,
    THREADS_FEED_WORKFLOW_ID,
    THREADS_FOLLOW_WORKFLOW_ID,
    THREADS_TARGET_WORKFLOW_ID,
    register_threads_automation_handlers,
)

__all__ = [
    "ActionProbabilities",
    "FeedInteractConfig",
    "InteractStats",
    "ProfileFilters",
    "SearchInteractConfig",
    "THREADS_AUTOMATION_WORKFLOW_IDS",
    "THREADS_FEED_WORKFLOW_ID",
    "THREADS_FOLLOW_WORKFLOW_ID",
    "THREADS_TARGET_WORKFLOW_ID",
    "register_threads_automation_handlers",
    "run_feed_and_interact",
    "run_search_and_interact",
]
