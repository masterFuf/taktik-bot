"""AI runtime hooks for Instagram automation workflows."""

import os
import tempfile
from typing import Any, Callable, Mapping

from loguru import logger

from taktik.core.shared.telemetry.sink import emit_step
from taktik.core.shared.text import detect_text_language
from taktik.core.social_media.instagram.actions.core.ipc.emitter import IPCEmitter
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_DETAIL_SELECTORS,
)

LogCallback = Callable[[str, str], None]
DecisionProvider = Callable[[Mapping[str, Any]], dict[str, Any]]


def _noop_log(_level: str, _message: str) -> None:
    return None


def _skipped_comment_result(reason: str) -> dict[str, Any]:
    """Keep the CommentAction result contract when AI intentionally declines a post."""
    return {
        "commented": False,
        "comment_text": None,
        "errors": 0,
        "success": False,
        "skipped": True,
        "skip_reason": reason,
    }


# Account/app language aliases → a single code, so the detected POST language (an English name
# like "Spanish") can be compared against the account's preferred language (a code like "es").
# Codes match only exactly; full names match by prefix (so "Slovenian" is never read as English).
_COMMENT_LANG_ALIASES = {
    "fr": ("french", "français", "francais"),
    "en": ("english", "anglais"),
    "es": ("spanish", "español", "espanol", "castellano"),
    "de": ("german", "deutsch", "allemand"),
    "it": ("italian", "italiano", "italien"),
    "pt": ("portuguese", "português", "portugues"),
    "ar": ("arabic", "arabe"),
}


def _detect_language_code(detected_lower: str) -> str:
    for code, names in _COMMENT_LANG_ALIASES.items():
        if detected_lower == code or any(detected_lower.startswith(n) for n in names):
            return code
    return "other"


def _resolve_comment_language(base_lang: str, post_language: Any) -> "str | None":
    """Decide which language to comment in, or None to SKIP the comment entirely.

    `base_lang` is the ACCOUNT's preferred language (the operated account can target an audience
    different from the operator's app UI), falling back to the app language. A comment is read by
    real people, so it follows the POST's language — but only within {base_lang, English}:
      - post in base_lang                 -> comment in base_lang
      - post in English                   -> comment in English (universal 2nd language)
      - post in ANY other detected language -> None (skip): commenting a language we don't claim
        to speak isn't credible
      - language undetected                -> default to base_lang
    """
    base = (base_lang or "en").lower()
    if not post_language:
        return base  # undetected → default to the account/app language
    detected = _detect_language_code(str(post_language).strip().lower())
    if detected == base:
        return base
    if detected == "en":
        return "en"  # English is always allowed as a second language
    return None  # neither the account language nor English → don't comment


def _load_cached_qualification(username: str) -> "dict | None":
    """Return this profile's already-stored AI qualification (niche / category / profession) from the
    local DB, or None if it was never AI-qualified.

    Lets the interaction hook REUSE a prior scraping analysis instead of re-paying for the vision
    classification of a profile we've already qualified — the same dedup the scraping deep-qualify
    path already applies (avoids paying twice for the same profile analysis)."""
    if not username:
        return None
    try:
        from taktik.core.database.local.service import get_local_database

        rows = get_local_database().get_profiles_by_usernames([username]) or []
    except Exception:
        return None
    target = username.lower()
    for row in rows:
        if str(row.get("username", "")).lower() != target:
            continue
        # Only reuse when there is an actual AI classification stored (not just a bare profile row).
        if any([row.get("niche_category"), row.get("niche"), row.get("profession")]):
            return row
    return None


def crop_screenshot_to_post(img: Any, device: Any) -> Any:
    """Crop a full-screen screenshot to the currently visible post area."""
    try:
        width, height = img.size
        crop_top = None
        crop_bottom = None

        for selector in POST_DETAIL_SELECTORS.ai_crop_header_selectors:
            try:
                element = device.xpath(selector)
                if element.exists:
                    bounds = element.info.get("bounds", {})
                    if bounds and bounds.get("top", 0) >= 0:
                        crop_top = max(0, bounds.get("top", 0) - 8)
                        break
            except Exception:
                continue

        for selector in POST_DETAIL_SELECTORS.ai_crop_button_row_selectors:
            try:
                element = device.xpath(selector)
                if element.exists:
                    bounds = element.info.get("bounds", {})
                    if bounds and bounds.get("bottom", 0) > 0:
                        crop_bottom = min(height, bounds.get("bottom", height) + int(height * 0.03))
                        break
            except Exception:
                continue

        if crop_top is not None and crop_bottom is not None:
            if crop_bottom > crop_top + 50:
                return img.crop((0, crop_top, width, crop_bottom))
        elif crop_bottom is not None:
            crop_top = max(0, crop_bottom - int(height * 0.70))
            return img.crop((0, crop_top, width, crop_bottom))
    except Exception:
        pass

    return img


