"""AI runtime hooks for Instagram automation workflows."""

import os
import tempfile
from typing import Any, Callable, Mapping

from taktik.core.social_media.instagram.actions.core.ipc.emitter import IPCEmitter
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_DETAIL_SELECTORS,
)

LogCallback = Callable[[str, str], None]


def _noop_log(_level: str, _message: str) -> None:
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
        IPCEmitter.emit_action("greeting", persona.get("displayName") or "votre compte", {
            "displayName": persona.get("displayName"),
            "niche": persona.get("niche"),
            "audience": persona.get("targetAudience"),
            "objective": persona.get("objective"),
        })

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
                    if ai_config.get("postAnalysis", False):
                        analysis = ai.analyze_post(screenshot_path, username=username)
                        if analysis.get("success"):
                            post_desc = analysis["description"]
                        else:
                            log(
                                "warning",
                                f"Post analysis failed for @{username}: {analysis.get('error')}",
                            )

                    if not post_desc and not post_caption:
                        log("info", f"No post context for @{username} (no vision description, no caption), skipping comment (AI mode)")
                        return False

                    lang = language if language != "en" else "auto"
                    # Use OUR account persona (niche + brand voice), injected into the AI config
                    # at launch from the account profile, so the comment is on-brand — not generic.
                    account_persona = ai_config.get("accountProfile") if isinstance(ai_config, dict) else None
                    result = ai.generate_smart_comment(
                        post_description=post_desc,
                        username=username or "unknown",
                        niche=(account_persona or {}).get("niche") or "general",
                        language=lang,
                        post_caption=post_caption,
                        account_persona=account_persona,
                    )
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
                            log(
                                "warning",
                                f"AI comment refused/unusable for @{username}, skipping comment",
                            )
                            return False
                        log("info", f'AI comment for @{username}: "{ai_comment}"')
                        return original_comment_on_post(
                            self_comment,
                            comment_text=ai_comment,
                            template_category=template_category,
                            custom_comments=None,
                            config=config,
                            username=username,
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

    if ai_config.get("profileAnalysis", False):
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

            def ai_perform_interactions(self_engine, username, config, profile_data=None):
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
                    )
                    if result.get("success") and result.get("classification"):
                        classification = result["classification"]
                        log(
                            "info",
                            (
                                f"@{username}: [{classification.get('niche_category', '?')}] "
                                f"{classification.get('niche', '?')} - "
                                f"{classification.get('gender', '?')}, "
                                f"{classification.get('age_group', '?')}"
                            ),
                        )
                        # Lot 1: surface the engagement verdict on profile_data so the engine
                        # can later GATE follow/comment with it (no decision change yet — we log
                        # it and compare to what the random ratio would do, to vet quality first).
                        engagement = classification.get("engagement")
                        if isinstance(engagement, dict):
                            if isinstance(profile_data, dict):
                                profile_data["ai_engagement"] = engagement
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
                                    f"  ↳ pertinence IA @{username}: "
                                    f"{'pertinent' if engagement.get('relevant') else 'non pertinent'} "
                                    f"(score {score_str}) → {', '.join(would) or 'rien'}"
                                    + (f" · {engagement['reason']}" if engagement.get("reason") else "")
                                ),
                            )
                            # Surface the WHY as a proper Agent card (prod + Lab), not just a log:
                            # "is this profile worth engaging vs OUR niche, and why".
                            IPCEmitter.emit_action("relevance", username, {
                                "relevant": bool(engagement.get("relevant")),
                                "score": engagement.get("score"),
                                "reason": engagement.get("reason"),
                                "follow": bool(engagement.get("follow")),
                                "comment": bool(engagement.get("comment")),
                                "like": bool(engagement.get("like")),
                            })
                except Exception as exc:
                    log("warning", f"AI profile analysis error for @{username}: {exc}")

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
                    ai.analyze_post(screenshot_path)
                except Exception as exc:
                    log("warning", f"AI post analysis before like error: {exc}")
                return original_like_current(self_like)

            LikeOrchestration.like_current_post = ai_like_current_post
            log("info", "AI Post Analysis hook installed")
        except Exception as exc:
            log("warning", f"Failed to install Post Analysis hook: {exc}")

    log(
        "info",
        (
            "AI hooks installed: "
            f"smartComments={ai_config.get('smartComments')}, "
            f"profileAnalysis={ai_config.get('profileAnalysis')}, "
            f"postAnalysis={ai_config.get('postAnalysis')}"
        ),
    )
