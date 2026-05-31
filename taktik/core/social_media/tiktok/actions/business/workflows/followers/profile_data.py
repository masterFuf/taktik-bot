"""Profile data extraction mixin for the TikTok Followers workflow.

Extracts username, display name, stats, bio from profile pages
and saves to the local database.
"""

class ProfileDataMixin:
    """Methods for extracting and persisting TikTok profile data."""

    def _get_current_profile_username(self) -> str:
        """Extract the username from the current profile page."""
        try:
            from taktik.core.social_media.tiktok.services.profile.username import (
                get_current_profile_username,
            )

            return get_current_profile_username(self.device)
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
            posts = []
            for sel in self.followers_selectors.profile_post_item:
                posts = self.device.xpath(sel).all()
                if posts:
                    break
            if posts:
                profile_data['videos_count'] = len(posts)
            
            try:
                saved = self._followers_repository.save_profile(
                    account_id=self._account_id,
                    profile_data=profile_data,
                )
                if saved:
                    self.logger.debug(f"📊 Saved profile data for @{self._current_profile_username}: "
                                     f"{profile_data['followers_count']} followers, "
                                     f"{profile_data['likes_count']} likes")
            except Exception as e:
                self.logger.debug(f"Error saving profile data: {e}")
                    
        except Exception as e:
            self.logger.debug(f"Error extracting profile data: {e}")
