"""Liker extraction — extract usernames from likers popup (regular post and reel)."""

import time
from typing import TYPE_CHECKING, Any, Callable, Optional, List

if TYPE_CHECKING:
    from taktik.core.social_media.instagram.ui.extractors import InstagramUIExtractors

#: How long the likers sheet may take to come up after the tap on a like counter before the reading
#: refuses (seconds), and how often it looks meanwhile.
LIKERS_SHEET_ARRIVAL_S = 3.0
LIKERS_SHEET_POLL_S = 0.5


class LikerExtractionMixin:
    """Mixin: extraction likers depuis popup (post régulier, reel, after click)."""

    # What the host (`BaseBusinessAction`) gives, declared here as an interface would be.
    ui_extractors: "InstagramUIExtractors"
    logger: Any
    automation: Any
    _is_likers_popup_open: Callable[[], bool]
    _close_likers_popup: Callable[[], None]

    def _extract_likers_after_click(self, max_interactions: int = None,
                                    multiply_by: int = 2) -> List[str]:
        """Extract usernames from likers popup after the like-count element has been clicked.

        Shared logic used by both regular post and reel extraction, and the Lab's `post.read_likers`.
        The likers popup must be on screen (`_likers_sheet_arrived`): without it, nothing is read and
        no scroll is made, an empty list and a warning. Every scroll of the reading drags the sheet;
        on any other screen it drags the post list under it (Pixel 6 Pro, Instagram 410: ten drags
        down a profile's posts for "0 liker(s)").
        """
        if not self._likers_sheet_arrived():
            self.logger.warning("⚠️ No likers popup on screen: no liker read, no scroll")
            return []
        if max_interactions is None:
            max_interactions = getattr(self, 'current_max_interactions', 
                                      self.default_config.get('max_interactions', 20))
        
        target_users = max_interactions * multiply_by
        
        if hasattr(self, 'current_max_interactions'):
            original_max = self.current_max_interactions
            self.current_max_interactions = target_users
            likers = self.ui_extractors.extract_usernames_from_likers_popup(
                current_max_interactions_attr=target_users,
                automation=self.automation,
                logger_instance=self.logger,
                add_initial_sleep=False
            )
            self.current_max_interactions = original_max
        else:
            likers = self.ui_extractors.extract_usernames_from_likers_popup(
                max_interactions=target_users,
                automation=self.automation,
                logger_instance=self.logger,
                add_initial_sleep=True
            )
        
        self._close_likers_popup()
        return likers

    def _likers_sheet_arrived(self) -> bool:
        """Is the likers popup on screen (`_is_likers_popup_open`), within `LIKERS_SHEET_ARRIVAL_S`
        of the tap that asked for it."""
        looks = int(LIKERS_SHEET_ARRIVAL_S / LIKERS_SHEET_POLL_S) + 1
        for look in range(looks):
            if self._is_likers_popup_open():
                return True
            if look < looks - 1:
                time.sleep(LIKERS_SHEET_POLL_S)
        return False

    def _extract_likers_from_regular_post(self, max_interactions: int = None, 
                                         multiply_by: int = 2) -> List[str]:
        try:
            like_count_element = self.ui_extractors.find_like_count_element(logger_instance=self.logger)
            if not like_count_element:
                self.logger.warning("⚠️ Like count not found")
                return []
            
            self.logger.debug("👆 Clicking on like count")
            like_count_element.click()
            self._human_like_delay('popup_open')
            
            return self._extract_likers_after_click(max_interactions, multiply_by)
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting likers from regular post: {e}")
            return []
    
    def _extract_likers_from_reel(self, max_interactions: int = None, 
                                 multiply_by: int = 2) -> List[str]:
        try:
            like_element = None
            found_selector = None
            
            for selector in self.post_selectors.reel_like_selectors:
                try:
                    elements = self.device.xpath(selector).all()
                    if not elements:
                        continue
                    
                    for element in elements:
                        text = element.get_text() if hasattr(element, 'get_text') else (
                            element.text if hasattr(element, 'text') else ""
                        )
                        
                        if text and self.ui_extractors.is_like_count_text(text):
                            like_element = element
                            found_selector = selector
                            self.logger.info(f"✅ Reel like count found: '{text}' via {selector}")
                            break
                    
                    if like_element:
                        break
                        
                except Exception as e:
                    self.logger.debug(f"Error testing selector {selector}: {e}")
                    continue
            
            if not like_element:
                self.logger.warning("⚠️ Reel like count not found with any selector")
                return []
            
            like_element.click()
            self._human_like_delay('popup_open')
            
            return self._extract_likers_after_click(max_interactions, multiply_by)
            
        except Exception as e:
            self.logger.error(f"❌ Error extracting likers from Reel: {e}")
            return []
