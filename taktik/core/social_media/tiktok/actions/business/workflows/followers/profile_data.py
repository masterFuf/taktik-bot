"""Profile data extraction mixin for the TikTok Followers workflow.

Extracts username, display name, stats, bio from profile pages
and saves to the local database.
"""


class ProfileDataMixin:
    """Methods for extracting and persisting TikTok profile data."""

    def _get_current_profile_username(self) -> str:
        """Extract the username from the current profile page."""
        try:
            from .....ui.selectors import PROFILE_SELECTORS
            # Try to find username element on profile (starts with @)
            for selector in PROFILE_SELECTORS.username:
                username_elem = self.device.xpath(selector)
                if username_elem.exists:
                    text = username_elem.get_text()
                    if text:
                        return text.lstrip('@')
            
            # Fallback: try content-desc
            username_elem = self.device.xpath('//*[contains(@content-desc, "@")]')
            if username_elem.exists:
                desc = username_elem.info.get('contentDescription', '')
                if '@' in desc:
                    parts = desc.split('@')
                    if len(parts) > 1:
                        return parts[1].split()[0]
                        
        except Exception as e:
            self.logger.debug(f"Error getting profile username: {e}")
        
        return "unknown"
    
    def _extract_and_save_profile_data(self):
        """Extract profile data from the current profile page and save to database.
        
        Uses the shared extract_profile_from_screen utility for data extraction,
        then enriches with video count and saves to the local database.
        """
        if not self._current_profile_username or self._current_profile_username == "unknown":
            return
        
        try:
            from .._internal.profile_extractor import extract_profile_from_screen
            
            # Get raw uiautomator2 device for the shared extractor
            raw_device = self.device._device if hasattr(self.device, '_device') else self.device
            
            extracted = extract_profile_from_screen(raw_device, self._current_profile_username)
            if not extracted:
                return
            
            # Map to DB schema (bio → biography, display_name stays)
            profile_data = {
                'username': extracted.get('username', self._current_profile_username),
                'display_name': extracted.get('display_name') or None,
                'followers_count': extracted.get('followers_count', 0),
                'following_count': extracted.get('following_count', 0),
                'likes_count': extracted.get('likes_count', 0),
                'videos_count': 0,
                'biography': extracted.get('bio') or None,
                'is_private': extracted.get('is_private', False),
                'is_verified': extracted.get('is_verified', False),
            }
            
            # Count visible videos in profile grid (followers-specific)
            posts = self.device.xpath(self.followers_selectors.profile_post_item[0]).all()
            if posts:
                profile_data['videos_count'] = len(posts)
            
            # Save to database
            if self._db and self._account_id:
                try:
                    self._db.get_or_create_tiktok_profile(profile_data)
                    self.logger.debug(f"📊 Saved profile data for @{self._current_profile_username}: "
                                     f"{profile_data['followers_count']} followers, "
                                     f"{profile_data['likes_count']} likes")
                except Exception as e:
                    self.logger.debug(f"Error saving profile data: {e}")
                    
        except Exception as e:
            self.logger.debug(f"Error extracting profile data: {e}")
