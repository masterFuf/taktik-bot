"""Base Video Workflow — shared logic for ForYou and Search workflows.

Centralises: callbacks, stop/pause/resume, like/follow/favorite,
action-decision, limits, pause checks, popup handling, stuck-video detection,
stats dataclass, and _parse_count delegation.

Subclasses only need to implement:
    - run()            — the main entry point
    - _should_skip_video()  (optional override)
"""

from typing import Optional, Dict, Any, Callable
from loguru import logger
import time
import random

from taktik.core.shared.telemetry.sink import emit_step

from .video_comment import VideoCommentMixin
from ....core.utils import parse_count
from .base_workflow import BaseTikTokWorkflow
from .models import VideoWorkflowStats


# ---------------------------------------------------------------------------
# Base workflow
# ---------------------------------------------------------------------------

class BaseVideoWorkflow(VideoCommentMixin, BaseTikTokWorkflow):
    """Base class for video-feed workflows (ForYou, Search, …).

    Inherits from BaseTikTokWorkflow:
        - atomic-action helpers (click, navigation, scroll, detection)
        - popup handler
        - stop / pause / resume / _wait_if_paused
        - _send_stats_update, set_on_stats_callback

    Adds:
        - 4 video-specific callback setters
        - _like_video, _follow_user, _favorite_video
        - _decide_and_execute_actions
        - _check_limits_reached, _check_pause_needed
        - _handle_stuck_video (stuck-video detection)
        - _parse_count (delegate to utils.parse_count)
        - get_stats
    """

    def __init__(self, device, *, module_name: str = "tiktok-video-workflow"):
        super().__init__(device, module_name=module_name)

        # Video-specific callbacks
        self._on_video_callback: Optional[Callable] = None
        self._on_like_callback: Optional[Callable] = None
        self._on_follow_callback: Optional[Callable] = None

        # Stuck-video tracking
        self._last_video_signature: Optional[str] = None
        self._same_video_count = 0

    # ------------------------------------------------------------------
    # Callback setters
    # ------------------------------------------------------------------

    def set_on_video_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called for each video processed."""
        self._on_video_callback = callback

    def set_on_like_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called when a video is liked."""
        self._on_like_callback = callback

    def set_on_follow_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback called when a user is followed."""
        self._on_follow_callback = callback

    # ------------------------------------------------------------------
    # Video actions
    # ------------------------------------------------------------------

    def _like_video(self, video_info: Dict[str, Any]) -> bool:
        """Like the current video."""
        self.logger.info(f"❤️ Liking video by @{video_info.get('author')}")

        if self.click.click_like_button():
            self.stats.videos_liked += 1
            emit_step("like", action="button", target=video_info.get('author'))
            self._send_stats_update()

            if self._on_like_callback:
                try:
                    self._on_like_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Like callback error: {e}")
            return True
        return False

    def _follow_user(self, video_info: Dict[str, Any]) -> bool:
        """Follow the current video's author."""
        self.logger.info(f"👤 Following @{video_info.get('author')}")

        if self.click.click_video_follow_button():
            self.stats.users_followed += 1
            emit_step("follow", action="button", target=video_info.get('author'))
            self._send_stats_update()

            if self._on_follow_callback:
                try:
                    self._on_follow_callback(video_info)
                except Exception as e:
                    self.logger.warning(f"Follow callback error: {e}")
            return True
        return False

    def _favorite_video(self, video_info: Dict[str, Any]) -> bool:
        """Add current video to favorites."""
        self.logger.info(f"⭐ Adding to favorites: @{video_info.get('author')}")

        if self.click.click_favorite_button():
            self.stats.videos_favorited += 1
            emit_step("favorite", action="button", target=video_info.get('author'))
            self._send_stats_update()
            return True
        return False

    # ------------------------------------------------------------------
    # Action decision  (uses config.like_probability etc.)
    # ------------------------------------------------------------------

    def _decide_and_execute_actions(self, video_info: Dict[str, Any]):
        """Decide and execute actions based on probabilities.

        Expects ``self.config`` to expose:
            like_probability, follow_probability, favorite_probability,
            max_likes_per_session, max_follows_per_session
        """
        cfg = self.config
        # The addressee of anything published on this video, read where it is known rather than
        # carried as state: `_comment_target_username` needs it and the feed has no walked profile.
        self._current_video_author = (video_info.get('author') or '').strip()

        # Like
        if (self.stats.videos_liked < cfg.max_likes_per_session
                and random.random() < cfg.like_probability
                and not video_info.get('is_liked')):
            if self._like_video(video_info):
                self._actions_since_pause += 1

        # Follow
        if (self.stats.users_followed < cfg.max_follows_per_session
                and random.random() < cfg.follow_probability):
            if self._follow_user(video_info):
                self._actions_since_pause += 1

        # Favorite
        if (random.random() < cfg.favorite_probability
                and not video_info.get('is_favorited')):
            if self._favorite_video(video_info):
                self._actions_since_pause += 1

        # Comment. Read with getattr because the two configs that reach here gained these knobs
        # later than the rest — a run whose payload predates them must behave exactly as before,
        # which means a probability of zero and no comment.
        comment_probability = getattr(cfg, 'comment_probability', 0.0) or 0.0
        max_comments = getattr(cfg, 'max_comments_per_session', 0) or 0
        commented = getattr(self.stats, 'videos_commented', 0)
        if (comment_probability > 0 and commented < max_comments
                and random.random() < comment_probability):
            if self._try_comment_video():
                if hasattr(self.stats, 'videos_commented'):
                    self.stats.videos_commented += 1
                emit_step("comment", action="sheet", target=video_info.get('author'))
                self._actions_since_pause += 1

        # Repost. Same shape as the comment branch and the same getattr caution: a payload that
        # predates the knob must behave exactly as it did, which means never reposting.
        repost_probability = getattr(cfg, 'repost_probability', 0.0) or 0.0
        max_reposts = getattr(cfg, 'max_reposts_per_session', 0) or 0
        reposted = getattr(self.stats, 'videos_reposted', 0)
        if (repost_probability > 0 and reposted < max_reposts
                and random.random() < repost_probability):
            if self._try_repost_video():
                if hasattr(self.stats, 'videos_reposted'):
                    self.stats.videos_reposted += 1
                emit_step("repost", action="share_sheet", target=video_info.get('author'))
                self._actions_since_pause += 1

    def _try_repost_video(self) -> bool:
        """Put the video on screen on our own profile. False when it did not land.

        Already reposted counts as done, not as a new action -- the counter must not move for a
        video that was already there, or a session reports reposts it did not make.
        """
        from taktik.core.social_media.tiktok.actions.atomic.interaction.repost_actions import RepostActions

        try:
            actions = RepostActions(self.device)
            if actions.is_reposted(sheet_already_open=False) is True:
                self.logger.debug("Repost: cette vidéo est déjà republiée")
                return False
            return actions.repost_video()
        except Exception as exc:
            self.logger.warning(f"Repost impossible: {exc}")
            return False

    def _comment_target_username(self) -> str:
        """On a video feed the addressee is the AUTHOR of the video on screen.

        The default in the mixin reads `_current_profile_username`, which the followers loop
        holds and a feed workflow does not — filing a comment under it here would attribute it
        to nobody, or worse to the last profile some other code touched.

        KNOWN LIMIT, measured 2026-08-30: what the video screen offers is a DISPLAY NAME, not a
        handle. `get_video_author` reads the `title` node or the avatar's description, and both
        say `Kéo` where the handle is `keo2edit` — the handle is not rendered anywhere on that
        screen. So a comment published from the feed is recorded under a display name.

        That is accepted rather than hidden, because of what reads the column: the anti-tic guard
        filters on account and `source='ai'`, never on the target, so it is unaffected. What IS
        affected is any future "have we already commented on this person" question, which would
        silently miss. Getting the handle would mean opening the profile for every comment — a
        visit per gesture — so it is a product trade, not an oversight.
        """
        author = (getattr(self, '_current_video_author', '') or '').strip()
        return author.lstrip('@')

    # ------------------------------------------------------------------
    # Limits & pauses
    # ------------------------------------------------------------------

    def _check_limits_reached(self) -> bool:
        """Check if session limits are reached.

        Lit d'abord ce que le run ne PEUT plus faire, avant ce qu'il n'a plus le DROIT de faire :
        un lien ADB tombe ou un plantage de TikTok laissait cette boucle tourner jusqu'a son
        plafond, en avalant une exception par tour.
        """
        from taktik.core.shared.diagnostics.run_halt import arret_demande
        arret = arret_demande()
        if arret:
            self.logger.warning(f"⛔ Arret : {arret['code']} — {arret.get('detail') or ''}")
            return True

        if self.stats.videos_liked >= self.config.max_likes_per_session:
            self.logger.info("📊 Max likes per session reached")
            return True
        if self.stats.users_followed >= self.config.max_follows_per_session:
            self.logger.info("📊 Max follows per session reached")
            return True
        return False

    def _handle_popups(self) -> bool:
        """Override to also track popup stats."""
        closed = super()._handle_popups()
        if closed:
            self.stats.popups_closed += 1
        return closed

    # ------------------------------------------------------------------
    # Stuck-video detection
    # ------------------------------------------------------------------

    def _handle_stuck_video(self, video_info: Dict[str, Any]) -> bool:
        """Detect if we're stuck on the same video.

        Returns True if stuck was detected and recovery attempted
        (caller should ``continue`` the loop).
        """
        current_author = video_info.get('author', '')
        current_likes = video_info.get('like_count', '')
        signature = f"{current_author}_{current_likes}"

        if signature == self._last_video_signature and current_author:
            self._same_video_count += 1
            self.logger.warning(
                f"⚠️ Same video detected {self._same_video_count} times: @{current_author}"
            )

            if self._same_video_count >= 3:
                self.logger.error("🚨 Stuck on same video! Checking for blocking popups...")
                self.click.close_system_popup()
                time.sleep(0.3)
                self._handle_popups()
                time.sleep(0.3)
                self.device.press("back")
                time.sleep(0.5)
                self._same_video_count = 0
                return True  # caller should continue
        else:
            self._same_video_count = 0
            self._last_video_signature = signature

        return False

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _parse_count(self, count_str: str) -> int:
        """Parse count string (e.g., '1.2K', '500', '1M') to integer."""
        return parse_count(count_str)

    def get_stats(self) -> Dict[str, Any]:
        """Get current workflow statistics."""
        return self.stats.to_dict()
