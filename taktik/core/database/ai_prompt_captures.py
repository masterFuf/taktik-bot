"""Write-side facade for the prompt captures.

Same shape as `instagram_posted_comments.py`, and for the same reason: ownership of
`ai_prompt_bodies` / `ai_call_captures` stays in `taktik/core/database/**`, and a workflow that
wants to record what it sent asks for it rather than opening SQLite itself.

Best effort throughout: a capture is diagnostic material. Failing to store one must never cost a
classification or a comment, so every method swallows and returns a falsy value.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from loguru import logger


class AiPromptCaptures:
    """What was sent to a model, recorded next to what came back."""

    @staticmethod
    def _db():
        from taktik.core.database.local.service import LocalDatabaseService

        return LocalDatabaseService()

    @staticmethod
    def record(
        capture: Optional[Dict[str, Any]],
        *,
        kind: str,
        platform: str = "instagram",
        username: Optional[str] = None,
        comment_id: Optional[int] = None,
        model: Optional[str] = None,
        persona: Optional[Dict[str, Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Store one call.

        `capture` is what `AIService.last_prompt_capture()` returns: the hash of the stable half,
        that half's text ONLY when the process has not sent it before, and the small variable half.
        Returns the capture id, which the comment path binds to a `posted_comments.id` once the
        comment is actually published.
        """
        if not capture:
            return None
        try:
            db = AiPromptCaptures._db()
            prompt_hash = capture.get("hash")
            db.prompt_captures.remember_body(prompt_hash, kind, capture.get("system"))
            return db.prompt_captures.record_call(
                kind=kind,
                platform=platform,
                username=username,
                comment_id=comment_id,
                model=model,
                prompt_hash=prompt_hash,
                user_prompt=capture.get("user"),
                persona_json=json.dumps(persona, ensure_ascii=False) if persona else None,
                meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
            )
        except Exception as exc:  # noqa: BLE001 — a capture must never break a run
            logger.debug(f"Could not record prompt capture: {exc}")
            return None

    @staticmethod
    def attach_comment(capture_id: Optional[int], comment_id: Optional[int]) -> bool:
        """Bind a capture to the comment it produced, once that comment exists."""
        if not capture_id or not comment_id:
            return False
        try:
            return AiPromptCaptures._db().prompt_captures.attach_comment_id(capture_id, comment_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Could not attach comment to capture: {exc}")
            return False


__all__ = ["AiPromptCaptures"]
