"""AI decision engine for the Taktik Agent autonomous workflow.

Each method takes a screenshot path + the account's persona block and returns
a structured dict that the workflow uses to decide what action to take.
"""

import json
import time
from typing import Dict, Any, Optional
from loguru import logger

from taktik.core.agent.contracts import AgentAIService


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_FEED_SYSTEM = """You are an AI assistant that controls an Instagram account.
You are shown a screenshot of a post from the Instagram home feed.
Based on the account persona below and the post content, decide what action to take.

--- ACCOUNT PERSONA ---
{persona}
-----------------------

Respond ONLY with a valid JSON object — no markdown, no explanation:
{{
  "action": "skip" | "like" | "like_comment" | "like_save",
  "visit_profile": true | false,
  "comment": "",
  "reason": "one-line reason"
}}

Rules:
- action MUST be one of: skip, like, like_comment, like_save
- skip ~52% of posts — this is normal human behaviour
- like ~35% — for relevant, quality content that fits the niche
- like_comment ~8% — only for high-quality posts where a genuine comment adds value
- like_save ~5% — for content worth saving (tutorials, inspiration, references)
- visit_profile: true only when the author looks like a great connection for the niche
- comment must be natural, 1-2 sentences, no hashtags, at most 1 emoji; empty string if not commenting
- Skip sponsored posts and content completely unrelated to the niche
- Never like posts that are already liked (content-desc will say "Unlike")
"""

_PROFILE_SYSTEM = """You are an AI assistant managing an Instagram account.
You are viewing someone's profile page.
Based on the account persona below, decide whether to follow this person.

--- ACCOUNT PERSONA ---
{persona}
-----------------------

Respond ONLY with a valid JSON object — no markdown, no explanation:
{{
  "follow": true | false,
  "extra_likes": 0,
  "reason": "one-line reason"
}}

Rules:
- follow: true only if clearly relevant to the niche and target audience
- extra_likes: 0, 1, or 2 additional posts to like on this profile (only if following or very relevant)
- Be selective — follow at most ~20% of profiles visited
- Do NOT follow private accounts unless very clearly relevant
"""


