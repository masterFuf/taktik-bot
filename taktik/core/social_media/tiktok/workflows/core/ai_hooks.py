"""AI hooks for TikTok automation — the TikTok counterpart of the Instagram AI hooks.

Currently installs the **profile relevance verdict** on the Followers workflow: before
interacting with a follower's profile, take a screenshot and ask the AI whether this
profile is worth engaging (relative to OUR account niche), then surface the WHY to the
Taktik Agent panel. Mirrors `instagram/workflows/core/ai_hooks.py` (profile-analysis hook).

Smart comments are intentionally NOT hooked yet — TikTok lacks the type/post-comment
actions (a separate, device-validated lot).

The call itself lives in `qualify_tiktok_profile` rather than inside the hook's closure,
because a second flow now asks the very same question: the new-followers welcome pass judges
a brand-new follower exactly the way the Followers workflow judges a scraped one. A second
spelling of this call is how one of the two ends up paying a vision call it never persists,
or filing a TikTok niche under Instagram — both already happened once here.

Standalone-safe: the verdict is emitted through an injected `emit_relevance` callback
(the bridge wires it to stdout); no `bridges` import here, no-op if not installed.
"""

import os
import tempfile
from typing import Any, Callable, Optional

LogCallback = Callable[[str, str], None]
EmitRelevance = Callable[[str, dict], None]
EmitClassification = Callable[[str, dict], None]
# (device, username) -> the engagement verdict dict, or None when there is no verdict.
ProfileQualifier = Callable[[Any, str], Optional[dict]]


def qualify_tiktok_profile(
    ai: Any,
    device: Any,
    username: str,
    *,
    account_niche: Optional[str] = None,
    account_sub_niche: Optional[str] = None,
    language: str = "en",
    log: LogCallback = lambda level, msg: None,
    emit_relevance: Optional[EmitRelevance] = None,
    emit_classification: Optional[EmitClassification] = None,
) -> Optional[dict]:
    """Screenshot the profile CURRENTLY ON SCREEN, ask the AI, return its engagement verdict.

    Returns the `engagement` block (`relevant`, `score`, `reason`, `follow`, `comment`, `like`)
    or **None** when no verdict could be obtained — an unreadable screen, a provider error, a
    classification that came back without an engagement block. None means "unknown", and a
    caller must never read it as "not relevant": one of them decides whether to write a private
    message, and a failed call is not permission to send one.

    The caller is responsible for being on the right profile. This function does not navigate
    and cannot tell whose screen it is looking at; it names `username` in what it emits, so a
    caller that mis-navigated would file the verdict under the wrong handle.
    """
    if not ai or not username:
        return None

    try:
        tmp_dir = os.path.join(tempfile.gettempdir(), "taktik_ai")
        os.makedirs(tmp_dir, exist_ok=True)
        safe = "".join(c for c in username if c.isalnum() or c in "._-") or "profile"
        screenshot_path = os.path.join(tmp_dir, f"tt_profile_{safe}.png")
        img = device.screenshot_pil()
        if img is None:
            log("warning", f"Pas de capture pour @{username}: aucun verdict IA")
            return None
        img.save(screenshot_path, format="PNG")

        result = ai.classify_profile_niche(
            username=username,
            screenshot_path=screenshot_path,
            profile_context={},
            include_engagement=True,
            account_niche=account_niche,
            account_sub_niche=account_sub_niche,
            platform="tiktok",
            response_language=language,
        )
        classification = (result or {}).get("classification") or {}

        # Persist what the call actually bought. The engagement verdict is account-relative and
        # recomputed every run, but the NICHE is a fact about the profile: paying for it twice
        # is paying for nothing.
        if classification and emit_classification:
            try:
                emit_classification(username, classification)
            except Exception as exc:
                log("warning", f"AI classification not persisted: {exc}")

        engagement = classification.get("engagement")
        if not isinstance(engagement, dict):
            log("warning", f"Verdict IA absent pour @{username} (classification sans engagement)")
            return None

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
        return engagement
    except Exception as exc:
        log("warning", f"AI profile analysis error: {exc}")
        return None


