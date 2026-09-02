"""TikTok Scraping Workflow - Scrape profiles from followers/following lists or hashtags.

Core business logic only — no IPC, no bridge dependencies.
The bridge wires up callbacks for progress/status/DB persistence.
"""

from typing import Optional, Dict, Any, List, Callable, Set
from loguru import logger
import time

from ....atomic.navigation.navigation_actions import NavigationActions
from ....atomic.navigation.search_actions import SearchActions
from ....atomic.scroll.scroll_actions import ScrollActions
from ....core.base_action import BaseAction
from ....core.utils import extract_resource_id as _extract_rid, first_matching
from .....ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from .....ui.selectors.surfaces.profile import PROFILE_SELECTORS
from .....ui.selectors.surfaces.search import SEARCH_SELECTORS
from .....services.profile.username import read_open_profile_handle
from .....services.navigation.deeplink import open_post_by_url
from ....atomic.interaction.comment_actions import CommentActions
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
        self._profile_sel = PROFILE_SELECTORS

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

            elif self.config.scrape_type == 'post_url':
                for url in self.config.post_urls:
                    if self.stopped:
                        break
                    remaining = self.config.max_profiles - len(all_profiles)
                    if remaining <= 0:
                        break
                    all_profiles.extend(self._scrape_post_commenters(url, remaining))

            elif self.config.scrape_type == 'account_posts':
                for username in self.config.target_usernames:
                    if self.stopped:
                        break
                    self._scrape_account_posts(username)

            elif self.config.scrape_type == 'sound':
                all_profiles = self._scrape_sounds(self.config.max_profiles)

            else:
                # Said out loud. An unknown type used to fall through to an empty list and a
                # successful-looking run, which is how a front that sends a type the bot does not
                # know reports "0 profiles found" instead of "I cannot do that".
                message = f"Unknown scrape type: {self.config.scrape_type!r}"
                logger.error(message)
                self._emit_error(message)

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

    # ── an account's posts ─────────────────────────

    def _scrape_account_posts(self, username: str) -> None:
        """Collect the LINK and the IDENTITY of an account's videos, one grid cell at a time.

        Returns nothing and emits no profiles on purpose: this mode produces POSTS, not people.
        They land in `social_posts` and are read back by anything that needs to reopen a video --
        the commenter scrape, for one, which takes links as its input.

        The identity is what makes a second run cheap. TikTok mints a new short link on every
        copy, so keying on the URL would store one video once per visit; the key built from
        author, date and caption recognises a post already collected and refreshes its link
        instead of adding a row.
        """
        from taktik.core.social_media.tiktok.actions.atomic.interaction.post_link_actions import PostLinkActions

        logger.info(f"Collecting posts of @{username}")
        self._emit_status("navigating", f"Opening @{username}")

        if not SearchActions(self.device).navigate_to_user_profile(username):
            message = f"Could not open @{username}"
            logger.warning(message)
            self._emit_error(message)
            return

        time.sleep(2)
        collector = PostLinkActions(self.device)
        posts = self._local_db().social_posts if self._local_db() else None
        seen_keys = set()
        budget = self.config.max_posts_per_account

        self._emit_status("scraping", f"Collecting posts of @{username}")
        for index in range(budget):
            if self.stopped:
                break
            cells = first_matching(self.device, self._profile_sel.video_item)
            if index >= len(cells):
                # Out of visible cells: scroll once and look again, then give up rather than
                # loop. A grid that will not move has nothing more to give.
                self._scroll.scroll_profile_videos('down')
                time.sleep(1.5)
                cells = first_matching(self.device, self._profile_sel.video_item)
                if index >= len(cells):
                    logger.debug(f"@{username}: no cell {index} on the grid")
                    break

            try:
                cells[index].click()
            except Exception as exc:
                logger.debug(f"Cell {index} not tappable: {exc}")
                break
            time.sleep(3.5)

            collected = collector.collect_post()
            self.device.press("back")
            time.sleep(1.5)

            if not collected:
                continue
            key = collected["post_key"]
            if key in seen_keys:
                continue
            seen_keys.add(key)

            if posts is not None:
                try:
                    posts.record(
                        post_url=collected["post_url"],
                        author_username=username,
                        platform="tiktok",
                        post_key=key,
                    )
                except Exception as exc:
                    logger.warning(f"Could not store {key}: {exc}")

            self._emit_progress(len(seen_keys), budget, key)
            logger.info(f"Collected [{len(seen_keys)}/{budget}]: {collected['post_url']}")

        logger.info(f"Collected {len(seen_keys)} post(s) of @{username}")

    def _local_db(self):
        """The local database, or None when it cannot be opened.

        None rather than a raise: a collection run that cannot store is still worth watching, and
        the links it emits are still usable. What must not happen is the run dying on a database.
        """
        if getattr(self, "_db_service", None) is None:
            try:
                from taktik.core.database.local.service import get_local_database

                self._db_service = get_local_database()
            except Exception as exc:
                logger.warning(f"Local database unavailable: {exc}")
                self._db_service = False
        return self._db_service or None

    # ── sounds ──────────────────────────────────────

    def _scrape_sounds(self, max_profiles: int) -> List[Dict[str, Any]]:
        """Walk the feed, and harvest the people behind the sounds that carry a real audience.

        The shape follows a measured limit rather than a preference. Reaching a sound BY NAME
        through the search Sounds tab does not work here -- the tab is found and tapped and the
        list stays empty past twelve seconds -- so a sound is reached from a video that uses it.
        The feed supplies the sounds; the count decides which are worth opening.

        `min_sound_posts` is what makes this cheap enough to run. Most sounds are somebody's own
        original audio: our test account's had 3 posts, `Umbrella - Rihanna` had 3.3 million.
        Opening the first kind costs twenty seconds and returns the author we already had.
        """
        from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions

        profiles: List[Dict[str, Any]] = []
        scraped_usernames: Set[str] = set()
        seen_sounds: Set[str] = set()
        sounds = SoundActions(self.device)

        # A named sound short-circuits the feed walk. The name that comes back is the REAL one,
        # which is not always the one asked for -- the search rows carry no titles, so the only
        # way to know is to open and read.
        if self.config.sound_query:
            self._emit_status("navigating", f"Opening the sound {self.config.sound_query}")
            landed = sounds.open_sound_by_name(self.config.sound_query)
            if not landed:
                message = f"Could not open a sound for {self.config.sound_query!r}"
                logger.warning(message)
                self._emit_error(message)
                return profiles
            if landed != self.config.sound_query:
                logger.info(f"Asked for {self.config.sound_query!r}, landed on {landed!r}")
                self._emit_status("scraping", f"Sound: {landed}")
            for person in sounds.collect_sound_users(max_users=self.config.max_users_per_sound):
                username = person["username"]
                if username in scraped_usernames:
                    continue
                scraped_usernames.add(username)
                profile = empty_profile(username, display_name=person.get("display_name", ""))
                profiles.append(profile)
                self.stats.profiles_scraped += 1
                self._emit_progress(len(profiles), max_profiles, username)
                self._emit_profile(profile)
                self._emit_save_profile(profile)
                logger.info(f"Scraped [{len(profiles)}]: @{username}")
            logger.info(f"Scraped {len(profiles)} profile(s) from {landed!r}")
            return profiles

        self._emit_status("scraping", "Reading the sounds of the feed")

        for _ in range(self.config.max_videos):
            if self.stopped or len(profiles) >= max_profiles:
                break
            if len(seen_sounds) >= self.config.max_sounds_per_session:
                break

            label = sounds.read_current_sound()
            if label and label in seen_sounds:
                self._next_video()
                continue

            if not label or not sounds.open_sound_page():
                self._next_video()
                continue
            seen_sounds.add(label)

            count = sounds.sound_post_count()
            # None is not zero: an unreadable page and an unused sound lead to opposite calls,
            # and treating the first as the second silently skips real trends.
            if count is None or count < self.config.min_sound_posts:
                logger.info(f"Sound skipped ({count} posts): {label}")
                self.device.press("back")
                time.sleep(2)
                self._next_video()
                continue

            logger.info(f"Sound kept ({count} posts): {label}")
            budget = min(max_profiles - len(profiles), self.config.max_users_per_sound)
            for person in sounds.collect_sound_users(max_users=budget):
                username = person["username"]
                if username in scraped_usernames:
                    continue
                scraped_usernames.add(username)
                profile = empty_profile(username, display_name=person.get("display_name", ""))
                profiles.append(profile)
                self.stats.profiles_scraped += 1
                self._emit_progress(len(profiles), max_profiles, username)
                self._emit_profile(profile)
                self._emit_save_profile(profile)
                logger.info(f"Scraped [{len(profiles)}/{max_profiles}]: @{username}")

            self.device.press("back")
            time.sleep(2)
            self._next_video()

        logger.info(f"Scraped {len(profiles)} profile(s) from {len(seen_sounds)} sound(s)")
        return profiles

    def _next_video(self) -> None:
        """One swipe to the next video, through the fling every feed walk uses."""
        try:
            self._scroll.scroll_to_next_video()
            time.sleep(2.0)
        except Exception as exc:
            logger.debug(f"Could not advance the feed: {exc}")

    # ── post commenters ────────────────────────────────

    def _scrape_post_commenters(self, post_url: str, max_profiles: int) -> List[Dict[str, Any]]:
        """The people who commented on one post, by their handle.

        On Instagram the equivalent surface is the likers of a post. TikTok renders no such list
        at all -- the like count is a number and nothing else -- so on this platform the audience
        a post exposes is its COMMENTERS, and that is what this collects.

        The post is reopened from its link by deep link, which was measured to land on the post
        itself: `https://vm.tiktok.com/ZN8FaXgeY/` reopened charli d'amelio's video, caption and
        all. The handles come from `read_commenter_handles`, which opens each row because a
        comment row carries a display name and no username anywhere.
        """
        logger.info(f"Scraping commenters of {post_url}")
        self._emit_status("navigating", f"Opening {post_url}")

        profiles: List[Dict[str, Any]] = []
        if not open_post_by_url(self.device, post_url):
            message = f"Could not open {post_url}"
            logger.warning(message)
            self._emit_error(message)
            return profiles

        budget = min(max_profiles, self.config.max_commenters_per_post)
        self._emit_status("scraping", f"Reading commenters of {post_url}")
        commenters = CommentActions(self.device).read_commenter_handles(max_commenters=budget)

        for person in commenters:
            if self.stopped:
                break
            profile = empty_profile(person["username"], display_name=person.get("display_name", ""))
            profiles.append(profile)
            self.stats.profiles_scraped += 1
            self._emit_progress(len(profiles), budget, person["username"])
            self._emit_profile(profile)
            self._emit_save_profile(profile)
            logger.info(f"Scraped [{len(profiles)}/{budget}]: @{person['username']}")

        logger.info(f"Scraped {len(profiles)} commenter(s) from {post_url}")
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
