"""AI hooks for TikTok automation — the TikTok counterpart of the Instagram AI hooks.

Currently installs the **profile relevance verdict** on the Followers workflow: before
interacting with a follower's profile, take a screenshot and ask the AI whether this
profile is worth engaging (relative to OUR account niche), then surface the WHY to the
Taktik Agent panel. Mirrors `instagram/workflows/core/ai_hooks.py` (profile-analysis hook).

Smart comments are intentionally NOT hooked yet — TikTok lacks the type/post-comment
actions (a separate, device-validated lot).

Standalone-safe: the verdict is emitted through an injected `emit_relevance` callback
(the bridge wires it to stdout); no `bridges` import here, no-op if not installed.
"""

import os
import tempfile
from typing import Any, Callable, Optional

LogCallback = Callable[[str, str], None]
EmitRelevance = Callable[[str, dict], None]


def install_tiktok_ai_hooks(
    ai: Any,
    ai_config: dict,
    *,
    log: LogCallback = lambda level, msg: None,
    emit_relevance: Optional[EmitRelevance] = None,
) -> None:
    """Install the TikTok AI hooks based on the AI config flags.

    Args:
        ai: an AIService instance (OpenRouter).
        ai_config: the run's `ai` config block (enabled, profileAnalysis, accountNiche…).
        log: (level, message) logger.
        emit_relevance: callback (username, payload) to surface the verdict to the UI.
    """
    if not ai or not ai_config.get("enabled", False):
        return

    if ai_config.get("profileAnalysis", False):
        try:
            from taktik.core.social_media.tiktok.actions.business.workflows.followers.interaction import (
                VideoInteractionMixin,
            )

            original_interact = VideoInteractionMixin._interact_with_profile_posts

            # Operated account's niche → the verdict is judged relative to it (adjacency-aware).
            # Absent for now → generic "good engagement target?" judgement (front-owned taxonomy).
            account_niche = ai_config.get("accountNiche") or ai_config.get("account_niche")
            account_sub_niche = ai_config.get("accountSubNiche") or ai_config.get("account_sub_niche")

            def ai_interact_with_profile_posts(self_wf):
                # Run the relevance verdict ONCE per profile, before interacting. Never let
                # an AI error block the real interaction (fall through to the original).
                try:
                    username = getattr(self_wf, "_current_profile_username", None)
                    if username:
                        tmp_dir = os.path.join(tempfile.gettempdir(), "taktik_ai")
                        os.makedirs(tmp_dir, exist_ok=True)
                        safe = "".join(c for c in username if c.isalnum() or c in "._-") or "profile"
                        screenshot_path = os.path.join(tmp_dir, f"tt_profile_{safe}.png")
                        img = self_wf.device.screenshot_pil()
                        if img is not None:
                            img.save(screenshot_path, format="PNG")
                            result = ai.classify_profile_niche(
                                username=username,
                                screenshot_path=screenshot_path,
                                profile_context={},
                                include_engagement=True,
                                account_niche=account_niche,
                                account_sub_niche=account_sub_niche,
                                platform="tiktok",
                            )
                            classification = (result or {}).get("classification") or {}
                            engagement = classification.get("engagement")
                            if isinstance(engagement, dict):
                                would = [v for v, k in (("follow", "follow"), ("comment", "comment"), ("like", "like")) if engagement.get(k)]
                                score = engagement.get("score")
                                score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
                                log(
                                    "info",
                                    (
                                        f"  ↳ pertinence IA @{username}: "
                                        f"{'pertinent' if engagement.get('relevant') else 'non pertinent'} "
                                        f"(score {score_str}) → {', '.join(would) or 'rien'}"
                                        + (f" · {engagement['reason']}" if engagement.get("reason") else "")
                                    ),
                                )
                                if emit_relevance:
                                    emit_relevance(username, {
                                        "relevant": bool(engagement.get("relevant")),
                                        "score": engagement.get("score"),
                                        "reason": engagement.get("reason"),
                                        "follow": bool(engagement.get("follow")),
                                        "comment": bool(engagement.get("comment")),
                                        "like": bool(engagement.get("like")),
                                    })
                except Exception as exc:
                    log("warning", f"AI profile analysis error: {exc}")

                return original_interact(self_wf)

            VideoInteractionMixin._interact_with_profile_posts = ai_interact_with_profile_posts
            log("info", "TikTok AI Profile Analysis hook installed")
        except Exception as exc:
            log("warning", f"Failed to install TikTok Profile Analysis hook: {exc}")
