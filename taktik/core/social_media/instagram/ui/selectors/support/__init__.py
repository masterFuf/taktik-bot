"""Instagram selector support modules."""

from .debug import DebugSelectors, DEBUG_SELECTORS
from .scroll import ScrollSelectors, SCROLL_SELECTORS
from .watchdog import WatchdogSelectors, WATCHDOG_SELECTORS

__all__ = [
    "DEBUG_SELECTORS",
    "SCROLL_SELECTORS",
    "WATCHDOG_SELECTORS",
    "DebugSelectors",
    "ScrollSelectors",
    "WatchdogSelectors",
]
