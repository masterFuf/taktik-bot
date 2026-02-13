"""Page detection mixin for the TikTok Followers workflow.

Detects which page the UI is currently on:
video playback, user profile, story view, or followers list.
"""


class PageDetectionMixin:
    """Methods to detect the current page state in TikTok."""

    def _is_on_video_page(self) -> bool:
        """Check if we're currently on a video playback page.
        
        Unique elements on video page:
        - Like button with content-desc="Video liked" or "Like"
        - resource-id long_press_layout with content-desc="Video"
        - Share button with content-desc containing "Share video"
        """
        try:
            for selector in self.video_selectors.video_page_indicator:
                if self.device.xpath(selector).exists:
                    return True
            return False
        except Exception as e:
            self.logger.debug(f"Error checking video page: {e}")
            return False
    
    def _is_on_profile_page(self) -> bool:
        """Check if we're currently on a user profile page.
        
        Unique elements on profile page:
        - Username (@), stats labels, video grid, "No videos yet"
        """
        try:
            from .....ui.selectors import PROFILE_SELECTORS
            for selector in PROFILE_SELECTORS.profile_page_indicator:
                if self.device.xpath(selector).exists:
                    return True
            return False
        except Exception as e:
            self.logger.debug(f"Error checking profile page: {e}")
            return False
    
    def _is_on_story_page(self) -> bool:
        """Check if we're currently viewing a TikTok story.
        
        Needs at least 2 indicator matches to confirm (timestamp, close, follow, message input).
        """
        try:
            from .....ui.selectors import PROFILE_SELECTORS
            # Need at least 2 matches to confirm it's a story page
            matches = 0
            for selector in PROFILE_SELECTORS.story_page_indicator:
                if self.device.xpath(selector).exists:
                    matches += 1
                    if matches >= 2:
                        return True
            return False
        except Exception as e:
            self.logger.debug(f"Error checking story page: {e}")
            return False

    def _is_on_followers_list(self) -> bool:
        """Check if we're currently on the followers list page.
        
        Key differentiator: profile pages have qh5 (@username) which followers list doesn't.
        """
        try:
            from .....ui.selectors import PROFILE_SELECTORS
            # First, make sure we're NOT on a profile page
            if self.device.xpath(PROFILE_SELECTORS.username[0]).exists:
                return False
            
            # Check for followers list specific elements
            for selector in (self.followers_selectors.followers_tab_selected
                             + self.followers_selectors.followers_list):
                if self.device.xpath(selector).exists:
                    return True
            
            # Also check for Follow buttons with the followers-list resource-id
            if self.device.xpath(self.followers_selectors.follower_any_button[0]).exists:
                return True
            
            return False
        except Exception as e:
            self.logger.debug(f"Error checking followers list: {e}")
            return False
