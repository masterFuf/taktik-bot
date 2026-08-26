"""Collect the posts of target accounts: their URL, their likes, their comments.

The other scraping sources produce PROFILES. This one produces POST URLS — what the
`post_url` workflows need to run on, and what had to be pasted by hand until now.

Per target: open the FIRST post of the grid, read the two counters, copy the link, move to
the next post, repeat. The profile itself is never read and nothing is interacted with.

Moving on is the delicate part, and it is not this module's invention: `PostNavigationMixin`
already does it for the like workflow, which walks a profile's posts the same way. A normal
post advances INSIDE the viewer; a reel must instead exit to the grid, because a vertical
gesture in the clips viewer scrolls Instagram's global reels feed and the Back control
disappears after the first one. `_advance_or_exit_reel` is that decision, and it is reused
here rather than re-spelled.

The reads are the production ones too: the counters through the shared
`InstagramUIExtractors` (Lab: `post.read_stats`), the URL through `get_post_url_from_share`
(Lab: `post.read_share_url`).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from ...ui.language import detect_and_optimize
from ..common.detection import is_reel_post
from ..common.post_navigation import ensure_profile_grid_tab, get_post_url_from_share

console = Console()

DEFAULT_MAX_POSTS_PER_TARGET = 20
#: Back presses allowed to leave a post viewer: a photo needs one, a reel viewer can need two.
MAX_BACK_PRESSES_TO_GRID = 2


class ProfilePostsScrapingMixin:
    """Mixin: collect the post URLs and counters of target profiles."""

    def _scrape_profile_posts(self) -> Dict[str, Any]:
        """Walk each target's posts and collect them."""
        targets = [t for t in (self.config.get('target_usernames') or []) if t]
        if not targets:
            return {"success": False, "error": "No target usernames provided"}

        max_posts = int(self.config.get('max_posts_per_target') or DEFAULT_MAX_POSTS_PER_TARGET)
        repo = self._local_db().social_posts if self.config.get('save_to_db', True) else None
        if repo is None:
            self.logger.info("save_to_db is off: posts are read and reported, nothing is stored")

        # The reel indicator and the share sheet's "Copy link" are localised: the app language
        # must be known before the first localised selector is read.
        try:
            detect_and_optimize(self.device)
        except Exception as exc:
            self.logger.debug(f"Language detection skipped: {exc}")

        targets_info: List[Dict[str, Any]] = []
        for target in targets:
            if not self._should_continue():
                self.logger.info("Session time limit reached")
                break
            targets_info.append(self._collect_target_posts(target, max_posts, repo))

        return {
            "success": True,
            "total_scraped": len(self.scraped_posts),
            "targets_processed": len(targets_info),
            "targets_info": targets_info,
        }

    def _post_navigator(self):
        """The production carrier of `PostNavigationMixin` — opening a profile's first post,
        advancing between posts, escaping a reel.

        Those helpers live on `LikeOrchestration`, and this is how the Cartography Lab mounts
        them too: built with the device alone, which is all they need. Nothing is liked here;
        only its navigation methods are called.
        """
        navigator = getattr(self, "_post_navigator_instance", None)
        if navigator is None:
            from ...actions.business.actions.like.orchestration import LikeOrchestration
            navigator = LikeOrchestration(self.device)
            self._post_navigator_instance = navigator
        return navigator

    def _collect_target_posts(self, target: str, max_posts: int, repo) -> Dict[str, Any]:
        """Open the profile's posts one after another and collect each. Returns the tally.

        The profile itself is deliberately NOT read: its stats are not what this run produces,
        the read costs several seconds per target, and it announced a captured PROFILE on a run
        whose whole output is post URLs.
        """
        info: Dict[str, Any] = {"username": target, "opened": 0, "collected": 0, "no_url": 0}
        console.print(f"\n[cyan]Collecting the posts of @{target}...[/cyan]")

        if not self.nav_actions.navigate_to_profile(target):
            self.logger.warning(f"Failed to navigate to @{target}")
            info["error"] = "navigation failed"
            return info
        time.sleep(1.5)

        navigator = self._post_navigator()
        ensure_profile_grid_tab(self.device, self.logger)
        if not navigator._open_first_post_of_profile(username=target):
            # No thumbnail could be opened: an empty grid, or an account whose posts are not
            # served to us (private). Either way there is nothing to collect here.
            console.print(f"[yellow]@{target}: no post could be opened[/yellow]")
            info["error"] = "no post reachable"
            return info

        # The URL is the post's identity. If an advance lands on one already collected, the
        # viewer stopped moving — better to stop than to record the same post twice.
        seen_urls: set = set()
        for index in range(1, max_posts + 1):
            if not self._should_continue():
                break
            info["opened"] += 1

            # Read the type BEFORE the share sheet: opening it is what could change the surface.
            is_reel = False
            try:
                is_reel = is_reel_post(self.device, self.logger)
            except Exception as exc:
                self.logger.debug(f"Reel check failed: {exc}")

            try:
                outcome = self._collect_open_post(target, repo, seen_urls)
            except Exception as exc:
                self.logger.warning(f"@{target} post #{index}: {exc}")
                outcome = "no_url"

            if outcome == "duplicate":
                self.logger.info(f"@{target}: same post again, the viewer stopped advancing")
                break
            info[outcome] += 1

            if index >= max_posts:
                break
            if not navigator._advance_or_exit_reel(is_reel, username=target):
                self.logger.info(f"@{target}: no further post to open")
                break

        self._return_to_post_grid()
        console.print(
            f"[green]@{target}: {info['opened']} opened, {info['collected']} collected, "
            f"{info['no_url']} without URL[/green]"
        )
        return info

    def _collect_open_post(self, target: str, repo, seen_urls: set) -> str:
        """Read the open post and store it. Returns the tally key of what happened."""
        likes, comments = self._read_post_counts()
        post_url = get_post_url_from_share(self.device, self.logger)
        if not post_url:
            self.logger.warning(f"@{target}: no share URL on this post, not collected")
            return "no_url"
        if post_url in seen_urls:
            return "duplicate"
        seen_urls.add(post_url)

        if repo is not None and repo.record(
            post_url=post_url,
            author_username=target,
            likes_count=likes,
            comments_count=comments,
        ) is None:
            return "no_url"

        entry = {
            "username": target,
            "post_url": post_url,
            "likes_count": likes,
            "comments_count": comments,
        }
        self.scraped_posts.append(entry)
        self.logger.info(f"@{target}: {post_url} ({likes} likes, {comments} comments)")
        if self._ipc:
            try:
                self._ipc.send("post_captured", **entry)
            except Exception as exc:
                self.logger.debug(f"post_captured event not sent: {exc}")
        return "collected"

    def _read_post_counts(self) -> Tuple[Optional[int], Optional[int]]:
        """The open post's like and comment counts, or (None, None) when unreadable.

        The atomic read first: it takes both numbers from ONE element, so they cannot come
        from two different posts. The separate extractors answer 0 when they find nothing,
        which is not a measurement — a double zero on that path is reported as unreadable
        rather than written over a value already stored.
        """
        try:
            atomic = self.ui_extractors.extract_post_stats_atomic()
            if atomic:
                return atomic.get("likes"), atomic.get("comments")
        except Exception as exc:
            self.logger.debug(f"Atomic counter read failed: {exc}")

        try:
            reel = is_reel_post(self.device, self.logger)
            likes = self.ui_extractors.extract_likes_count_from_ui(is_reel=reel)
            comments = self.ui_extractors.extract_comments_count_from_ui(is_reel=reel)
        except Exception as exc:
            self.logger.debug(f"Counter read failed: {exc}")
            return None, None
        return (None, None) if not likes and not comments else (likes, comments)

    def _return_to_post_grid(self) -> bool:
        """Leave the post viewer for the grid. One back for a photo; a reel viewer can need two."""
        for _ in range(MAX_BACK_PRESSES_TO_GRID):
            if self.detection_actions.is_post_grid_visible():
                return True
            self.device.press("back")
            time.sleep(1.2)
        return self.detection_actions.is_post_grid_visible()
