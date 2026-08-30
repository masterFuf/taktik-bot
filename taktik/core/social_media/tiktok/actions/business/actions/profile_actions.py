"""
TikTok Profile Actions
Actions for interacting with TikTok profiles, including fetching own profile info.
"""

from dataclasses import dataclass
from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ...core.utils import parse_count
from ....ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from ....ui.labels import classify_profile_stat_label


@dataclass
class TikTokProfileInfo:
    """Information about a TikTok profile."""
    username: str  # @username without the @
    display_name: Optional[str] = None
    following_count: int = 0
    followers_count: int = 0
    likes_count: int = 0
    bio: Optional[str] = None
    #: `data:image/jpeg;base64,...` cropped off the profile page, or None. TikTok exposes no URL
    #: for it, so a picture only exists if a screenshot was taken while the profile was up.
    profile_pic_base64: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'username': self.username,
            'display_name': self.display_name,
            'following_count': self.following_count,
            'followers_count': self.followers_count,
            'likes_count': self.likes_count,
            'bio': self.bio,
            'profile_pic_base64': self.profile_pic_base64,
        }


class ProfileActions(BaseAction):
    """Actions for TikTok profile interactions.
    
    Uses scoped selectors from ui/selectors/shell and ui/selectors/surfaces.
    """
    
    def navigate_to_own_profile(self) -> bool:
        """Navigate to the user's own profile page.

        The verification only accepts markers that exist on OUR profile and nowhere else.
        It used to fall back on "a username is visible", which is true on every profile in the
        app: a tap that landed on somebody else's page passed, and `get_own_profile_info` then
        recorded THEIR follower count as the bot's own. Measured 2026-08-29 while capturing the
        own lists — the probe walked away with a stranger's 235 K followers.

        Two anchors, measured on both shipped versions (1 on our profile, 0 on a stranger's):
        the profile menu, and the edit button where it exists. `username` is deliberately not a
        third chance — it fires for everyone, which is the whole problem.

        Returns:
            True if we are standing on OUR profile, False otherwise.
        """
        logger.info("📱 Navigating to own profile...")

        if self._find_and_click(NAVIGATION_SELECTORS.profile_tab, timeout=5.0):
            self._random_sleep(1.5, 2.5)

            try:
                if self._element_exists(PROFILE_SELECTORS.edit_profile_button, timeout=2):
                    logger.info("✅ Successfully navigated to own profile (Edit button found)")
                    return True

                # `edit_profile_button` is `@text="Modifier"`, which reads 0 on 46.6.3 FR; the
                # profile menu is what survives there.
                if self._element_exists(PROFILE_SELECTORS.profile_menu_button, timeout=2):
                    logger.info("✅ Successfully navigated to own profile (profile menu found)")
                    return True

                if self._element_exists(PROFILE_SELECTORS.username, timeout=1):
                    logger.warning(
                        "❌ On a profile, but not ours — no owner marker found. Refusing rather "
                        "than reading somebody else's numbers as the bot's."
                    )
                    return False
            except Exception as e:
                logger.debug(f"Verification failed: {e}")

        logger.warning("❌ Could not navigate to profile page")
        return False
    
    def get_own_profile_info(self) -> Optional[TikTokProfileInfo]:
        """Get information about the user's own profile.
        
        Must be on the profile page first (call navigate_to_own_profile).
        
        Returns:
            TikTokProfileInfo if successful, None otherwise.
        """
        logger.info("📊 Fetching own profile info...")
        
        username = None
        display_name = None
        following_count = 0
        followers_count = 0
        likes_count = 0
        bio = None
        
        # The bio. It was declared and never read -- initialised to None at the top of this
        # method and handed straight to the dataclass, so every own-profile fetch since the
        # beginning reported an empty bio for an account that has one. It only became visible
        # once the field started travelling to the front.
        try:
            bio = self._get_element_text(PROFILE_SELECTORS.bio_text, timeout=3) or None
            if bio:
                logger.debug(f"Found bio: {bio[:40]}...")
        except Exception as e:
            logger.debug(f"Failed to get bio: {e}")

        # Get username using centralized selectors
        try:
            text = self._get_element_text(PROFILE_SELECTORS.username, timeout=3)
            if text:
                username = text.lstrip('@').strip()
                logger.debug(f"Found username: @{username}")
        except Exception as e:
            logger.debug(f"Failed to get username: {e}")
        
        if not username:
            logger.warning("❌ Could not find username on profile page")
            return None
        
        # Get display name
        try:
            display_name = self._get_element_text(PROFILE_SELECTORS.display_name, timeout=3)
            if display_name:
                logger.debug(f"Found display name: {display_name}")
        except Exception as e:
            logger.debug(f"Failed to get display name: {e}")
        
        # Get stats (Following, Followers, Likes) - use specific selectors based on UI dump
        # The stats are in a row with value above label
        try:
            # Get all stat values (they share the same resource-id)
            # Try each selector until we find results (handles musically vs trill package)
            stat_values = []
            for sel in PROFILE_SELECTORS.stat_value:
                stat_values = self.device.xpath(sel).all()
                if stat_values:
                    break

            stat_labels = []
            for sel in PROFILE_SELECTORS.stat_label:
                stat_labels = self.device.xpath(sel).all()
                if stat_labels:
                    break

            logger.debug(f"Found {len(stat_values)} stat values and {len(stat_labels)} stat labels")
            
            for i, label_elem in enumerate(stat_labels):
                try:
                    # XMLElement uses .text property, not .get_text() method
                    label_text = label_elem.text or ''

                    if i < len(stat_values):
                        value_text = stat_values[i].text or '0'
                        count = parse_count(value_text)

                        # Which of the three stats is this? The row is paired by position
                        # (language-neutral resource-ids), but the ANSWER is in the label —
                        # and it used to be compared against English words, so a French
                        # profile reported zero followers, following AND likes in silence.
                        stat = classify_profile_stat_label(label_text)
                        if stat == 'following':
                            following_count = count
                            logger.debug(f"Found following: {count}")
                        elif stat == 'followers':
                            followers_count = count
                            logger.debug(f"Found followers: {count}")
                        elif stat == 'likes':
                            likes_count = count
                            logger.debug(f"Found likes: {count}")
                except Exception as e:
                    logger.debug(f"Failed to parse stat {i}: {e}")
        except Exception as e:
            logger.debug(f"Failed to get stats: {e}")
        
        # The picture, while the profile is still on screen -- it cannot be fetched later, because
        # TikTok gives no URL for it and the crop only exists where the pixels are.
        profile_pic_base64 = None
        try:
            from taktik.core.social_media.tiktok.actions.atomic.avatar_actions import AvatarActions

            profile_pic_base64 = AvatarActions(self.device).capture_own_avatar()
        except Exception as e:
            logger.debug(f"Failed to capture the avatar: {e}")

        profile_info = TikTokProfileInfo(
            username=username,
            display_name=display_name,
            following_count=following_count,
            followers_count=followers_count,
            likes_count=likes_count,
            bio=bio,
            profile_pic_base64=profile_pic_base64,
        )
        
        logger.info(f"✅ Profile info: @{username} ({display_name}) - {followers_count} followers")
        return profile_info
    
    def navigate_to_home(self) -> bool:
        """Navigate back to the Home/For You page.
        
        Returns:
            True if successfully navigated to home, False otherwise.
        """
        logger.info("🏠 Navigating to Home...")
        
        if self._find_and_click(NAVIGATION_SELECTORS.home_tab, timeout=5.0):
            self._random_sleep(1.5, 2.5)
            logger.info("✅ Successfully navigated to Home")
            return True
        
        logger.warning("❌ Could not navigate to Home page")
        return False
    
    def fetch_own_profile(self) -> Optional[TikTokProfileInfo]:
        """Navigate to own profile, fetch info, then return to Home.
        
        This is a convenience method that combines navigation and fetching.
        
        Returns:
            TikTokProfileInfo if successful, None otherwise.
        """
        if not self.navigate_to_own_profile():
            # The tap may still have landed somewhere off Home even though verification
            # failed (device: this left the app stuck with no bottom nav visible, so every
            # later navigate_to_home/open_search attempt kept failing and the workflow died
            # with 0 videos). Always try to recover to Home before giving up, not just on
            # the success path below.
            self.navigate_to_home()
            return None

        self._random_sleep(1.0, 1.5)
        profile_info = self.get_own_profile_info()

        # Navigate back to Home so the workflow can continue
        self._random_sleep(0.5, 1.0)
        self.navigate_to_home()

        return profile_info
