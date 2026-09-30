"""Commenting the video on screen — one implementation, every workflow that has a video.

Extracted from the Followers/Target interaction mixin on 2026-08-30, unchanged, because the For
You page and the hashtag search reach a video by a different road and arrive at the same place.
Leaving the capability in one of the two branches is how the For You page ended up able to like,
follow and favourite a video but not comment on it, while Target could.

Two things the host must provide:

- ``self.device``, ``self.logger`` and ``self.config`` (the usual workflow trio);
- ``_comment_target_username()``, because "who is this comment addressed to" is the one thing the
  two roads know differently: the followers loop holds the profile it is walking, the video feed
  holds the author of the video on screen. Filing it under the wrong one would put the comment in
  somebody else's history and let the anti-tic guard read the wrong voice.
"""

import random
from typing import Optional


class VideoCommentMixin:
    """Post a comment on the video currently on screen, and record what was published."""

    def _comment_target_username(self) -> str:
        """Whose video is this? Overridden by each host; empty when it cannot be told.

        The default covers the followers/target road, which keeps the handle it is walking.
        """
        return getattr(self, "_current_profile_username", "") or ""

    def _try_comment_video(self, comment_text: str = None, ai_metadata: dict = None) -> bool:
        """Comment the video on screen. Returns True only once the comment actually left.

        `comment_text=None` is the seam the AI hook wraps, exactly as Instagram's
        `comment_on_post` does: given a text it publishes it, given none it falls back to the
        run's own list. Same contract on both platforms so the smart-comment hook is the same
        shape twice, not two shapes.

        Until 2026-08-30 the followers branch was `# TODO: Implement commenting` with a `pass`.
        The probability knob and the per-session cap were both read and both honoured — a run
        configured to comment 30% of the time drew the dice, decided yes, and did nothing, then
        reported zero comments as if the dice had said no.
        """
        text = (comment_text or "").strip() or self._pick_configured_comment()
        if not text:
            self.logger.debug("No comment text available — skipping the comment")
            return False

        actions = self._comment_actions()
        if actions is None:
            return False
        try:
            if not actions.open_comments():
                self.logger.debug("Could not open the comment sheet — no comment")
                return False
            posted = actions.post_comment(text)
            if posted:
                self.logger.info(f'💬 Commented: "{text}"')
                self._record_posted_comment(text, ai_metadata)
            return posted
        except Exception as exc:
            self.logger.debug(f"Error commenting: {exc}")
            return False
        finally:
            # A sheet left open hides the next video, and the swipe to it would scroll the
            # comments instead. Closing is part of commenting, not a courtesy.
            try:
                actions.close_comments()
            except Exception:
                pass

    def _comment_actions(self):
        """The shared comment actions, built once per workflow."""
        existing = getattr(self, "_comment_actions_instance", None)
        if existing is not None:
            return existing
        try:
            from taktik.core.social_media.tiktok.actions.atomic.interaction.comment_actions import CommentActions

            self._comment_actions_instance = CommentActions(self.device)
            return self._comment_actions_instance
        except Exception as exc:
            self.logger.debug(f"Comment actions unavailable: {exc}")
            return None

    def _record_posted_comment(self, text: str, ai_metadata: dict = None) -> None:
        """Keep what was published, under platform='tiktok'.

        Not bookkeeping for its own sake: `posted_comments` is what the anti-tic guard reads back
        to show the model what THIS account just said, so it stops repeating its own openers.
        Without this write that guard reads an empty list forever and the guard is a decoration.

        Never raises — the comment is already live on the platform by the time we get here.
        """
        target = self._comment_target_username()
        if not target:
            self.logger.debug("Comment published but its addressee is unknown — not recorded")
            return
        try:
            from taktik.core.database.instagram_posted_comments import InstagramPostedComments

            InstagramPostedComments.record(
                target_username=target,
                comment_text=text,
                account_id=getattr(self, "_account_id", None),
                session_id=getattr(self, "_session_id", None),
                ai_metadata=ai_metadata,
                source="ai" if ai_metadata else "template",
                platform="tiktok",
            )
        except Exception as exc:
            self.logger.debug(f"Could not record the posted comment: {exc}")

    def _pick_configured_comment(self) -> str:
        """One of the run's own comment texts, at random. Empty when the run supplied none.

        Deliberately NOT a built-in default list: a generic "Nice!" under a stranger's video is
        the most recognisable bot signature there is, and a run that forgot to configure texts
        should post nothing rather than that.
        """
        texts = [
            str(t).strip()
            for t in (getattr(self.config, "comment_texts", None) or [])
            if str(t).strip()
        ]
        return random.choice(texts) if texts else ""


__all__ = ["VideoCommentMixin"]
