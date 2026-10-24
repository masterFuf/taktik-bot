"""Scroll actions facade - backward-compatible ScrollActions class."""

from loguru import logger

from taktik.core.social_media.instagram.actions.base.base_action import BaseAction
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.shared.behavior.session_state import BehaviorSessionState

from taktik.core.social_media.instagram.actions.atomic.scroll.base_scroll import BaseScrollMixin
from taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll import FeedScrollMixin
from taktik.core.social_media.instagram.actions.atomic.scroll.context_scroll import ContextScrollMixin


class ScrollActions(
    BaseScrollMixin,
    FeedScrollMixin,
    ContextScrollMixin
):
    """
    Facade composing all scroll mixins.

    Sub-modules:
    - base_scroll.py      - Generic directional scrolls + the shared humanized gesture primitives
                            (GestureMixin: real-fling flick / 1:1 drag) via inheritance.
    - feed_scroll.py      - Intelligent feed scroll: advance-to-next-post, framing, stop-on-metadata,
                            reading (caption/carousel), ad/suggested skip, browse session.
    - context_scroll.py   - Context-specific scrolls (followers, comments, feed, grid) + load more + smart scroll
    """
    
    def __init__(self, device, behavior_state=None):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-scroll-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        # Standalone/Lab callers get an isolated in-memory state. Workflow callers inject the
        # SessionManager-owned instance so every ScrollActions facade on that device shares one
        # coherent history without a cross-device singleton.
        self.behavior_state = behavior_state or BehaviorSessionState()
        

    # Every scroll is computed in proportion of the screen: its size is read, never made up
    # (`get_screen_size` raises when neither uiautomator2 nor `wm size` gives it), and read when a
    # gesture first needs it, not when the actions are built: Android 17 refuses uiautomator2's
    # deviceInfo on the first calls of a run, where the size was taken for 1080 x 1920 for good.
    # The facade keeps it once read. A host that knows the size (a replayed capture) sets it.
    # The mixins declare `screen_width` / `screen_height` as what their host gives: these
    # properties give it.

    @property
    def screen_width(self) -> int:
        width = self.__dict__.get("_screen_width")
        return int(width) if width is not None else self.device.get_screen_size()[0]

    @screen_width.setter
    def screen_width(self, value: int) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        self.__dict__["_screen_width"] = value

    @property
    def screen_height(self) -> int:
        height = self.__dict__.get("_screen_height")
        return int(height) if height is not None else self.device.get_screen_size()[1]

    @screen_height.setter
    def screen_height(self, value: int) -> None:  # pyright: ignore[reportIncompatibleVariableOverride]
        self.__dict__["_screen_height"] = value


__all__ = ['ScrollActions']
