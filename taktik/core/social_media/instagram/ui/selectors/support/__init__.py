"""Instagram selector support modules."""

from taktik.core.social_media.instagram.ui.selectors.support.debug import DebugSelectors, DEBUG_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.support.scroll import ScrollSelectors, SCROLL_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.support.text_reading import TextReadingSelectors, TEXT_READING_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.support.watchdog import WatchdogSelectors, WATCHDOG_SELECTORS

__all__ = [
    "DEBUG_SELECTORS",
    "SCROLL_SELECTORS",
    "TEXT_READING_SELECTORS",
    "WATCHDOG_SELECTORS",
    "DebugSelectors",
    "ScrollSelectors",
    "TextReadingSelectors",
    "WatchdogSelectors",
]
