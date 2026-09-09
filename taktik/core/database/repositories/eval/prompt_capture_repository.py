"""Prompt captures — owner of `ai_prompt_bodies` and `ai_call_captures`.

The Bot is the source of truth: it is the side that builds the prompt, so it is the only side that
can record what was actually sent. The desktop reads these two tables to explain an answer, and
writes nothing.

See `local/schemas/ai_prompt_capture.py` for why the stable half is content-addressed rather than
copied into every row.
"""

from typing import Any, Optional

from loguru import logger

from .._base.base_repository import BaseRepository


class PromptCaptureRepository(BaseRepository):
    """What was sent to a model, per call."""

    def remember_body(self, prompt_hash: str, kind: str, body: Optional[str]) -> bool:
        """Store a prompt body once, and count a use.

        `body` may be None on every call after the first: the caller sends it only when the hash
        is new to its process, because re-sending 9 KB of identical text on every profile is the
        cost this whole design removes. A hash whose body never arrived still counts its uses —
        the row is created empty and filled by the first caller that carries the text, so a
        capture is never lost just because it was not the one holding the body.
        """
        if not prompt_hash:
            return False
        try:
            self.execute(
                """
                INSERT INTO ai_prompt_bodies (hash, kind, body, chars, uses)
                VALUES (?, ?, COALESCE(?, ''), ?, 1)
                ON CONFLICT(hash) DO UPDATE SET
                    uses = uses + 1,
                    last_seen_at = datetime('now'),
                    -- Never overwrite a stored body with an empty one: the first caller to carry
                    -- the text wins, whichever call that was.
                    body  = CASE WHEN excluded.body <> '' THEN excluded.body ELSE ai_prompt_bodies.body END,
                    chars = CASE WHEN excluded.body <> '' THEN excluded.chars ELSE ai_prompt_bodies.chars END
                """,
                (prompt_hash, kind, body, len(body) if body else None),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Could not remember prompt body: {exc}")
            return False

    def record_call(
        self,
        *,
        kind: str,
        platform: str = "instagram",
        username: Optional[str] = None,
        comment_id: Optional[int] = None,
        model: Optional[str] = None,
        prompt_hash: Optional[str] = None,
        user_prompt: Optional[str] = None,
        persona_json: Optional[str] = None,
        meta_json: Optional[str] = None,
    ) -> Optional[int]:
        """Store one call's variable half, pointing at its stable half."""
        try:
            cursor = self.execute(
                """
                INSERT INTO ai_call_captures
                    (platform, kind, username, comment_id, model, prompt_hash,
                     user_prompt, persona, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (platform, kind, username, comment_id, model, prompt_hash,
                 user_prompt, persona_json, meta_json),
            )
            return cursor.lastrowid
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Could not record prompt capture: {exc}")
            return None

    def attach_comment_id(self, capture_id: int, comment_id: int) -> bool:
        """Bind a capture to the comment it produced.

        The comment's id only exists after it is published, and the capture is written when the
        model answers — which is BEFORE we know whether the comment will be posted at all. Writing
        the capture first and binding after is what keeps a refused comment's prompt: those are
        precisely the ones worth reading.
        """
        try:
            self.execute(
                "UPDATE ai_call_captures SET comment_id = ? WHERE id = ?",
                (comment_id, capture_id),
            )
            return True
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"Could not attach comment id to capture: {exc}")
            return False
