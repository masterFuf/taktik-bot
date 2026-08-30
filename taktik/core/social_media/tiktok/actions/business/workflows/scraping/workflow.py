"""TikTok Scraping Workflow - Scrape profiles from followers/following lists or hashtags.

Core business logic only — no IPC, no bridge dependencies.
The bridge wires up callbacks for progress/status/DB persistence.
"""

from typing import Optional, Dict, Any, List, Callable, Set
from loguru import logger
import time

from ....atomic.navigation_actions import NavigationActions
from ....atomic.scroll_actions import ScrollActions
from ....core.base_action import BaseAction
from ....core.utils import extract_resource_id as _extract_rid, first_matching
from .....ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from .....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from .....ui.selectors.surfaces.search import SEARCH_SELECTORS
from .....services.profile.username import read_open_profile_handle
from .....ui.selectors.surfaces.video import VIDEO_SELECTORS
from .models import ScrapingConfig, ScrapingStats, empty_profile
from .._internal.profile_extractor import extract_profile_from_screen


class ScrapingWorkflow:
    """TikTok Scraping workflow — scrapes profiles without interactions."""

    def __init__(self, device, navigation: NavigationActions, config: ScrapingConfig):
        self.device = device
        self.navigation = navigation
        self.config = config
        self.stopped = False
        self.stats = ScrapingStats()

        self._base = BaseAction(device)
        self._scroll = ScrollActions(device)
        self._followers_sel = FOLLOWERS_SELECTORS
        self._video_sel = VIDEO_SELECTORS
        self._search_sel = SEARCH_SELECTORS

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

                # Read through the selector list. Both follower anchors are written
                # `contains(@resource-id, …)`, which the id extractor cannot parse — and unlike
                # the profile extractor, this loop had NO `if rid:` guard, so it was asking the
                # device for `resourceId=''` on every iteration and scrolling a list it could not
                # read. The display name is the fallback: some rows show only that.
                username_elements = first_matching(raw_device, self._followers_sel.follower_username)
                display_name_elements = first_matching(
                    raw_device, self._followers_sel.follower_display_name)
                if not username_elements:
                    username_elements = display_name_elements

                found_new = False

                for i in range(len(username_elements)):
                    if self.stopped:
                        break
                    try:
                        elem = username_elements[i]
                        username_text = elem.text
                        if username_text and username_text not in scraped_usernames:
                            username = username_text.replace('@', '').strip()
                            if username:
                                scraped_usernames.add(username_text)
                                found_new = True

                                display_name = ''
                                if i < len(display_name_elements):
                                    try:
                                        display_name = display_name_elements[i].text or ''
                                    except Exception:
                                        pass

                                profile = empty_profile(username, display_name)

                                if self.config.enrich_profiles and len(profiles) < self.config.max_profiles_to_enrich:
                                    self._enrich_in_place(profile, elem, raw_device, username)

                                profiles.append(profile)
                                self.stats.profiles_scraped += 1
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
                    self._scroll.scroll_search_results(direction='down')
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
        """The people posting under a hashtag, by their HANDLE.

        Rewritten on 2026-08-30 because the previous version returned nothing at all. Measured:
        a full run on #fitness logged "Scraped 0 profiles" after 38 seconds and emitted no error.
        It read `author_username` straight after submitting the search, expecting a video feed --
        but a hashtag search lands on a RESULTS GRID, where that node does not exist. It then
        swiped `max_videos` times against a grid and returned an empty list, reporting success.

        Two more things the screen had to say before this could work:

        - The grid cell's own description is the anchor: `Vidéo par <NAME>, <caption>, Aimé par
          <n> utilisateurs`. Readable, so it survives a version bump; the obfuscated `sq1`
          container the surface used to name had already stopped resolving entirely.
        - The name in that description is a DISPLAY NAME. The first #fitness cell read
          `I AM MAGIC ✨` and belongs to @peerajmalraza314. Every handle here is therefore read
          off the profile that opens, never taken from the grid -- the same rule the comment
          sheet and the new-followers page both forced.

        Costs roughly 20 seconds per person: cell -> video -> profile -> back -> back. That is
        what a real handle costs on this surface, and it is why `max_profiles` is a budget.
        """
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
            time.sleep(2.5)

            self._emit_status("scraping", f"Scraping videos from #{hashtag}")
            cells_opened = 0

            while len(profiles) < max_profiles and cells_opened < max_videos and not self.stopped:
                cells = first_matching(self.device, self._search_sel.video_result_cell)
                if not cells:
                    logger.warning(
                        f"No result cell on screen for #{hashtag} -- "
                        "the search did not land on a results grid"
                    )
                    break

                found_here = 0
                for index in range(len(cells)):
                    if len(profiles) >= max_profiles or cells_opened >= max_videos or self.stopped:
                        break
                    cells_opened += 1
                    username = self._handle_behind_result_cell(index)
                    if not username or username in scraped_usernames:
                        continue

                    scraped_usernames.add(username)
                    profile = empty_profile(username)
                    profiles.append(profile)
                    found_here += 1
                    self.stats.profiles_scraped += 1
                    self._emit_progress(len(profiles), max_profiles, username)
                    self._emit_profile(profile)
                    self._emit_save_profile(profile)
                    logger.info(f"Scraped [{len(profiles)}/{max_profiles}]: @{username}")

                if len(profiles) >= max_profiles or cells_opened >= max_videos:
                    break
                if not found_here:
                    # Nobody new from a whole screenful. Comparing the cells themselves would be
                    # the obvious check and it is not reliable -- the descriptions repeat once a
                    # creator has several videos under the tag.
                    logger.debug(f"#{hashtag}: a full screenful brought nobody new")
                    break
                self._scroll.scroll_profile_videos('down')
                time.sleep(1.5)

            logger.info(f"Scraped {len(profiles)} profiles from #{hashtag}")

        except Exception as e:
            logger.error(f"Error scraping hashtag: {e}")

        return profiles

    def _handle_behind_result_cell(self, index: int) -> str:
        """Open the result cell at `index`, read the author's handle, and come back to the grid.

        Returns "" whenever any leg of the round trip failed, INCLUDING failing to get back: a
        caller that kept opening indices on the wrong screen would tap whatever sits there.
        """
        cells = first_matching(self.device, self._search_sel.video_result_cell)
        if index >= len(cells):
            return ""

        try:
            cells[index].click()
        except Exception as exc:
            logger.debug(f"Result cell {index} not tappable: {exc}")
            return ""
        time.sleep(3.5)

        handle = ""
        author = first_matching(self.device, self._video_sel.author_username)
        if author:
            try:
                author[0].click()
                time.sleep(2.5)
                handle = read_open_profile_handle(self.device, timeout=6)
            except Exception as exc:
                logger.debug(f"Could not open the author of cell {index}: {exc}")
            self.device.press("back")
            time.sleep(1.5)
        else:
            logger.debug(f"Cell {index} did not open a video screen")

        self.device.press("back")
        time.sleep(1.5)

        if not first_matching(self.device, self._search_sel.video_result_cell):
            logger.warning("Lost the results grid on the way back -- stopping this hashtag")
            return ""
        return handle

    # ── enrichment ───────────────────────────────────────────────────

    def _enrich_in_place(self, profile: dict, elem, raw_device, username: str):
        """Click a username element, enrich the profile dict, then go back."""
        try:
            self._emit_status("enriching", f"Enriching @{username}")
            if not self._base._human_tap_bounds(elem):
                elem.click()
            time.sleep(3.5)

            enriched = extract_profile_from_screen(raw_device, username)
            if enriched:
                profile.update(enriched)
                self.stats.profiles_enriched += 1
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
