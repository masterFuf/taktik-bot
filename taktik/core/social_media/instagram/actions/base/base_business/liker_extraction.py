"""Liker extraction — extract usernames from likers popup (regular post and reel)."""

from typing import Optional, List


class LikerExtractionMixin:
    """Mixin: extraction likers depuis popup (post régulier, reel, after click)."""

    def _extract_likers_after_click(self, max_interactions: int = None,
                                    multiply_by: int = 2) -> List[str]:
        """Extract usernames from likers popup after the like-count element has been clicked.
        
        Shared logic used by both regular post and reel extraction.
        """
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
