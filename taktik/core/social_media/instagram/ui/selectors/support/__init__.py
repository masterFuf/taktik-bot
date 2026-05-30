"""Instagram selector support modules."""

from .debug import DebugSelectors, DEBUG_SELECTORS
from .scroll import ScrollSelectors, SCROLL_SELECTORS

__all__ = [
    "DEBUG_SELECTORS",
    "SCROLL_SELECTORS",
    "DebugSelectors",
    "ScrollSelectors",
]
