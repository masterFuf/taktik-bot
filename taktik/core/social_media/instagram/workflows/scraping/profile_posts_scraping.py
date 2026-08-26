"""Collect the posts of target accounts: their URL, their likes, their comments.

The other scraping sources produce PROFILES. This one produces POST URLS — what the
`post_url` workflows need to run on, and what had to be pasted by hand until now.

Per target: walk the profile grid, open the posts one by one, read the two counters, copy
the link, store. No profile is visited, nothing is interacted with.

Everything here calls the production readers directly — the counters through the shared
`InstagramUIExtractors` (both already testable from the Lab as `post.read_stats`), the URL
through `get_post_url_from_share` (Lab: `post.read_share_url`).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from rich.console import Console

from ...ui.language import detect_and_optimize
from ..common.detection import is_reel_post
from ..common.post_navigation import (
    ensure_profile_grid_tab,
    get_post_url_from_share,
    open_post_at_position,
)

console = Console()

DEFAULT_MAX_POSTS_PER_TARGET = 20
#: Consecutive grid cells that would not open before the target is considered exhausted (a
#: profile with fewer posts than asked, or a grid that stopped scrolling).
MAX_CONSECUTIVE_OPEN_FAILURES = 2
#: Back presses allowed to leave a post viewer: a photo needs one, a reel viewer can need two.
MAX_BACK_PRESSES_TO_GRID = 2


class ProfilePostsScrapingMixin:
    """Mixin: collect the post URLs and counters of target profiles."""

    def _scrape_profile_posts(self) -> Dict[str, Any]:
        """Walk each target's grid and collect its posts."""
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

    def _collect_target_posts(self, target: str, max_posts: int, repo) -> Dict[str, Any]:
        """Open up to `max_posts` posts of one profile and collect each. Returns the tally."""
        info: Dict[str, Any] = {"username": target, "opened": 0, "collected": 0, "no_url": 0}
        console.print(f"\n[cyan]Collecting the posts of @{target}...[/cyan]")

        if not self.nav_actions.navigate_to_profile(target):
            self.logger.warning(f"Failed to navigate to @{target}")
            info["error"] = "navigation failed"
            return info
        time.sleep(1.5)

        profile_info = self.profile_manager.get_complete_profile_info(username=target, navigate_if_needed=False)
        if profile_info and profile_info.get('is_private'):
            console.print(f"[yellow]@{target}: private account, its posts are not reachable[/yellow]")
            info["error"] = "private"
            return info
        # A read count of 0 means "could not read", not "no posts": the grid decides then.
        posts_count = int((profile_info or {}).get('posts_count') or 0)
        if posts_count:
            max_posts = min(max_posts, posts_count)

        ensure_profile_grid_tab(self.device, self.logger)
        failures = 0
        for index in range(1, max_posts + 1):
            if not self._should_continue():
                break
            if not self.detection_actions.is_post_grid_visible():
                self._return_to_post_grid()

            if not open_post_at_position(self.device, index, self.logger):
                failures += 1
                if failures >= MAX_CONSECUTIVE_OPEN_FAILURES:
                    self.logger.info(f"@{target}: grid exhausted at position {index}")
                    break
                continue
            failures = 0
            info["opened"] += 1

            try:
                info["collected" if self._collect_open_post(target, repo) else "no_url"] += 1
            except Exception as exc:
                self.logger.warning(f"@{target} post #{index}: {exc}")
            finally:
                self._return_to_post_grid()

        console.print(
            f"[green]@{target}: {info['opened']} opened, {info['collected']} collected, "
            f"{info['no_url']} without URL[/green]"
        )
        return info

    def _collect_open_post(self, target: str, repo) -> bool:
        """Read the open post and store it. True when it was collected."""
        likes, comments = self._read_post_counts()
        post_url = get_post_url_from_share(self.device, self.logger)
        if not post_url:
            self.logger.warning(f"@{target}: no share URL on this post, not collected")
            return False

        if repo is not None and repo.record(
            post_url=post_url,
            author_username=target,
            likes_count=likes,
            comments_count=comments,
        ) is None:
            return False

        entry = {
            "username": target,
            "post_url": post_url,
            "likes_count": likes,
            "comments_count": comments,
        }
        self.scraped_posts.append(entry)
        if self._ipc:
            try:
                self._ipc.send("post_captured", **entry)
            except Exception as exc:
                self.logger.debug(f"post_captured event not sent: {exc}")
        return True

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