def build_tiktok_profile_qualifier(
    ai: Any,
    ai_config: dict,
    *,
    log: LogCallback = lambda level, msg: None,
    emit_relevance: Optional[EmitRelevance] = None,
    emit_classification: Optional[EmitClassification] = None,
    language: str = "en",
) -> ProfileQualifier:
    """Bind a run's `ai` config to `qualify_tiktok_profile`, once, for every profile it judges.

    Operated account's niche → the verdict is judged relative to it (adjacency-aware).
    Absent → generic "good engagement target?" judgement (front-owned taxonomy).
    """
    account_niche = ai_config.get("accountNiche") or ai_config.get("account_niche")
    account_sub_niche = ai_config.get("accountSubNiche") or ai_config.get("account_sub_niche")

    def qualify(device: Any, username: str) -> Optional[dict]:
        return qualify_tiktok_profile(
            ai,
            device,
            username,
            account_niche=account_niche,
            account_sub_niche=account_sub_niche,
            language=language,
            log=log,
            emit_relevance=emit_relevance,
            emit_classification=emit_classification,
        )

    return qualify


def install_tiktok_ai_hooks(
    ai: Any,
    ai_config: dict,
    *,
    log: LogCallback = lambda level, msg: None,
    emit_relevance: Optional[EmitRelevance] = None,
    emit_classification: Optional[EmitClassification] = None,
    language: str = "en",
) -> None:
    """Install the TikTok AI hooks based on the AI config flags.

    Args:
        ai: an AIService instance (OpenRouter).
        ai_config: the run's `ai` config block (enabled, profileAnalysis, accountNiche…).
        log: (level, message) logger.
        emit_relevance: callback (username, payload) to surface the verdict to the UI.
        emit_classification: callback (username, classification) so the desktop PERSISTS the
            niche. Without it the vision call is paid for and thrown away, and the next pass
            pays again for the same profile — which is what TikTok did until now.
        language: the Taktik APP language — the operator-facing engagement `reason` is written
            in it (shown on the Agent panel). Mirrors the Instagram hook.

    NOTE for a caller looking for a second consumer: this installs a patch on
    `VideoInteractionMixin`, which only the Followers/Target-profiles workflows enter. A flow
    that never touches that mixin (the DM/new-followers workflow does not) gets a hook that
    never fires — call `build_tiktok_profile_qualifier` directly instead.
    """
    if not ai or not ai_config.get("enabled", False):
        return

    if ai_config.get("profileAnalysis", False):
        try:
            from taktik.core.social_media.tiktok.actions.business.workflows.followers.interaction import (
                VideoInteractionMixin,
            )

            original_interact = VideoInteractionMixin._interact_with_profile_posts

            qualify = build_tiktok_profile_qualifier(
                ai,
                ai_config,
                log=log,
                emit_relevance=emit_relevance,
                emit_classification=emit_classification,
                language=language,
            )

            def ai_interact_with_profile_posts(self_wf):
                # Run the relevance verdict ONCE per profile, before interacting. Never let
                # an AI error block the real interaction (fall through to the original).
                try:
                    username = getattr(self_wf, "_current_profile_username", None)
                    if username:
                        qualify(self_wf.device, username)
                except Exception as exc:
                    log("warning", f"AI profile analysis error: {exc}")

                return original_interact(self_wf)

            VideoInteractionMixin._interact_with_profile_posts = ai_interact_with_profile_posts
            log("info", "TikTok AI Profile Analysis hook installed")
        except Exception as exc:
            log("warning", f"Failed to install TikTok Profile Analysis hook: {exc}")


__all__ = [
    "ProfileQualifier",
    "build_tiktok_profile_qualifier",
    "install_tiktok_ai_hooks",
    "qualify_tiktok_profile",
]
