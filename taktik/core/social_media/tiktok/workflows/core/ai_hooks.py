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

from taktik.core.shared.vision.screen_text import screenshot_pil as shared_screenshot_pil

LogCallback = Callable[[str, str], None]
EmitRelevance = Callable[[str, dict], None]
EmitClassification = Callable[[str, dict], None]
# (device, username) -> the engagement verdict dict, or None when there is no verdict.
ProfileQualifier = Callable[[Any, str], Optional[dict]]


def _screenshot_for_ai(device: Any, name: str, *, log: LogCallback) -> Optional[str]:
    """Capture the screen to a file the vision call can read, or None.

    Through the SHARED helper, which accepts both device shapes. `device.screenshot_pil()` is a
    method of the project's facade, and TikTok workflows are handed the RAW uiautomator2 device
    (`DeviceManager.device = u2.connect(...)`) — so every TikTok profile analysis died on
    `'Device' object has no attribute 'screenshot_pil'`, caught and logged as a warning while
    the run carried on. That is the whole reason `profile_qualification` held zero TikTok rows:
    not a missing pipeline, a missing screenshot. Measured on device 2026-08-30.

    One capture path for both AI calls here, so the next one cannot pick the wrong shape again.
    """
    try:
        img = shared_screenshot_pil(device)
        if img is None:
            log("warning", f"Pas de capture pour {name}")
            return None
        tmp_dir = os.path.join(tempfile.gettempdir(), "taktik_ai")
        os.makedirs(tmp_dir, exist_ok=True)
        safe = "".join(c for c in name if c.isalnum() or c in "._-") or "screen"
        path = os.path.join(tmp_dir, f"{safe}.png")
        img.save(path, format="PNG")
        return path
    except Exception as exc:
        log("warning", f"Capture impossible pour {name}: {exc}")
        return None


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
        screenshot_path = _screenshot_for_ai(device, f"tt_profile_{username}", log=log)
        if screenshot_path is None:
            log("warning", f"Pas de capture pour @{username}: aucun verdict IA")
            return None

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


