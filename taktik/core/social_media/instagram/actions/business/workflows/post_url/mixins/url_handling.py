"""URL validation, post metadata extraction, and author extraction for post_url workflow."""

import re
import time
from typing import Dict, Any, Optional


class PostUrlHandlingMixin:
    """Mixin: validate URLs, extract post metadata, extract author username."""
    
    def _validate_instagram_url(self, url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        
        instagram_patterns = [
            r'https?://(www\.)?instagram\.com/p/[A-Za-z0-9_-]+/?',
            r'https?://(www\.)?instagram\.com/reel/[A-Za-z0-9_-]+/?',
            r'https?://(www\.)?instagram\.com/tv/[A-Za-z0-9_-]+/?'
        ]
        
        for pattern in instagram_patterns:
            if re.match(pattern, url.strip()):
                self.logger.debug(f"Valid URL detected: {pattern}")
                return True
        
        self.logger.debug(f"Invalid URL: {url}")
        return False
    
    def _extract_author_username(self) -> Optional[str]:
        try:
            # PRIORITY 1: Try extracting from Reel-specific content-desc (e.g., "Reel by username")
            try:
                reel_container = self.device.xpath(self._hashtag_sel.reel_author_container[0])
                if reel_container.exists:
                    content_desc = reel_container.info.get('contentDescription', '')
                    self.logger.debug(f"Reel container content-desc: '{content_desc}'")
                    username_match = re.search(r'Reel by ([a-zA-Z0-9_.]+)', content_desc)
                    if username_match:
                        username = username_match.group(1)
                        if self._is_valid_username(username):
                            self.logger.debug(f"Username found from Reel content-desc: @{username}")
                            return username
            except Exception as e:
                self.logger.debug(f"Error extracting from Reel content-desc: {e}")
            
            # PRIORITY 2: Try extracting from profile image content-desc (works for both posts and Reels)
            for selector in self.post_selectors.profile_image_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element_info = element.info
                        content_desc = element_info.get('contentDescription', '')
                        self.logger.debug(f"Profile image content-desc: '{content_desc}'")
                        if content_desc:
                            # Try French format first
                            username_match = re.search(r'Photo de profil de ([a-zA-Z0-9_.]+)', content_desc)
                            if not username_match:
                                # Try English format (for Reels)
                                username_match = re.search(r'Profile picture of ([a-zA-Z0-9_.]+)', content_desc)
                            if username_match:
                                username = username_match.group(1)
                                self.logger.debug(f"Extracted username from profile image: '{username}'")
                                if self._is_valid_username(username):
                                    self.logger.debug(f"Username found from profile image: @{username}")
                                    return username
                except Exception as e:
                    self.logger.debug(f"Error with profile image selector {selector}: {e}")
                    continue
            
            for selector in self.post_selectors.header_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element_info = element.info
                        content_desc = element_info.get('contentDescription', '')
                        self.logger.debug(f"Header content-desc: '{content_desc}'")
                        if content_desc:
                            username_match = re.match(r'^([a-zA-Z0-9_.]+)', content_desc)
                            if username_match:
                                username = username_match.group(1)
                                self.logger.debug(f"Extracted potential username: '{username}'")
                                if self._is_valid_username(username):
                                    self.logger.debug(f"Username found from header: @{username}")
                                    return username
                except Exception as e:
                    self.logger.debug(f"Error with header selector {selector}: {e}")
                    continue
            
            for selector in self.post_selectors.username_extraction_selectors:
                try:
                    text = self._get_text_from_element(selector)
                    if text and self._is_valid_username(text.lstrip('@')):
                        username = text.strip().lstrip('@')
                        self.logger.debug(f"Username found from text: @{username}")
                        return username
                except Exception as e:
                    self.logger.debug(f"Error with text selector {selector}: {e}")
                    continue
            
            self.logger.warning("Author username not found")
            return None
            
        except Exception as e:
            self.logger.error(f"Error extracting username: {e}")
            return None
    
    # _is_valid_username is inherited from BaseBusinessAction (delegates to ui_extractors)

    def _validate_interaction_limits(self, post_metadata: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        return self._validate_resource_limits(
            available=post_metadata.get('likes_count', 0),
            requested=config.get('max_interactions', 20),
            resource_name="likes"
        )
    
    def _calculate_adaptive_tolerance(self, target_likes: int) -> int:
        """
        Calculate adaptive tolerance based on post popularity.
        
        Strategy:
        - Small posts (<500 likes): ±5 likes tolerance (~1-5%)
        - Medium posts (500-2000): ±15 likes tolerance (~1-3%)
        - Popular posts (2000-10000): ±50 likes tolerance (~0.5-2.5%)
        - Viral posts (10000-50000): ±100 likes tolerance (~0.2-1%)
        - Mega viral (>50000): ±200 likes tolerance (~0.4%)
        """
        if target_likes < 500:
            return 5
        elif target_likes < 2000:
            return 15
        elif target_likes < 10000:
            return 50
        elif target_likes < 50000:
            return 100
        else:
            return 200
