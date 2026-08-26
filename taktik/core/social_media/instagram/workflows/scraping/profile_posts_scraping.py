"""Catalogue the posts of target accounts — one `social_posts` row per post, no profile scraped.

The other scraping sources produce PROFILES. This one produces the list a `post_url` run
draws from: for each target, walk the profile grid, open the posts one by one, read each
post's card (author, likes, comments, caption, date, share URL) and write it to the
catalogue. The counters are what make a post worth a run, and they are read HERE, once,
instead of by every workflow that would later land on the post.

The share sheet is the expensive step (one round trip per post), so a post the catalogue
already holds is recognised BEFORE paying for it: the card is read without its URL, its
author + caption identity is looked up, and a hit only refreshes the counters. The identity
is only trusted when the caption is discriminating (see `instagram_post_identity`) — a weak
caption pays the share sheet rather than risk refreshing the wrong row.

Grid positions are walked in order, which is NOT chronological: Instagram lets an account
pin up to three posts at the top, and the grid shows reels and photos alike. The position
is recorded so a reader can tell.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from rich.console import Console

from taktik.core.database.instagram_post_identity import is_discriminating_post_ref

from ...ui.language import detect_and_optimize
from ..common.post_card import read_open_post_card, read_open_post_url
from ..common.post_navigation import ensure_profile_grid_tab, open_post_at_position

console = Console()

DEFAULT_MAX_POSTS_PER_TARGET = 20
#: Consecutive grid cells that would not open before the target is considered exhausted (a
#: profile with fewer posts than asked, or a grid that stopped scrolling).
MAX_CONSECUTIVE_OPEN_FAILURES = 2
#: Back presses allowed to leave a post viewer: a photo needs one, a reel viewer can need two.
MAX_BACK_PRESSES_TO_GRID = 2


class ProfilePostsScrapingMixin:
    """Mixin: catalogue the posts of target profiles into `social_posts`."""

    def _scrape_profile_posts(self) -> Dict[str, Any]:
        """Walk each target's grid and catalogue its posts."""
        targets = [t for t in (self.config.get('target_usernames') or []) if t]
        if not targets:
            return {"success": False, "error": "No target usernames provided"}

        max_posts = int(self.config.get('max_posts_per_target') or DEFAULT_MAX_POSTS_PER_TARGET)
        refresh_known = bool(self.config.get('refresh_known', True))
        repo = self._local_db().social_posts if self.config.get('save_to_db', True) else None
        if repo is None:
            self.logger.info("save_to_db is off: posts are read and reported, nothing is catalogued")

        # Reel indicators, the share sheet's "Copy link" and the media labels are localised:
        # the app language must be known before the first localised selector is read.
        try:
            detect_and_optimize(self.device)
        except Exception as exc:
            self.logger.debug(f"Language detection skipped: {exc}")

        targets_info: List[Dict[str, Any]] = []
        for target in targets:
            if not self._should_continue():
                self.logger.info("Session time limit reached")
                break
            targets_info.append(self._catalogue_target_posts(target, max_posts, refresh_known, repo))

        return {
            "success": True,
            "total_scraped": len(self.scraped_posts),
            "targets_processed": len(targets_info),
            "targets_info": targets_info,
        }

    def _catalogue_target_posts(self, target: str, max_posts: int, refresh_known: bool, repo) -> Dict[str, Any]:
        """Open up to `max_posts` posts of one profile and catalogue each. Returns the tally."""
        info: Dict[str, Any] = {
            "username": target, "opened": 0, "recorded": 0, "refreshed": 0,
            "skipped_known": 0, "no_url": 0,
        }
        console.print(f"\n[cyan]Cataloguing the posts of @{target}...[/cyan]")

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
                    self.logger.info(f"@{target}: no post opened at positions {index - failures + 1}-{index}, grid exhausted")
                    break
                continue
            failures = 0
            info["opened"] += 1

            try:
                outcome = self._catalogue_open_post(target, index, refresh_known, repo)
                info[outcome] += 1
            except Exception as exc:
                self.logger.warning(f"@{target} post #{index}: {exc}")
            finally:
                self._return_to_post_grid()

        console.print(
            f"[green]@{target}: {info['opened']} opened, {info['recorded']} catalogued, "
            f"{info['refreshed']} refreshed, {info['skipped_known']} already known, {info['no_url']} without URL[/green]"
        )
        return info

    def _catalogue_open_post(self, target: str, index: int, refresh_known: bool, repo) -> str:
        """Read the open post and write it. Returns the tally key of what happened."""
        card = read_open_post_card(
            self.device, self.logger,
            ui_extractors=self.ui_extractors, scroll_actions=self.scroll_actions,
            with_url=False, author_hint=target,
        )

        known = None
        if repo is not None and card.post_ref and is_discriminating_post_ref(card.caption):
            known = repo.find_by_ref(card.post_ref)
        if known:
            if not refresh_known:
                self.logger.debug(f"@{target} post #{index}: already catalogued, left as is")
                return "skipped_known"
            repo.refresh_counts_by_ref(
                card.post_ref, card.likes_count, card.comments_count,
                scraping_id=self.scraping_session_id,
            )
            self._remember_post(card, known.get('post_url'), index, target, "refreshed")
            return "refreshed"

        post_url = read_open_post_url(self.device, self.logger)
        if not post_url:
            self.logger.warning(f"@{target} post #{index}: no share URL, not catalogued")
            return "no_url"

        if repo is not None:
            row_id = repo.record(
                post_url=post_url,
                author_username=card.author or target,
                likes_count=card.likes_count,
                comments_count=card.comments_count,
                post_type='reel' if card.is_reel else 'post',
                post_ref=card.post_ref,
                caption_preview=card.caption,
                posted_at_label=card.posted_at_label,
                grid_position=index,
                scraping_id=self.scraping_session_id,
            )
            if row_id is None:
                return "no_url"
        self._remember_post(card, post_url, index, target, "recorded")
        return "recorded"

    def _remember_post(self, card, post_url: Optional[str], index: int, target: str, status: str) -> None:
        """Keep the run's tally and tell the desktop what was just read."""
        entry = {
            "username": target,
            "author": card.author or target,
            "post_url": post_url,
            "likes_count": card.likes_count,
            "comments_count": card.comments_count,
            "is_reel": card.is_reel,
            "caption": (card.caption or "")[:100] or None,
            "position": index,
            "status": status,
        }
        self.scraped_posts.append(entry)
        if self._ipc:
            try:
                self._ipc.send("post_captured", **entry)
            except Exception as exc:
                self.logger.debug(f"post_captured event not sent: {exc}")

    def _return_to_post_grid(self) -> bool:
        """Leave the post viewer for the grid. One back for a photo; a reel viewer can need two."""
        for _ in range(MAX_BACK_PRESSES_TO_GRID):
            if self.detection_actions.is_post_grid_visible():
                return True
            self.device.press("back")
            time.sleep(1.2)
        return self.detection_actions.is_post_grid_visible()