def generate_tiktok_comment(
    ai: Any,
    device: Any,
    username: str,
    *,
    account_persona: Optional[dict] = None,
    app_language: str = "en",
    account_id: Optional[int] = None,
    decision_mode: bool = False,
    log: LogCallback = lambda level, msg: None,
) -> Optional[dict]:
    """A comment for the video ON SCREEN with what produced it, or None to publish nothing.

    Returns `{"comment", "language", "model", "cost_usd", "reasoning", "post_caption"}` — the
    same shape Instagram hands its comment action, so the stored record can answer "which video,
    which model, what did it cost, why this comment" later on. The language in it is the
    COMMENT's, decided below; passing the app language there would file every comment under the
    operator's reading preference.

    None means "say nothing", and every path that returns it is a deliberate silence: no caption
    and no capture (nothing to react to), a language we do not claim to speak, a model that
    answered with an apology instead of a comment. A caller must never turn None into a fallback
    text — a generic line under a stranger's video is the most recognisable bot signature there
    is, which is exactly what having no default list protects against.

    The three decisions around the generation — which language, is this a refusal, what has this
    account said lately — are the SHARED ones (`app/ai/comments/decisions.py`), not TikTok
    copies. They were extracted from the Instagram hook unchanged on 2026-08-30 so both
    platforms ask the same questions; the language rule in particular has an asymmetry that took
    a real incident to find.
    """
    from taktik.core.app.ai.comments.decisions import (
        is_comment_refusal,
        resolve_base_language,
        resolve_comment_language,
    )
    from taktik.core.database.instagram_posted_comments import InstagramPostedComments
    from taktik.core.shared.text import detect_text_language

    from ...actions.core.utils import first_text
    from ...ui.selectors.surfaces.video import VIDEO_MEDIA_SELECTORS

    if not ai:
        return None

    caption = first_text(device, VIDEO_MEDIA_SELECTORS.video_description)
    screenshot_path = _screenshot_for_ai(device, f"tt_post_{username or 'video'}", log=log)
    if not caption and not screenshot_path:
        log("info", f"Rien a lire sur la video de @{username}: pas de commentaire")
        return None

    base_language = resolve_base_language(account_persona)
    comment_language = resolve_comment_language(
        base_language, detect_text_language(caption) if caption else None
    )
    if comment_language is None:
        log(
            "info",
            f"Pas de commentaire pour @{username}: langue du compte "
            f"{base_language or 'inconnue'}, legende hors de ce qu'on parle",
        )
        return None

    try:
        recent = InstagramPostedComments.recent_texts(account_id=account_id, platform="tiktok")
    except Exception:
        recent = []

    try:
        result = ai.generate_smart_comment(
            post_description="",
            username=username or "unknown",
            niche=(account_persona or {}).get("niche") or "general",
            language=comment_language,
            post_caption=caption,
            account_persona=account_persona,
            platform="tiktok",
            app_language=app_language,
            post_screenshot_path=screenshot_path,
            require_relevance_decision=decision_mode,
            recent_comments=recent,
        )
    except Exception as exc:
        log("warning", f"AI comment generation error for @{username}: {exc}")
        return None

    if decision_mode and result.get("success") and result.get("should_comment") is not True:
        log("info", f"Pas de commentaire pour @{username}: {result.get('reasoning') or 'video non pertinente'}")
        return None
    if not (result.get("success") and result.get("comment")):
        return None

    comment = result["comment"]
    if is_comment_refusal(comment):
        log("warning", f"Reponse IA inutilisable pour @{username} — aucun commentaire publie")
        return None
    log("info", f'Commentaire IA pour @{username}: "{comment}"')
    return {
        "comment": comment,
        "language": comment_language,
        "model": result.get("model"),
        "cost_usd": result.get("cost_usd"),
        "reasoning": result.get("reasoning"),
        "post_caption": caption,
        "source": "ai",
    }


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

    if ai_config.get("smartComments", False):
        try:
            # Patched on the SHARED mixin, not on one of its users. `_try_comment_video` lives in
            # `VideoCommentMixin`, which both the followers/target road and the video-feed road
            # (For You, hashtag search) inherit. Patching `VideoInteractionMixin` would bind the
            # attribute on the subclass only and leave the feed running the unpatched original —
            # the hook would log "installed" and never fire there, which is exactly how the
            # profile-analysis hook once installed cleanly onto a workflow that never entered it.
            from taktik.core.social_media.tiktok.actions.business.workflows._internal.video_comment import (
                VideoCommentMixin,
            )

            original_comment = VideoCommentMixin._try_comment_video
            persona = ai_config.get("accountProfile") if isinstance(ai_config, dict) else None
            decision_mode = bool(ai_config.get("commentDecisionMode", False))

            def ai_try_comment_video(self_wf, comment_text=None, ai_metadata=None):
                # Given a text, publish it: the operator's own words are not the AI's business.
                # The same pass-through Instagram's `comment_on_post` does, so the seam is one
                # shape on both platforms rather than two.
                if comment_text:
                    return original_comment(self_wf, comment_text, ai_metadata)

                try:
                    generated = generate_tiktok_comment(
                        ai,
                        self_wf.device,
                        getattr(self_wf, "_current_profile_username", "") or "",
                        account_persona=persona,
                        app_language=language,
                        account_id=getattr(self_wf, "_account_id", None),
                        decision_mode=decision_mode,
                        log=log,
                    )
                except Exception as exc:
                    log("warning", f"AI comment error: {exc}")
                    return False

                # None is a DECISION to stay silent, never a reason to fall back to the run's
                # own list: the AI declined because the video, the language or the answer did
                # not warrant a comment, and posting a canned line instead undoes that.
                if not generated:
                    return False
                # Everything only this hook knows about how the comment was produced travels with
                # it, so the stored record answers "which video, which model, what did it cost,
                # why this comment" later on. `source: "ai"` is also what the anti-tic guard
                # filters on — a template repeating is the operator's choice, not a tic.
                return original_comment(self_wf, generated["comment"], generated)

            VideoCommentMixin._try_comment_video = ai_try_comment_video
            log("info", "TikTok AI Smart Comments hook installed")
        except Exception as exc:
            log("warning", f"Failed to install the TikTok Smart Comments hook: {exc}")


__all__ = [
    "ProfileQualifier",
    "build_tiktok_profile_qualifier",
    "generate_tiktok_comment",
    "install_tiktok_ai_hooks",
    "qualify_tiktok_profile",
]
