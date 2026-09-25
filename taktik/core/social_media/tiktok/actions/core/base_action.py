import time
import random
from typing import Optional, Dict, Any, List, Union
from loguru import logger

from .device_facade import DeviceFacade
from .utils import ActionUtils

from taktik.core.shared.actions.base_action import SharedBaseAction
from taktik.core.shared.device.snapshot import SnapshotUnavailable

# Re-export for backward compatibility (some files import these from here)
TAKTIK_KEYBOARD_PKG = 'com.alexal1.adbkeyboard'


def _photo_of(screen):
    """A `TikTokScreen` carries its photo (None when the screen could not be read); a photo is its
    own."""
    return getattr(screen, "photo", screen)


class BaseAction(SharedBaseAction):
    """Base class for all TikTok actions.
    
    Inherits shared functionality (element finding, clicking, waiting,
    Taktik Keyboard, delays) from SharedBaseAction.
    
    Adds TikTok-specific:
    - video_watch delay type
    - _element_exists with timeout (polling variant)
    - _get_element_text with timeout (polling variant)
    - _input_text (click + clear + type)
    - _scroll_up / _scroll_down
    - _swipe_to_next_video / _swipe_to_previous_video
    - _double_tap_to_like
    - _close_popup
    """
    
    _device_facade_class = DeviceFacade
    _platform = "tiktok"
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module=f"tiktok.actions.{self.__class__.__name__.lower()}")
        self.utils = ActionUtils()
    
    def _human_like_delay(self, action_type: str = 'general') -> None:
        """Add human-like delay based on action type (with TikTok video_watch)."""
        delays = {
            'click': (0.2, 0.5),      
            'navigation': (0.7, 1.5),  
            'scroll': (0.3, 0.7),      
            'typing': (0.08, 0.15),    
            'video_watch': (2.0, 5.0),
            'default': (0.3, 0.8)      
        }
        
        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay)
    
    # =========================================================================
    # TikTok-specific: element methods with polling timeout, one screen photo per turn
    #
    # Each turn asks every selector of ONE photo of the screen (`device.snapshot()`, the code
    # `d.xpath()` runs, on one dump) instead of one dump per selector; the timeout, the pause
    # between turns and "the first selector that answers" are unchanged. Handed `screen` (a photo
    # already taken for this decision, or the `TikTokScreen` that carries it), they answer on it
    # at once and never wait.
    # =========================================================================

    def _turn_photo(self):
        """This turn's photo, or None when the screen could not be read: a failed dump finds
        nothing this turn, as every probe of a failed `d.xpath()` found nothing."""
        try:
            return self.device.snapshot()
        except SnapshotUnavailable:
            return None

    def _element_exists(self, selectors: Union[List[str], str], timeout: float = 2.0,
                        screen=None) -> bool:
        """Is one of `selectors` on screen? Polls until `timeout` unless handed `screen`."""
        if isinstance(selectors, str):
            selectors = [selectors]
        if screen is not None:
            return self._found_on(_photo_of(screen), selectors)

        start_time = time.time()

        while time.time() - start_time < timeout:
            if self._found_on(self._turn_photo(), selectors):
                return True
            time.sleep(0.3)
        
        return False

    def _get_element_text(self, selectors: Union[List[str], str], timeout: float = 5.0,
                          screen=None) -> Optional[str]:
        """The first non-empty text of `selectors`. Polls until `timeout` unless handed `screen`."""
        if isinstance(selectors, str):
            selectors = [selectors]
        if screen is not None:
            return self._text_on(_photo_of(screen), selectors)

        start_time = time.time()
        
        while time.time() - start_time < timeout:
            text = self._text_on(self._turn_photo(), selectors)
            if text is not None:
                return text
            time.sleep(0.5)
        
        return None

    def _get_element_content_desc(self, selectors: Union[List[str], str], timeout: float = 3.0,
                                  screen=None) -> Optional[str]:
        """The first non-empty content-desc of `selectors`. Polls until `timeout` unless handed
        `screen`.

        Used for TikTok Trill variant where counts/usernames are in content-desc
        rather than text nodes (e.g. 'Like video. 2 likes', 'username profile').
        """
        if isinstance(selectors, str):
            selectors = [selectors]
        if screen is not None:
            return self._content_desc_on(_photo_of(screen), selectors)

        start_time = time.time()

        while time.time() - start_time < timeout:
            desc = self._content_desc_on(self._turn_photo(), selectors)
            if desc is not None:
                return desc
            time.sleep(0.3)

        return None

    # What `d.xpath(selector)` answered, asked of one photo: the first selector that finds an
    # element wins, and what is read is that selector's FIRST element (`get_text()`, `get()`).
    # An invalid selector is skipped, as the per-selector loops skipped it.

    @staticmethod
    def _found_on(photo, selectors: List[str]) -> bool:
        if photo is None:
            return False
        for selector in selectors:
            try:
                if photo.elements(selector):
                    return True
            except Exception:
                continue
        return False

    def _text_on(self, photo, selectors: List[str]) -> Optional[str]:
        if photo is None:
            return None
        for selector in selectors:
            try:
                found = photo.elements(selector)
                if found:
                    text = found[0].text
                    if text:
                        return text.strip()
            except Exception as e:
                self.logger.debug(f"Error getting text from {selector[:50]}: {e}")
                continue
        return None

    def _content_desc_on(self, photo, selectors: List[str]) -> Optional[str]:
        if photo is None:
            return None
        for selector in selectors:
            try:
                found = photo.elements(selector)
                if found:
                    desc = found[0].attrib.get('content-desc', '')
                    if desc:
                        return desc.strip()
            except Exception as e:
                self.logger.debug(f"Error getting content-desc from {selector[:50]}: {e}")
                continue
        return None

    def _input_text(self, selectors: Union[List[str], str], text: str, 
                   timeout: float = 5.0, clear_first: bool = True) -> bool:
        """Input text into element using Taktik Keyboard."""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        start_time = time.time()
        last_error = None  # a field never found, without any error, reached the report unbound

        while time.time() - start_time < timeout:
            for selector in selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        # Click to focus first
                        element.click()
                        time.sleep(0.3)
                        
                        if clear_first:
                            # Clear using Taktik Keyboard
                            self._clear_text_with_taktik_keyboard()
                            time.sleep(0.2)
                        
                        # Use Taktik Keyboard for reliable text input
                        if not self._type_with_taktik_keyboard(text):
                            self.logger.warning("Taktik Keyboard failed, falling back to send_keys")
                            self.device.send_keys(text)
                        
                        self._human_like_delay('typing')
                        return True
                except Exception as e:
                    last_error = e
                    self.logger.debug(f"Error inputting text to {selector[:50]}: {e}")
                    continue

            time.sleep(0.5)

        # Say WHY, not just that it failed. Every attempt is swallowed and retried above, so a
        # raising keyboard and a missing field produced the same line — and the real cause, an
        # Android API the agent calls that no longer exists, stayed invisible for a whole
        # timeout's worth of retries.
        if last_error is not None:
            self.logger.warning(f"Failed to input text after {timeout}s — last error: {last_error}")
        else:
            self.logger.warning(f"Failed to input text after {timeout}s — field never found")
        return False
    
    # =========================================================================
    # TikTok-specific: scroll & video navigation
    # =========================================================================
    
    def _scroll_up(self, scale: float = 0.8):
        """Scroll up (swipe down)."""
        self.device.swipe_down(scale)
        self._human_like_delay('scroll')
    
    def _scroll_down(self, scale: float = 0.8):
        """Scroll down (swipe up)."""
        self.device.swipe_up(scale)
        self._human_like_delay('scroll')
    
    def _advance_mode(self, context: str) -> bool:
        """Should this feed advance COAST (flick) or be dragged? True = flick.

        The For You feed is a snapping pager: it lands on exactly one video whether it was flicked
        past or dragged up, so both are safe here -- which is what makes it the one surface where
        the gesture KIND can vary. Lists are not: a fling overshoots them, and the extractors that
        count one scroll as one row would read the wrong one. So this is asked on the feed only.

        Every advance being the same kind of gesture is the coarsest rhythm there is; a person
        flicks through a boring stretch and drags deliberately through an interesting one, in
        runs, not by independent coin toss. `choose_scroll_mode` is where that run lives.
        """
        state = getattr(self, "behavior_state", None)
        if state is None or not hasattr(state, "choose_scroll_mode"):
            return True
        try:
            return state.choose_scroll_mode(context=context)["mode"] != "drag"
        except Exception:
            return True

    def _swipe_to_next_video(self):
        """Advance one video — a fling, or sometimes a deliberate drag.

        Both land on the next video because the feed is a snapping pager; which one happens
        follows the session's current style rather than being fixed for the whole run."""
        self.device.swipe_up(scale=0.8, coast=self._advance_mode("tiktok_feed_advance"), pager=True)
        self._human_like_delay('scroll')

    def _swipe_to_previous_video(self):
        """Go back one video — same pager, same choice of gesture."""
        self.device.swipe_down(scale=0.8, coast=self._advance_mode("tiktok_feed_back"), pager=True)
        self._human_like_delay('scroll')
    
    def _double_tap_to_like(self):
        """Double-tap the video to like it — HUMANIZED. Samples a jittered point in the central
        video area (never the exact screen centre twice) via the shared humanization engine,
        staying clear of the right-side action buttons (x>0.8) and the top/bottom bars."""
        width, height = self.device.get_screen_size()
        bounds = (int(width * 0.25), int(height * 0.30), int(width * 0.75), int(height * 0.70))
        self.device.human_double_tap(bounds)
        self._human_like_delay('click')
    
    def _press_back(self):
        """Press back button."""
        self.device.press_back()
        self._human_like_delay('navigation')
    
    def _close_popup(self) -> bool:
        """Try to close any popup."""
        from ...ui.selectors.shell.popups import POPUP_SELECTORS
        
        if self._find_and_click(POPUP_SELECTORS.close_button, timeout=2):
            self.logger.debug("✅ Popup closed")
            return True
        
        if self._find_and_click(POPUP_SELECTORS.dismiss_button, timeout=2):
            self.logger.debug("✅ Popup dismissed")
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get action statistics."""
        return {
            'class': self.__class__.__name__,
            'stats': self._method_stats.copy()
        }
