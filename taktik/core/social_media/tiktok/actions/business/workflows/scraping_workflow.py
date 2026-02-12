"""TikTok Scraping Workflow - Scrape profiles from followers/following lists or hashtags.

Core business logic only — no IPC, no bridge dependencies.
The bridge wires up callbacks for progress/status/DB persistence.
"""

from typing import Optional, Dict, Any, List, Callable, Set
from dataclasses import dataclass, field
from loguru import logger
import time

from ...atomic.navigation_actions import NavigationActions
from ...core.base_action import BaseAction
from ...core.utils import parse_count as _parse_count


@dataclass
class ScrapingConfig:
    """Configuration for the TikTok scraping workflow."""
    scrape_type: str = 'target'           # 'target' or 'hashtag'
    target_usernames: List[str] = field(default_factory=list)
    target_scrape_type: str = 'followers'  # 'followers' or 'following'
    hashtag: str = ''
    max_profiles: int = 500
    max_videos: int = 50
    enrich_profiles: bool = True
    max_profiles_to_enrich: int = 50


class ScrapingWorkflow:
    """TikTok Scraping workflow — scrapes profiles without interactions."""

    def __init__(self, device, navigation: NavigationActions, config: ScrapingConfig):
        self.device = device
        self.navigation = navigation
        self.config = config
        self.stopped = False
        self.profiles_scraped = 0

        self._base = BaseAction(device)

        # Callbacks (set by bridge)
        self._on_status: Optional[Callable] = None
        self._on_progress: Optional[Callable] = None
        self._on_profile: Optional[Callable] = None
        self._on_save_profile: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

    # ── callback setters ─────────────────────────────────────────────

    def set_on_status_callback(self, cb: Callable):
        self._on_status = cb

    def set_on_progress_callback(self, cb: Callable):
        self._on_progress = cb

    def set_on_profile_callback(self, cb: Callable):
        self._on_profile = cb

    def set_on_save_profile_callback(self, cb: Callable):
        self._on_save_profile = cb

    def set_on_error_callback(self, cb: Callable):
        self._on_error = cb

    def stop(self):
        self.stopped = True

    # ── emit helpers ─────────────────────────────────────────────────

    def _emit_status(self, status: str, message: str):
        if self._on_status:
            self._on_status(status, message)

    def _emit_progress(self, scraped: int, total: int, current: str):
        if self._on_progress:
            self._on_progress(scraped, total, current)

    def _emit_profile(self, profile: Dict[str, Any]):
        if self._on_profile:
            self._on_profile(profile)

    def _emit_save_profile(self, profile: Dict[str, Any]):
        if self._on_save_profile:
            self._on_save_profile(profile)

    def _emit_error(self, message: str):
        if self._on_error:
            self._on_error(message)

    # ── run ──────────────────────────────────────────────────────────

    def run(self) -> List[Dict[str, Any]]:
        """Run the scraping workflow. Returns list of scraped profiles."""
        all_profiles: List[Dict[str, Any]] = []

        try:
            if self.config.scrape_type == 'target':
                for username in self.config.target_usernames:
                    if self.stopped:
                        break
                    remaining = self.config.max_profiles - len(all_profiles)
                    if remaining <= 0:
                        break
                    profiles = self._scrape_target_followers(
                        username, self.config.target_scrape_type, remaining
                    )
                    all_profiles.extend(profiles)
                    self.navigation.navigate_to_home()
                    time.sleep(2)

            elif self.config.scrape_type == 'hashtag':
                all_profiles = self._scrape_hashtag(
                    self.config.hashtag, self.config.max_profiles, self.config.max_videos
                )

        except Exception as e:
            logger.error(f"Scraping error: {e}")
            self._emit_error(str(e))

        return all_profiles

    # ── target followers/following ───────────────────────────────────

    def _scrape_target_followers(
        self, target_username: str, scrape_type: str, max_profiles: int
    ) -> List[Dict[str, Any]]:
        logger.info(f"Scraping {scrape_type} of @{target_username}")
        self._emit_status("navigating", f"Navigating to @{target_username}")

        profiles: List[Dict[str, Any]] = []

        try:
            if not self.navigation.navigate_to_user_profile(target_username):
                logger.warning(f"Could not find user: @{target_username}")
                return profiles
            time.sleep(2)

            from ....ui.selectors import PROFILE_SELECTORS

            if scrape_type == 'followers':
                self._emit_status("opening", "Opening followers list")
                if not self._base._find_and_click(PROFILE_SELECTORS.followers_count, timeout=5):
                    logger.warning("Could not click followers count")
                    return profiles
            else:
                self._emit_status("opening", "Opening following list")
                if not self._base._find_and_click(PROFILE_SELECTORS.following_count, timeout=5):
                    logger.warning("Could not click following count")
                    return profiles
            time.sleep(2)

            self._emit_status("scraping", f"Scraping {scrape_type} profiles")
            scraped_usernames: Set[str] = set()
            scroll_attempts = 0
            max_scroll_attempts = 50

            while len(profiles) < max_profiles and scroll_attempts < max_scroll_attempts and not self.stopped:
                raw_device = self.device._device if hasattr(self.device, '_device') else self.device

                username_elements = raw_device(resourceId="com.zhiliaoapp.musically:id/ygv")
                if not username_elements.exists:
                    username_elements = raw_device(resourceId="com.zhiliaoapp.musically:id/yhq")

                found_new = False
                display_name_elements = raw_device(resourceId="com.zhiliaoapp.musically:id/yhq")

                for i in range(username_elements.count):
                    if self.stopped:
                        break
                    try:
                        elem = username_elements[i]
                        username_text = elem.get_text()
                        if username_text and username_text not in scraped_usernames:
                            username = username_text.replace('@', '').strip()
                            if username:
                                scraped_usernames.add(username_text)
                                found_new = True

                                display_name = ''
                                if display_name_elements.exists and i < display_name_elements.count:
                                    try:
                                        display_name = display_name_elements[i].get_text() or ''
                                    except Exception:
                                        pass

                                profile = {
                                    'username': username,
                                    'display_name': display_name,
                                    'followers_count': 0,
                                    'following_count': 0,
                                    'likes_count': 0,
                                    'posts_count': 0,
                                    'bio': '',
                                    'website': '',
                                    'is_private': False,
                                    'is_verified': False,
                                    'is_enriched': False,
                                }

                                if self.config.enrich_profiles and len(profiles) < self.config.max_profiles_to_enrich:
                                    self._enrich_in_place(profile, elem, raw_device, username)

                                profiles.append(profile)
                                self.profiles_scraped += 1
                                self._emit_progress(len(profiles), max_profiles, username)
                                self._emit_profile(profile)
                                self._emit_save_profile(profile)

                                enriched_tag = " [enriched]" if profile.get('is_enriched') else ""
                                logger.info(f"Scraped [{len(profiles)}/{max_profiles}]: @{username} ({display_name}){enriched_tag}")

                                if len(profiles) >= max_profiles:
                                    break
                    except Exception as e:
                        logger.warning(f"Error extracting username: {e}")
                        continue

                if len(profiles) >= max_profiles:
                    break

                if not found_new:
                    scroll_attempts += 1
                else:
                    scroll_attempts = 0

                try:
                    raw_device.swipe(360, 1200, 360, 400, duration=0.4)
                    time.sleep(1.5)
                except Exception as e:
                    logger.warning(f"Scroll error: {e}")
                    scroll_attempts += 1

            logger.info(f"Scraped {len(profiles)} profiles from @{target_username}'s {scrape_type}")

        except Exception as e:
            logger.error(f"Error scraping {scrape_type}: {e}")

        return profiles

    # ── hashtag scraping ─────────────────────────────────────────────

    def _scrape_hashtag(self, hashtag: str, max_profiles: int, max_videos: int) -> List[Dict[str, Any]]:
        logger.info(f"Scraping profiles from #{hashtag}")
        self._emit_status("navigating", f"Navigating to #{hashtag}")

        profiles: List[Dict[str, Any]] = []
        scraped_usernames: Set[str] = set()

        try:
            if not self.navigation.open_search():
                logger.warning("Could not open search")
                return profiles
            time.sleep(1)

            if not self.navigation.search_and_submit(f"#{hashtag}"):
                logger.warning(f"Could not search for #{hashtag}")
                return profiles
            time.sleep(2)

            self._emit_status("scraping", f"Scraping videos from #{hashtag}")
            videos_processed = 0

            while len(profiles) < max_profiles and videos_processed < max_videos and not self.stopped:
                raw_device = self.device._device if hasattr(self.device, '_device') else self.device

                author_elem = raw_device(resourceId="com.zhiliaoapp.musically:id/title")
                if not author_elem.exists:
                    author_elem = raw_device(resourceId="com.zhiliaoapp.musically:id/ej6")

                if author_elem.exists:
                    try:
                        username_text = author_elem.get_text()
                        if username_text:
                            username = username_text.replace('@', '').strip()
                            if username and username not in scraped_usernames:
                                scraped_usernames.add(username)
                                profile = {
                                    'username': username,
                                    'display_name': '',
                                    'followers_count': 0,
                                    'following_count': 0,
                                    'likes_count': 0,
                                    'posts_count': 0,
                                    'bio': '',
                                    'is_private': False,
                                    'is_verified': False,
                                }
                                profiles.append(profile)
                                self.profiles_scraped += 1
                                self._emit_progress(len(profiles), max_profiles, username)
                                self._emit_profile(profile)
                                self._emit_save_profile(profile)
                                logger.info(f"Scraped [{len(profiles)}/{max_profiles}]: @{username}")
                    except Exception as e:
                        logger.warning(f"Error extracting author: {e}")

                videos_processed += 1
                if len(profiles) >= max_profiles:
                    break

                try:
                    raw_device.swipe(540, 1500, 540, 500, duration=0.2)
                    time.sleep(1.5)
                except Exception as e:
                    logger.warning(f"Swipe error: {e}")
                    break

            logger.info(f"Scraped {len(profiles)} profiles from #{hashtag}")

        except Exception as e:
            logger.error(f"Error scraping hashtag: {e}")

        return profiles

    # ── enrichment ───────────────────────────────────────────────────

    def _enrich_in_place(self, profile: dict, elem, raw_device, username: str):
        """Click a username element, enrich the profile dict, then go back."""
        try:
            self._emit_status("enriching", f"Enriching @{username}")
            elem.click()
            time.sleep(3.5)

            enriched = self._extract_profile_data(raw_device, username)
            if enriched:
                profile.update(enriched)
                logger.info(
                    f"Enriched @{username}: {enriched.get('followers_count', 0)} followers, "
                    f"bio: {enriched.get('bio', '')[:50]}..."
                )

            raw_device.press("back")
            time.sleep(2)
        except Exception as e:
            logger.warning(f"Error enriching @{username}: {e}")
            try:
                raw_device.press("back")
                time.sleep(1)
            except Exception:
                pass

    def _extract_profile_data(self, raw_device, username: str) -> Optional[Dict[str, Any]]:
        """Extract detailed profile data from the current profile screen."""
        try:
            data: Dict[str, Any] = {
                'username': username,
                'display_name': '',
                'followers_count': 0,
                'following_count': 0,
                'likes_count': 0,
                'posts_count': 0,
                'bio': '',
                'website': '',
                'is_private': False,
                'is_verified': False,
                'is_enriched': True,
            }

            username_elem = raw_device(resourceId="com.zhiliaoapp.musically:id/qh5")
            if username_elem.exists:
                data['username'] = username_elem.get_text().replace('@', '').strip()

            stat_counts = raw_device(resourceId="com.zhiliaoapp.musically:id/qfw")
            stat_labels = raw_device(resourceId="com.zhiliaoapp.musically:id/qfv")
            if stat_counts.exists and stat_labels.exists:
                for i in range(min(stat_counts.count, stat_labels.count)):
                    try:
                        count_text = stat_counts[i].get_text() or '0'
                        label_text = stat_labels[i].get_text() or ''
                        count = _parse_count(count_text)
                        if 'Following' in label_text:
                            data['following_count'] = count
                        elif 'Followers' in label_text:
                            data['followers_count'] = count
                        elif 'Likes' in label_text:
                            data['likes_count'] = count
                    except Exception as e:
                        logger.warning(f"Error parsing stat: {e}")

            bio_buttons = raw_device(className="android.widget.Button", clickable=True)
            for i in range(bio_buttons.count):
                try:
                    text = bio_buttons[i].get_text() or ''
                    if '\n' in text or len(text) > 50:
                        data['bio'] = text
                        break
                except Exception:
                    pass

            link_elems = raw_device(textContains="http")
            if link_elems.exists:
                try:
                    data['website'] = link_elems[0].get_text()
                except Exception:
                    pass

            return data

        except Exception as e:
            logger.warning(f"Error extracting profile @{username}: {e}")
            return None