def install_instagram_ai_hooks(
    *,
    ai: Any,
    ai_config: Mapping[str, Any],
    device: Any,
    language: str = "en",
    log: LogCallback = _noop_log,
    decision_provider: "DecisionProvider | None" = None,
) -> None:
    """Install monkey-patches that inject AI behavior into Instagram automation."""
    if not device:
        log("warning", "AI hooks: no device available, skipping")
        return

    # The agent greets the operator with OUR account context at session start ("Bonjour
    # <account>, votre niche est <X>, je cible <audience>…") so the copilot feels like it's
    # talking to us and knows who it works for. Only when a persona was injected.
    persona = ai_config.get("accountProfile") if isinstance(ai_config, dict) else None
    if isinstance(persona, dict) and (persona.get("niche") or persona.get("displayName")):
        # Empty when the persona has no display name — the desktop then shows a localized
        # "your account" fallback (do NOT hardcode a French label here).
        IPCEmitter.emit_action("greeting", persona.get("displayName") or "", {
            "displayName": persona.get("displayName"),
            "niche": persona.get("niche"),
            "audience": persona.get("targetAudience"),
            "objective": persona.get("objective"),
        })

    decision_settings = ai_config.get("decision") or {}
    decision_mode = decision_settings.get("mode") == "decide"

    if ai_config.get("smartComments", False):
        try:
            from taktik.core.social_media.instagram.actions.business.actions.comment.action import (
                CommentAction,
            )

            original_comment_on_post = CommentAction.comment_on_post

            def ai_comment_on_post(
                self_comment,
                comment_text=None,
                template_category="generic",
                custom_comments=None,
                config=None,
                username=None,
            ):
                if comment_text:
                    return original_comment_on_post(
                        self_comment,
                        comment_text=comment_text,
                        template_category=template_category,
                        custom_comments=custom_comments,
                        config=config,
                        username=username,
                    )

                def skip_comment(reason: str, stage: str) -> dict[str, Any]:
                    """Close the live AI attempt and keep CommentAction's dict contract."""
                    IPCEmitter.emit_action("comment_skip", username or "", {
                        "reason": reason,
                        "stage": stage,
                    })
                    emit_step(
                        "comment",
                        action=f"skip_{stage}",
                        target=username,
                        reason=reason,
                    )
                    return _skipped_comment_result(reason)

                try:
                    tmp_dir = os.path.join(tempfile.gettempdir(), "taktik_ai")
                    os.makedirs(tmp_dir, exist_ok=True)
                    screenshot_path = os.path.join(tmp_dir, f'post_{username or "unknown"}.png')
                    img = crop_screenshot_to_post(device.screenshot(), device)
                    img.save(screenshot_path, format="PNG")

                    # The author's ACTUAL caption: expand it ('… plus' / '… more') like a human
                    # reading the post, then read its full text from the UI. The screenshot crop
                    # stops at the button row, so this TEXT channel is the only way the model
                    # sees what the author wrote (announcement, question, wordplay).
                    post_caption = ""
                    try:
                        scroll = getattr(self_comment, "scroll_actions", None)
                        if scroll is not None:
                            scroll._last_reveal_scroll_px = 0
                            scroll.expand_caption_if_truncated()
                            post_caption = scroll.current_caption_text()
                            # Reading may have scrolled down to reveal the caption —
                            # reframe the post so the comment button click that follows
                            # targets THIS post's row, not the next one's.
                            reveal_px = getattr(scroll, "_last_reveal_scroll_px", 0)
                            if reveal_px:
                                scroll._reframe_post_after_reading(reveal_px)
                                scroll._last_reveal_scroll_px = 0
                    except Exception as exc:
                        log("warning", f"Caption read failed for @{username}: {exc}")

                    post_desc = ""
                    post_language = None
                    # A profile-level decision only nominates a comment candidate.
                    # Autonomous mode always analyzes the exact framed post before
                    # publishing, even when the optional broad postAnalysis toggle is off.
                    if ai_config.get("postAnalysis", False) or decision_mode:
                        # Feed the author's caption too: it's the reliable language signal (the post
                        # screenshot often carries stylised/English design text while the post is FR).
                        analysis = ai.analyze_post(
                            screenshot_path=screenshot_path,
                            username=username,
                            response_language=language,
                            post_caption=post_caption,
                        )
                        if analysis.get("success"):
                            post_desc = analysis["description"]
                            post_language = analysis.get("post_language")
                        else:
                            log(
                                "warning",
                                f"Post analysis failed for @{username}: {analysis.get('error')}",
                            )

                    if not post_desc and not post_caption:
                        reason = "no vision description or caption"
                        log("info", f"No post context for @{username} ({reason}), skipping comment (AI mode)")
                        return skip_comment(reason, "missing_context")

                    # The comment's BASE language is the ACCOUNT's preferred language — the reliable
                    # anchor the operator SET (erika.spahn = French). It falls back to the app language
                    # only if the account has none. Persona (niche + brand voice) is injected at launch.
                    account_persona = ai_config.get("accountProfile") if isinstance(ai_config, dict) else None
                    base_lang = (account_persona or {}).get("language") or language

                    # Which language to comment IN is decided from the author's CAPTION (ground truth),
                    # NEVER from the vision model's post_language guess — that guess is unreliable (a
                    # French post whose image carries stylised English design text reads as "english"),
                    # and letting it win over the account language is exactly what made a French account
                    # comment in English. So: caption confidently French/English → follow it; caption
                    # absent/too short/ambiguous → DEFAULT to the account language (never the vision
                    # guess). English is allowed as the universal 2nd language; a third language → skip.
                    caption_lang = detect_text_language(post_caption)
                    vision_lang = _detect_language_code(str(post_language).strip().lower()) if post_language else None
                    if caption_lang and vision_lang and vision_lang != caption_lang:
                        log("info", f"@{username}: comment language from caption = '{caption_lang}' "
                                    f"(vision guessed '{post_language}', ignored)")
                    # Safety veto (vision used ONLY to skip, never to force English): if the caption
                    # gave no verdict but the vision model flags a language that is neither the account's
                    # nor English (e.g. a genuinely Spanish post), skip instead of default-commenting in
                    # the account language on a clearly-foreign post.
                    base_code = str(base_lang or "en").lower()
                    if caption_lang is None and vision_lang and vision_lang not in (base_code, "en"):
                        reason = (
                            f"post looks '{vision_lang}' "
                            f"(neither {base_lang} nor English)"
                        )
                        log("info", f"Skipping comment for @{username}: {reason}")
                        return skip_comment(reason, "vision_language")

                    comment_lang = _resolve_comment_language(base_lang, caption_lang)
                    if comment_lang is None:
                        reason = (
                            f"caption language '{caption_lang}' is outside "
                            f"{{{base_lang}, english}}"
                        )
                        log(
                            "info",
                            f"Skipping comment for @{username}: {reason}",
                        )
                        return skip_comment(reason, "caption_language")
                    result = ai.generate_smart_comment(
                        post_description=post_desc,
                        username=username or "unknown",
                        niche=(account_persona or {}).get("niche") or "general",
                        language=comment_lang,
                        post_caption=post_caption,
                        account_persona=account_persona,
                        app_language=language,
                        post_screenshot_path=screenshot_path,
                        require_relevance_decision=decision_mode,
                    )
                    if (
                        decision_mode
                        and result.get("success")
                        and result.get("should_comment") is not True
                    ):
                        reason = result.get("reasoning") or "post not comment-worthy"
                        log(
                            "info",
                            f"Skipping comment for @{username}: {reason}",
                        )
                        return skip_comment(reason, "post_relevance")
                    if result.get("success") and result.get("comment"):
                        ai_comment = result["comment"]
                        refusal_signals = [
                            "i can't",
                            "i cannot",
                            "i'm unable",
                            "i am unable",
                            "without seeing",
                            "without the image",
                            "without viewing",
                            "no image",
                            "can't see",
                            "cannot see",
                            "don't have access",
                            "do not have access",
                            "provide an image",
                            "share the image",
                            "specific post",
                            "specific content",
                        ]
                        ai_comment_lower = ai_comment.lower()
                        is_refusal = len(ai_comment) > 120 or any(
                            signal in ai_comment_lower for signal in refusal_signals
                        )
                        if is_refusal:
                            reason = "AI response was a refusal or unusable"
                            log(
                                "warning",
                                f"AI comment refused/unusable for @{username}, skipping comment",
                            )
                            return skip_comment(reason, "ai_refusal")
                        log("info", f'AI comment for @{username}: "{ai_comment}"')
                        return original_comment_on_post(
                            self_comment,
                            comment_text=ai_comment,
                            template_category=template_category,
                            custom_comments=None,
                            config=config,
                            username=username,
                            # Everything only this hook knows about how the comment was
                            # produced, so the stored record answers "which post, which
                            # model, what did it cost, why this comment" later on.
                            ai_metadata={
                                "source": "ai",
                                "model": result.get("model"),
                                "cost_usd": result.get("cost_usd"),
                                "reasoning": result.get("reasoning"),
                                "post_caption": post_caption,
                                "post_description": post_desc,
                                "post_author": username,
                                "language": comment_lang,
                            },
                        )

                    log("warning", "AI comment generation failed, falling back to default")
                except Exception as exc:
                    log("warning", f"AI comment hook error: {exc}")

                return original_comment_on_post(
                    self_comment,
                    comment_text=comment_text,
                    template_category=template_category,
                    custom_comments=custom_comments,
                    config=config,
                    username=username,
                )

            CommentAction.comment_on_post = ai_comment_on_post
            log("info", "AI Smart Comments hook installed")
        except Exception as exc:
            log("warning", f"Failed to install Smart Comments hook: {exc}")

    if ai_config.get("profileAnalysis", False) or decision_mode:
        try:
            from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
                InteractionEngineMixin,
            )

            original_perform = InteractionEngineMixin._perform_interactions_on_profile

            # Operated account's niche → the engagement verdict is judged relative to it.
            # Injected by the front into the AI config (taxonomy is front-owned); absent for
            # now → the verdict falls back to a generic "good engagement target?" judgement.
            account_niche = ai_config.get("accountNiche") or ai_config.get("account_niche")
            account_sub_niche = ai_config.get("accountSubNiche") or ai_config.get("account_sub_niche")
            account_persona = (
                ai_config.get("accountProfile")
                if isinstance(ai_config.get("accountProfile"), dict)
                else None
            )

            # Opt-in relevance gating (front-owned settings). Rides on profile_data next to the
            # verdict so the interaction engine can enforce it WITHOUT any config threading —
            # {enabled, minScore, maskIntents, dryRun}. Absent/disabled → engine passthrough.
            relevance_gating = ai_config.get("relevanceGating") or ai_config.get("relevance_gating")

            def _request_agent_decision(
                self_engine,
                username,
                engagement,
                profile_data,
                config,
            ):
                """Ask Electron for one concrete plan and deposit it for the pure executor."""
                if not decision_mode or not isinstance(profile_data, dict):
                    return

                french = str(language).lower().startswith("fr")
                no_verdict_reason = (
                    "Aucun verdict fiable : aucune action n'est exécutée."
                    if french
                    else "No reliable verdict: no action will be executed."
                )
                failed = {
                    "mode": "decide",
                    "ok": False,
                    "error": "AI verdict unavailable",
                    "decision": {
                        "dryRun": bool(decision_settings.get("dryRun", True)),
                        "score": None,
                        "reason": no_verdict_reason,
                        "notes": [no_verdict_reason],
                    },
                }
                if not isinstance(engagement, dict):
                    profile_data["ai_agent_decision"] = failed
                    return
                if decision_provider is None:
                    failed["error"] = "desktop decision provider unavailable"
                    failed["decision"]["reason"] = (
                        "Le décideur premium est indisponible : aucune action n'est exécutée."
                        if french
                        else "The premium decision provider is unavailable: no action will be executed."
                    )
                    profile_data["ai_agent_decision"] = failed
                    return

                session = getattr(self_engine, "session_manager", None)
                snapshot = (
                    session.decision_budget_snapshot()
                    if session is not None and hasattr(session, "decision_budget_snapshot")
                    else {}
                )
                daily = snapshot.get("daily") or {}
                session_usage = snapshot.get("session") or {}
                caps = snapshot.get("caps") or {}
                facts = {
                    "username": username,
                    "engagement": {
                        "relevant": bool(engagement.get("relevant")),
                        "score": engagement.get("score"),
                        "reason": engagement.get("reason"),
                        "relevanceTier": engagement.get("relevance_tier"),
                        "evidence": engagement.get("evidence"),
                        "like": bool(engagement.get("like")),
                        "follow": bool(engagement.get("follow")),
                        "comment": bool(engagement.get("comment")),
                    },
                    "profile": {
                        "followersCount": int(profile_data.get("followers_count", 0) or 0),
                        "followingCount": int(profile_data.get("following_count", 0) or 0),
                        "postsCount": int(profile_data.get("posts_count", 0) or 0),
                        "followButtonState": profile_data.get("follow_button_state"),
                        "relationship": (
                            profile_data.get("relationship")
                            or profile_data.get("relationship_state")
                        ),
                        "niche": profile_data.get("ai_niche"),
                        "nicheCategory": profile_data.get("ai_niche_category"),
                    },
                    "budget": {
                        "daily": {
                            "total": int(daily.get("total", 0) or 0),
                            "follows": int(daily.get("follows", 0) or 0),
                            "comments": int(daily.get("comments", 0) or 0),
                        },
                        "session": {
                            "total": int(session_usage.get("total", 0) or 0),
                            "likes": int(session_usage.get("likes", 0) or 0),
                            "follows": int(session_usage.get("follows", 0) or 0),
                            "comments": int(session_usage.get("comments", 0) or 0),
                        },
                        "caps": {
                            "maxActionsPerDay": int(caps.get("max_actions_per_day", 0) or 0),
                            "maxFollowsPerDay": int(caps.get("max_follows_per_day", 0) or 0),
                            "maxCommentsPerDay": int(caps.get("max_comments_per_day", 0) or 0),
                            "maxActionsPerSession": int(caps.get("max_actions_per_session", 0) or 0),
                        },
                    },
                    "limits": {
                        "maxLikesPerProfile": int(config.get("max_likes_per_profile", 0) or 0),
                        "minLikesPerProfile": int(config.get("min_likes_per_profile", 0) or 0),
                        "maxCommentsPerProfile": max(0, int(
                            config.get("max_comments_per_profile", 1)
                            if config.get("max_comments_per_profile") is not None else 1
                        )),
                        "maxStoriesPerProfile": max(0, int(
                            config.get("max_stories_per_profile", 3)
                            if config.get("max_stories_per_profile") is not None else 3
                        )),
                        "maxStoryLikesPerProfile": max(0, int(
                            config.get("max_story_likes_per_profile", 1)
                            if config.get("max_story_likes_per_profile") is not None else 1
                        )),
                    },
                }
                try:
                    response = decision_provider(facts)
                    if isinstance(response, dict):
                        response_decision = response.get("decision")
                        response_decision = (
                            dict(response_decision)
                            if isinstance(response_decision, dict)
                            else {}
                        )
                        response_decision.setdefault(
                            "dryRun", bool(decision_settings.get("dryRun", True))
                        )
                        profile_data["ai_agent_decision"] = {
                            **response,
                            "mode": "decide",
                            "decision": response_decision,
                        }
                    else:
                        profile_data["ai_agent_decision"] = failed
                except Exception as exc:
                    failed["error"] = str(exc)
                    profile_data["ai_agent_decision"] = failed
                    log("warning", f"Profile decision failed for @{username}: {exc}")

            def _surface_engagement(username, engagement, profile_data):
                """Shared verdict surfacing (vision path AND cached path): deposit the verdict +
                gating settings on profile_data for the interaction engine, log the decision
                trace, and emit the 'relevance' Agent card."""
                if isinstance(profile_data, dict):
                    profile_data["ai_engagement"] = engagement
                    # Hand the gating settings to the engine alongside the verdict
                    # (both consumed in _perform_interactions_on_profile).
                    if relevance_gating:
                        profile_data["ai_relevance_gating"] = relevance_gating
                would = []
                if engagement.get("follow"):
                    would.append("follow")
                if engagement.get("comment"):
                    would.append("comment")
                if engagement.get("like"):
                    would.append("like")
                score = engagement.get("score")
                score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
                log(
                    "info",
                    (
                        f"  ↳ avis IA @{username}: "
                        f"{'pertinent' if engagement.get('relevant') else 'non pertinent'} "
                        f"(score {score_str}) · recommande {', '.join(would) or 'rien'} "
                        f"(le plan final est calculé ensuite)"
                        + (f" · {engagement['reason']}" if engagement.get("reason") else "")
                    ),
                )
                # Same verdict to the RUN LOG (stderr/loguru). `log` above is the injected
                # desktop callback, which only reaches Electron over IPC — so a finished run's
                # log carried no trace of the relevance decision and a post-hoc audit ("why was
                # this off-niche profile engaged?") was impossible. Structured tokens on purpose.
                logger.info(
                    f"[AI-Relevance] @{username} tier={engagement.get('relevance_tier') or '?'} "
                    f"score={score_str} relevant={bool(engagement.get('relevant'))} "
                    f"recommend={','.join(would) or 'none'}"
                    + (f" evidence={engagement['evidence']!r}" if engagement.get("evidence") else "")
                    + (f" reason={engagement['reason']!r}" if engagement.get("reason") else "")
                )
                # Surface the WHY as a proper Agent card (prod + Lab), not just a log:
                # "is this profile worth engaging vs OUR niche, and why".
                IPCEmitter.emit_action("relevance", username, {
                    "relevant": bool(engagement.get("relevant")),
                    "score": engagement.get("score"),
                    "reason": engagement.get("reason"),
                    "relevance_tier": engagement.get("relevance_tier"),
                    "evidence": engagement.get("evidence"),
                    "follow": bool(engagement.get("follow")),
                    "comment": bool(engagement.get("comment")),
                    "like": bool(engagement.get("like")),
                })

            def ai_perform_interactions(self_engine, username, config, profile_data=None):
                if profile_data is None:
                    profile_data = {}
                # Reuse an existing AI qualification instead of re-paying for the vision classification:
                # if this profile was already scraped + AI-qualified (its niche is in the DB), skip the
                # re-analysis entirely. Same dedup the scraping path already applies — a profile's niche
                # is stable, so re-classifying it would just burn tokens for a result we already have.
                cached = _load_cached_qualification(username)
                if cached:
                    niche = cached.get("niche") or cached.get("niche_category") or "?"
                    log("info", f"@{username}: qualification IA déjà en base ({niche}) — réutilisée (pas de nouvelle analyse IA)")
                    if isinstance(profile_data, dict):
                        profile_data["ai_niche"] = cached.get("niche")
                        profile_data["ai_niche_category"] = cached.get("niche_category")
                        profile_data["ai_reused_qualification"] = True
                    # Relevance gating needs a verdict, and this cached path skips the vision call
                    # that produces it — cached profiles used to FAIL-OPEN (never gated). Judge the
                    # KNOWN niche/bio against the account persona with a cheap TEXT-only call (no
                    # screenshot). Account-relative → recomputed per run, never persisted. Any
                    # failure keeps the historic fail-open behaviour.
                    engagement = None
                    if (relevance_gating or decision_mode) and isinstance(profile_data, dict):
                        try:
                            verdict = ai.engagement_verdict_for_known_profile(
                                username=username,
                                cached=cached,
                                account_niche=account_niche,
                                account_sub_niche=account_sub_niche,
                                account_persona=account_persona,
                                response_language=language,
                            )
                            if verdict.get("success") and isinstance(verdict.get("engagement"), dict):
                                engagement = verdict["engagement"]
                                _surface_engagement(username, engagement, profile_data)
                        except Exception as exc:
                            log("warning", f"Cached-profile relevance verdict failed for @{username}: {exc}")
                    _request_agent_decision(
                        self_engine, username, engagement, profile_data, config
                    )
                    return original_perform(self_engine, username, config, profile_data)

                engagement = None
                try:
                    tmp_dir = os.path.join(tempfile.gettempdir(), "taktik_ai")
                    os.makedirs(tmp_dir, exist_ok=True)
                    screenshot_path = os.path.join(tmp_dir, f"profile_{username}.png")
                    img = device.screenshot()
                    img.save(screenshot_path, format="PNG")

                    result = ai.classify_profile_niche(
                        username=username,
                        screenshot_path=screenshot_path,
                        profile_context=profile_data or {},
                        include_engagement=True,
                        account_niche=account_niche,
                        account_sub_niche=account_sub_niche,
                        account_persona=account_persona,
                        response_language=language,
                    )
                    if result.get("success") and result.get("classification"):
                        classification = result["classification"]
                        # The desktop allocator receives factual profile context in
                        # addition to the model's engagement advice. Cached
                        # qualifications already populated these fields, but fresh
                        # vision classifications did not, leaving every new
                        # decision request with a null niche/category.
                        if isinstance(profile_data, dict):
                            profile_data["ai_niche"] = classification.get("niche")
                            profile_data["ai_niche_category"] = classification.get(
                                "niche_category"
                            )
                        log(
                            "info",
                            (
                                f"@{username}: [{classification.get('niche_category', '?')}] "
                                f"{classification.get('niche', '?')} - "
                                f"{classification.get('gender', '?')}, "
                                f"{classification.get('age_group', '?')}"
                            ),
                        )
                        # PERSIST the qualification (front owns the DB/sync): emit the same
                        # ai_profile_done event the scraping path uses, so the desktop upserts
                        # niche/profession/gender/age into the canonical qualification store. Without
                        # this the interaction PAID for the vision classification but never saved it —
                        # the profile stayed unqualified in the DB and got re-analysed (double cost)
                        # on the next pass, which also defeated the _load_cached_qualification reuse.
                        IPCEmitter.emit_profile_classification(
                            username,
                            classification,
                            result=(
                                f"[{classification.get('niche_category', '?')}] "
                                f"{classification.get('niche', '?')}"
                            ),
                        )
                        # Surface the engagement verdict on profile_data. Always displayed as the
                        # decision trace; when relevanceGating.enabled, the interaction engine
                        # ENFORCES it (skip / mask intents) — otherwise it stays observation-only.
                        engagement = classification.get("engagement")
                        if isinstance(engagement, dict):
                            _surface_engagement(username, engagement, profile_data)
                except Exception as exc:
                    log("warning", f"AI profile analysis error for @{username}: {exc}")

                _request_agent_decision(
                    self_engine, username, engagement, profile_data, config
                )
                return original_perform(self_engine, username, config, profile_data)

            InteractionEngineMixin._perform_interactions_on_profile = ai_perform_interactions
            log("info", "AI Profile Analysis hook installed")
        except Exception as exc:
            log("warning", f"Failed to install Profile Analysis hook: {exc}")

    if ai_config.get("postAnalysis", False) and not ai_config.get("smartComments", False):
        try:
            from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
                LikeOrchestration,
            )

            original_like_current = LikeOrchestration.like_current_post

            def ai_like_current_post(self_like):
                try:
                    tmp_dir = os.path.join(tempfile.gettempdir(), "taktik_ai")
                    os.makedirs(tmp_dir, exist_ok=True)
                    screenshot_path = os.path.join(tmp_dir, f"post_like_{id(self_like)}.png")
                    img = crop_screenshot_to_post(device.screenshot(), device)
                    img.save(screenshot_path, format="PNG")
                    ai.analyze_post(
                        screenshot_path=screenshot_path,
                        response_language=language,
                    )
                except Exception as exc:
                    log("warning", f"AI post analysis before like error: {exc}")
                return original_like_current(self_like)

            LikeOrchestration.like_current_post = ai_like_current_post
            log("info", "AI Post Analysis hook installed")
        except Exception as exc:
            log("warning", f"Failed to install Post Analysis hook: {exc}")

    _gating_on = (
        (ai_config.get('relevanceGating') or {}).get('enabled')
        if isinstance(ai_config.get('relevanceGating'), dict) else False
    )
    _modes = (
        f"smartComments={ai_config.get('smartComments')}, "
        f"profileAnalysis={ai_config.get('profileAnalysis')}, "
        f"postAnalysis={ai_config.get('postAnalysis')}, "
        f"decisionMode={decision_mode}, "
        f"relevanceGating={_gating_on}"
    )
    log("info", f"AI hooks installed: {_modes}")
    # Mirror to the RUN LOG (stderr/loguru): `log` only reaches Electron over IPC, so a
    # finished run gave no way to know WHICH AI modes were active. Without it, a legitimate
    # `ai_posts_analyzed=0` (postAnalysis AND decision mode both off) is indistinguishable
    # from a broken counter.
    logger.info(f"[AI-Config] {_modes}")