class AgentAI:
    """Brain of the Taktik Agent: decides what to do with each feed post and profile."""

    def __init__(self, ai_service: AgentAIService, ipc=None):
        self.ai_service = ai_service
        self.ipc = ipc

    # ------------------------------------------------------------------
    # Feed decision
    # ------------------------------------------------------------------

    def decide_feed_action(
        self,
        screenshot_path: str,
        persona_block: str,
        author_username: str = "unknown",
    ) -> Dict[str, Any]:
        """Decide what action to take on the currently visible feed post.

        Returns:
            {
                "action": "skip" | "like" | "like_comment" | "like_save",
                "visit_profile": bool,
                "comment": str,
                "reason": str,
                "cost_usd": float,
                "model": str,
            }
        """
        system_prompt = _FEED_SYSTEM.format(persona=persona_block)
        user_msg = f"Analyse this feed post and decide what to do. Post author: @{author_username}"

        if self.ipc:
            screenshot_thumb = self._build_screenshot_preview_url(screenshot_path)
            self.ipc.ai_screenshot_analyzing(
                username=author_username,
                prompt=user_msg,
                model=self.ai_service.vision_model,
                image_url=screenshot_thumb,
            )

        t0 = time.time()
        result = self.ai_service.vision_completion(
            system_prompt=system_prompt,
            user_prompt=user_msg,
            image_path=screenshot_path,
            temperature=0.3,
            max_tokens=150,
        )
        duration_ms = int((time.time() - t0) * 1000)

        if not result.get("success"):
            logger.warning(f"[AgentAI] decide_feed_action failed: {result.get('error')}")
            return self._default_skip("AI call failed")

        decision = self._parse_json(result.get("text", ""))
        if decision is None:
            return self._default_skip("JSON parse error")

        # Normalize
        if decision.get("action") not in ("skip", "like", "like_comment", "like_save"):
            decision["action"] = "skip"
        decision.setdefault("visit_profile", False)
        decision.setdefault("comment", "")
        decision.setdefault("reason", "")
        decision["cost_usd"] = result.get("cost_usd", 0.0)
        decision["model"] = result.get("model", self.ai_service.vision_model)

        if self.ipc:
            self.ipc.ai_screenshot_analyzed(
                result=decision.get("reason", decision["action"]),
                username=author_username,
                duration_ms=duration_ms,
                model=decision["model"],
                cost_usd=decision["cost_usd"],
            )
            self.ipc.agent_decision(
                action=decision["action"],
                author=author_username,
                reason=decision.get("reason"),
                visit_profile=decision.get("visit_profile", False),
                comment=decision.get("comment") or None,
                cost_usd=decision["cost_usd"],
                model=decision["model"],
            )

        return decision

    # ------------------------------------------------------------------
    # Profile follow decision
    # ------------------------------------------------------------------

    def decide_profile_follow(
        self,
        screenshot_path: str,
        persona_block: str,
        profile_username: str = "unknown",
    ) -> Dict[str, Any]:
        """Decide whether to follow a profile and how many extra likes to give.

        Returns:
            {
                "follow": bool,
                "extra_likes": int (0-2),
                "reason": str,
                "cost_usd": float,
                "model": str,
            }
        """
        system_prompt = _PROFILE_SYSTEM.format(persona=persona_block)
        user_msg = f"Should I follow @{profile_username}?"

        if self.ipc:
            self.ipc.ai_profile_analyzing(
                username=profile_username,
                prompt=user_msg,
                model=self.ai_service.vision_model,
            )

        t0 = time.time()
        result = self.ai_service.vision_completion(
            system_prompt=system_prompt,
            user_prompt=user_msg,
            image_path=screenshot_path,
            temperature=0.3,
            max_tokens=100,
        )
        duration_ms = int((time.time() - t0) * 1000)

        if not result.get("success"):
            logger.warning(f"[AgentAI] decide_profile_follow failed: {result.get('error')}")
            return {"follow": False, "extra_likes": 0, "reason": "AI call failed", "cost_usd": 0.0}

        decision = self._parse_json(result.get("text", ""))
        if decision is None:
            return {"follow": False, "extra_likes": 0, "reason": "JSON parse error", "cost_usd": 0.0}

        decision.setdefault("follow", False)
        decision.setdefault("extra_likes", 0)
        decision.setdefault("reason", "")
        decision["extra_likes"] = max(0, min(2, int(decision.get("extra_likes") or 0)))
        decision["cost_usd"] = result.get("cost_usd", 0.0)
        decision["model"] = result.get("model", self.ai_service.vision_model)

        if self.ipc:
            self.ipc.ai_profile_analyzed(
                username=profile_username,
                result=f"{'Follow' if decision['follow'] else 'Skip'}: {decision.get('reason', '')}",
                duration_ms=duration_ms,
                model=decision["model"],
                cost_usd=decision["cost_usd"],
                classification={"follow": decision["follow"], "extra_likes": decision["extra_likes"]},
            )

        return decision

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_screenshot_preview_url(self, screenshot_path: str) -> Optional[str]:
        """Best-effort thumbnail for runtime IPC previews."""
        public_builder = getattr(self.ai_service, "image_to_thumbnail_url", None)
        if callable(public_builder):
            return public_builder(screenshot_path)

        legacy_builder = getattr(self.ai_service, "_image_to_thumbnail_url", None)
        if callable(legacy_builder):
            return legacy_builder(screenshot_path)

        return None

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from AI response, stripping markdown fences if needed."""
        text = text.strip()
        if text.startswith("```"):
            parts = text.split("```")
            # Take the block after the first fence
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Partial JSON fallback: try to find the first {...}
            import re
            m = re.search(r'\{.*?\}', text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            logger.warning(f"[AgentAI] Could not parse JSON: {text[:120]}")
            return None

    @staticmethod
    def _default_skip(reason: str) -> Dict[str, Any]:
        return {
            "action": "skip",
            "visit_profile": False,
            "comment": "",
            "reason": reason,
            "cost_usd": 0.0,
            "model": "",
        }
