"""Engage the people who COMMENTED on a video, reached by its link.

Instagram's equivalent engages the people who LIKED a post. TikTok has no such surface: it shows
nowhere who liked a video. The people who commented, however, are readable -- so this is the same
workflow answering the same question through the door TikTok leaves open.

Everything after "who are they?" is the production path, unchanged. This is a `TargetProfilesWorkflow`
with a different source of usernames: instead of a list the operator typed, the list is read off
the comment sheet of one video. That is the whole difference, and it is deliberately the whole
difference -- `_process_current_profile` (extract, save, filter, interact, follow), the same stats
shape, the same skip policy and the same filters all keep working because none of them is respelled
here.

The one thing this workflow owns is the detour that gets the handles. A comment row does not carry
a username: `:id/title` holds the DISPLAY NAME and nothing else identifies the person, so
`read_commenter_handles` opens each row's profile to read the handle off it. That costs about
thirteen seconds a head, which is why `max_commenters` is a budget and not a nicety -- the
operator is paying for each name in device time before a single interaction happens.
"""

import time
from dataclasses import dataclass
from typing import List

from loguru import logger

from taktik.core.shared.telemetry.sink import emit_step
from taktik.core.social_media.tiktok.services.navigation.deeplink import open_post_by_url

from ..followers.models import FollowersConfig, FollowersStats
from ..target_profiles.workflow import TargetProfilesConfig, TargetProfilesWorkflow


@dataclass
class PostUrlConfig(TargetProfilesConfig):
    """Target-profiles config plus the video whose commenters we want.

    `usernames` is inherited and stays empty: it is filled at run time from the comment sheet.
    Keeping the field rather than hiding it is what lets the parent's `_resolve_targets` run
    untouched.
    """

    post_url: str = ""
    #: How many commenters to resolve. Each one costs a profile open (~13 s), so this is a budget
    #: of device time as much as a budget of targets.
    max_commenters: int = 20
    #: How far to scroll the comment sheet looking for more rows.
    max_comment_scrolls: int = 8


class PostUrlWorkflow(TargetProfilesWorkflow):
    """Open one video by link, read who commented, then interact with those people."""

    #: A profile rejected here came from a video's comment section, not from anybody's followers
    #: and not from a hand-picked list. Filing it correctly is what keeps the reject stats
    #: readable when several workflows write to `filtered_profiles`.
    FILTER_SOURCE_TYPE = 'post_commenters'

    MODULE_NAME = "tiktok-post-url-workflow"

    @property
    def _filter_source_name(self) -> str:
        return 'post_url'

    def __init__(self, device, config: PostUrlConfig, *, device_id: str = ""):
        super().__init__(device, config)
        self.config: PostUrlConfig = config
        self.device_id = device_id
        self.logger = logger.bind(module=self.MODULE_NAME)

    # ------------------------------------------------------------------
    # The only thing this workflow owns: where the usernames come from
    # ------------------------------------------------------------------

    def _resolve_targets(self) -> List[str]:
        """Open the video, read the commenters, hand their handles to the parent's loop.

        Returns an empty list rather than raising on every failure along the way -- a link that
        does not open and a post with no comments are different facts, and both are reported as
        themselves in the log before the run ends on `no_targets`.
        """
        url = (self.config.post_url or "").strip()
        if not url:
            self.logger.error("❌ No post URL provided")
            return []

        emit_step("navigation", action="open_post_url", target=url[:120])
        if not open_post_by_url(self.device, url, device_id=self.device_id):
            self.logger.error(f"❌ The link did not open a video: {url}")
            return []

        # `read_commenter_handles` lives on CommentActions, NOT on the ClickActions aggregate the
        # workflow carries -- calling it off `self.click` would have raised on the first real run.
        self.logger.info("💬 Reading the comment sheet")
        try:
            from ....atomic.interaction.comment_actions import CommentActions

            rows = CommentActions(self.device).read_commenter_handles(
                max_commenters=self.config.max_commenters,
                max_scrolls=self.config.max_comment_scrolls,
            )
        except Exception as exc:
            self.logger.error(f"❌ Could not read the commenters: {exc}")
            return []

        targets: List[str] = []
        seen = set()
        for row in rows or []:
            handle = str((row or {}).get("username") or "").strip().lstrip("@").strip()
            if not handle:
                continue
            key = handle.casefold()
            if key in seen:
                continue
            seen.add(key)
            targets.append(handle)

        if not targets:
            self.logger.warning("⚠️ Nobody commented on this video, or no handle could be read")
            return []

        # The operator's own budget still applies on top: reading twenty handles and then visiting
        # five is a legitimate thing to ask for, and the parent's loop already enforces it.
        self.logger.info(f"👥 {len(targets)} commenter(s) resolved: {', '.join(targets[:5])}"
                         + (" ..." if len(targets) > 5 else ""))
        emit_step("analysis", action="commenters_resolved", target=url[:120], count=len(targets))
        self.config.usernames = targets
        return targets

    def run(self, bot_username: str = None) -> FollowersStats:
        """Same loop as the parent, from a source it had to open a video to read."""
        started = time.time()
        stats = super().run(bot_username)
        self.logger.debug(f"post-url run finished in {time.time() - started:.1f}s")
        return stats


__all__ = ["PostUrlConfig", "PostUrlWorkflow", "FollowersConfig"]
