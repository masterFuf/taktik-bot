"""Writing a comment, and replying to one — the persona-driven half of the AI.

Moved out of `providers/openrouter.py`, which had grown to carry HTTP transport, image
handling, niche taxonomy, engagement rules AND these generators. AGENTS.md gives this
family its own owner: `app/ai/comments/**`.

Exposed as a mixin rather than free functions so the call sites do not change: the
generators keep reaching `self.text_completion`, `self.model_generation` and `self.ipc`,
which the provider supplies. What moved is the code, not the contract.
"""

import json
import time
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from ..prompting import platform_label as _platform_label


_LANGUAGE_NAMES = {
    'fr': 'French', 'en': 'English', 'es': 'Spanish', 'pt': 'Portuguese',
    'it': 'Italian', 'de': 'German', 'nl': 'Dutch', 'ar': 'Arabic',
}

# The writing rules validated during the model benchmark. Shared by the two
# generators (a comment on a post, a reply to a comment) so a rule proven on one is never
# silently missing from the other — which is exactly how the sparkle-emoji tic reached
# production the first time.
_COMMENT_WRITING_RULES = """- No hashtags
- Write casually and spontaneously: a quick reaction (a few words to one short line), conversational — never stiff or formal
- Do NOT end with a period or other formal end punctuation — real social-media comments almost never end with a full stop
- Emoji: 0 to 2, and each must genuinely FIT this specific message — pick the emoji a real person would actually use here, or none at all. VARY it: never fall back to one default go-to emoji regardless of content (the sparkle is the classic overused reflex). Never emoji-only
- Vary your opening. Do NOT start with formulaic fillers like "C'est tellement vrai", "Tellement vrai", "Super" or "Bravo". Jump straight into a real reaction
- Naming the person: only OCCASIONALLY, and only when it genuinely fits — most replies should NOT name anyone. Never make it a reflex
- Sound genuinely interested, not generic
- Match the energy/tone you are answering"""


def _build_style_block(who: str, samples: Any, max_samples: int = 12, max_len: int = 240) -> str:
    """Few-shot writing-style block: real examples of how the operated account writes.

    `samples` is an optional list of short authentic texts — the account's OWN organic
    comment replies / DMs — scraped and injected by the desktop app. We imitate their
    VOICE (vocabulary, length, punctuation, emoji habits, register), never their content.
    Absent / empty / malformed -> "" so the open-source bot stays generic in standalone
    mode (no dependency on a premium desktop feature).
    """
    if not isinstance(samples, (list, tuple)):
        return ""
    cleaned: list = []
    seen = set()
    for sample in samples:
        if not isinstance(sample, str):
            continue
        text = " ".join(sample.split()).strip()
        if len(text) < 3 or len(text) > max_len:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
        if len(cleaned) >= max_samples:
            break
    if not cleaned:
        return ""
    examples = "\n".join(f'- "{text}"' for text in cleaned)
    return (
        f"\nHere is how {who} ACTUALLY writes — real examples of their own comments/replies:\n"
        f"{examples}\n"
        "Mirror this voice: their vocabulary, sentence length, punctuation habits (or lack of), "
        "emoji usage and level of formality/slang. Imitate the STYLE only — never reuse these "
        "lines or their topics, and keep writing in the language required below.\n"
    )


class CommentGenerationMixin:
    """The comment/persona generators of the AI service."""

    def generate_comment_reply(self, comment_text: str, username: str,
                               niche: str = "general", language: str = "auto",
                               post_caption: str = "", account_persona: dict = None,
                               platform: str = "instagram", app_language: str = "en") -> Dict[str, Any]:
        """Write a reply to somebody's COMMENT under a post (not a comment on the post).

        Same model, same persona voice and the same benchmark-validated writing rules as
        `generate_smart_comment` — only the thing being reacted to changes: a person's
        sentence addressed to the author, rather than a post. That difference is the whole
        prompt: a reply talks TO someone, so it must answer what THEY said.

        Returns `{success, comment, reasoning, should_reply, ...}`. `should_reply` is False
        when the comment offers nothing to answer (an emoji, "🔥🔥", a tag, a spam drop) —
        replying to those is what makes an account look automated.
        """
        t0 = time.time()
        source = (comment_text or "").strip()
        if not source:
            return {"success": False, "error": "No comment text to reply to"}

        persona = account_persona if isinstance(account_persona, dict) else {}
        if persona.get("niche"):
            niche = persona["niche"]
        brand_block, style_block = self._persona_voice_blocks(persona, niche, "replying")

        if self.ipc:
            self.ipc.ai_comment_generating(username, prompt=f"Reply to @{username} ({niche})",
                                           model=self.model_generation, prompt_key="promptSmartComment")

        lang_label = _LANGUAGE_NAMES.get(language, language)
        reasoning_lang = _LANGUAGE_NAMES.get(app_language, 'English')

        system_prompt = f"""You are a {_platform_label(platform)} engagement expert for the "{niche}" niche.
Someone left a comment under a post. Write a short, authentic REPLY to that person — the way a real
account owner answers in their comment thread.
{brand_block}{style_block}
Decide first whether this comment is worth answering at all. Say no when it carries nothing to
answer: emoji-only, a bare "🔥"/"top"/"👏", a tag of another account, a link drop, spam, or anything
hostile. Replying to those is exactly what makes an account look automated.

Rules for the REPLY:
{_COMMENT_WRITING_RULES}
- Answer what THEY actually said — pick up their word, their question, their joke. A reply that
  would fit under any comment is a failed reply
- Address the person, not the audience: it is a one-to-one answer, not a broadcast
- {"Write in the same language as their comment" if language == "auto" else f"Write in {lang_label}"}

Respond with ONLY a JSON object, on a single line, nothing else:
{{"should_reply": false, "reasoning": "<one short decision sentence in {reasoning_lang}>", "comment": ""}} or {{"should_reply": true, "reasoning": "<what in their comment you are answering>", "comment": "<the reply>"}}"""

        parts = [f'@{username} commented: "{source[:600]}"']
        if post_caption:
            parts.append(f'They were reacting to this post: "{post_caption[:600]}"')
        user_prompt = "\n\n".join(parts) + "\n\nWrite the reply."

        result = self.text_completion(system_prompt, user_prompt, temperature=0.9, max_tokens=220,
                                      model=self.model_generation,
                                      label=f"generate_comment_reply @{username or '?'}")
        duration_ms = int((time.time() - t0) * 1000)

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Reply generation failed"), username)
            return result

        # Fail CLOSED on an unparseable answer: publishing raw model output under someone's
        # comment is worse than not replying at all.
        raw = (result.get("text") or "").strip()
        reply, reasoning, should_reply = "", "", False
        try:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                obj = json.loads(raw[start:end + 1])
                reply = (obj.get("comment") or "").strip().strip('"').strip("'")
                reasoning = (obj.get("reasoning") or "").strip()
                should_reply = obj.get("should_reply") is True and bool(reply)
        except Exception:
            logger.debug(f"[AI-Reply] unparseable response for @{username}: {raw[:120]}")

        if not should_reply:
            reply = ""

        if self.ipc and should_reply:
            self.ipc.ai_comment_ready(
                username=username, comment=reply, duration_ms=duration_ms,
                model=result.get("model"), provider="openrouter",
                cost_usd=result.get("cost_usd"), reasoning=reasoning,
                post_description="", post_caption=source, screenshot=None,
            )

        return {
            "success": True,
            "comment": reply,
            "reasoning": reasoning,
            "should_reply": should_reply,
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }

    def _persona_voice_blocks(self, persona: dict, niche: str, verb: str) -> Tuple[str, str]:
        """The brand-voice and writing-style prompt blocks for our operated account."""
        if not persona:
            return "", ""
        who = persona.get("displayName") or "our account"
        voice_bits = []
        if persona.get("tonePersonality"):
            voice_bits.append(f"Voice/tone: {persona['tonePersonality']}")
        if persona.get("objective"):
            voice_bits.append(f"Our goal: {persona['objective']}")
        if persona.get("uniqueSellingPoint"):
            voice_bits.append(f"What sets us apart: {persona['uniqueSellingPoint']}")
        brand_block = (
            f"\nYou are {verb} AS {who} (a \"{niche}\" account). {' '.join(voice_bits)}\n"
            "Let that expertise/voice shine through ONLY where it's natural — it must "
            "stay about THEM and feel like a genuine person, NEVER a sales pitch or self-promo.\n"
        )
        return brand_block, _build_style_block(who, persona.get("writingStyleSamples"))

    def generate_smart_comment(self, post_description: str, username: str,
                                niche: str = "general", language: str = "auto",
                                post_caption: str = "", account_persona: dict = None,
                                platform: str = "instagram", app_language: str = "en",
                                post_screenshot_path: str = None,
                                require_relevance_decision: bool = False) -> Dict[str, Any]:
        """
        Generate a contextual smart comment based on post analysis.
        `post_description` is the vision model's description of the post image;
        `post_caption` is the author's ACTUAL caption text (extracted from the UI after
        expanding it) — when present it grounds the comment in the author's own words.
        `account_persona` (optional) is OUR account's profile (niche/tone/objective/USP) so the
        comment is in OUR brand voice — the operator sets it in the account profile. When absent
        the comment is just a generic genuine reaction.
        Emits IPC events for the AgentPanel.
        """
        t0 = time.time()

        # Our own account voice (from the injected persona) — use its niche, and a short
        # brand-voice block so the comment sounds like US without becoming a sales pitch.
        persona = account_persona if isinstance(account_persona, dict) else {}
        if persona.get("niche"):
            niche = persona["niche"]
        brand_block = ""
        style_block = ""
        if persona:
            who = persona.get("displayName") or "our account"
            voice_bits = []
            if persona.get("tonePersonality"):
                voice_bits.append(f"Voice/tone: {persona['tonePersonality']}")
            if persona.get("objective"):
                voice_bits.append(f"Our goal: {persona['objective']}")
            if persona.get("uniqueSellingPoint"):
                voice_bits.append(f"What sets us apart: {persona['uniqueSellingPoint']}")
            voice = " ".join(voice_bits)
            brand_block = (
                f"\nYou are commenting AS {who} (a \"{niche}\" account). {voice}\n"
                "Let that expertise/voice shine through ONLY where it's natural — the comment must "
                "stay about THEIR post and feel like a genuine person, NEVER a sales pitch or self-promo.\n"
            )
            # Writing-style transfer: real examples of how THIS account actually writes (its own
            # organic comment replies / DMs), scraped by the desktop app and injected on the persona.
            # We imitate the VOICE, never the content. Absent -> "" (generic in standalone).
            style_block = _build_style_block(who, persona.get("writingStyleSamples"))

        if self.ipc:
            self.ipc.ai_comment_generating(username, prompt=f"Smart comment for @{username} ({niche})",
                                           model=self.model_generation, prompt_key="promptSmartComment")

        # Render the target language as a full name in the prompt ("Write in French", not "Write in
        # fr"). "auto" is handled separately (match the post's language).
        _comment_lang_label = _LANGUAGE_NAMES.get(language, language)
        # The REASONING is operator-facing (shown on the Agent card, feeds the autonomous-mode
        # decision trace) so it is written in the APP language, not the comment's language.
        _reasoning_lang_label = _LANGUAGE_NAMES.get(app_language, 'English')

        decision_rules = ""
        response_schema = (
            f'{{"reasoning": "<one short sentence in {_reasoning_lang_label} explaining WHY you '
            'wrote this specific comment>", "comment": "<the comment>"}}'
        )
        if require_relevance_decision:
            decision_rules = """
Before writing, decide whether THIS EXACT POST offers a concrete, authentic comment opportunity
for the operated account. Reject it when the post is unrelated to the account's niche/objective,
too ambiguous, sensitive/personal, purely promotional with nothing specific to react to, or when
the only possible response would be generic praise. Approval requires one explicit detail from the
caption or image that the comment can naturally reference. A strong profile does not make every
one of its posts comment-worthy.
"""
            response_schema = (
                f'{{"should_comment": false, "reasoning": "<one short decision sentence in '
                f'{_reasoning_lang_label}>", "comment": ""}} or '
                '{"should_comment": true, "reasoning": "<specific opportunity>", '
                '"comment": "<the comment>"}'
            )

        system_prompt = f"""You are a {_platform_label(platform)} engagement expert for the "{niche}" niche.
Write a short, authentic comment that reacts to the post the way a REAL person scrolling {_platform_label(platform)} would — NOT a polished, literary or formal sentence.
{brand_block}{style_block}{decision_rules}Rules for the COMMENT:
{_COMMENT_WRITING_RULES}
- React to the SPECIFIC point of the post — the exact offer, contest, question, result or detail — not just the general vibe
- If the author's caption is provided, react to what THEY said (their announcement, question or joke), not only the visual
- {"Write in the same language as the post" if language == "auto" else f"Write in {_comment_lang_label}"}

Respond with ONLY a JSON object, on a single line, nothing else:
{response_schema}"""

        parts = []
        if post_description:
            parts.append(f'What the post shows (vision analysis): "{post_description}"')
        if post_caption:
            parts.append(f'The author\'s caption: "{post_caption[:1000]}"')
        user_prompt = "\n\n".join(parts) + "\n\nGenerate a natural, engaging comment."

        result = self.text_completion(system_prompt, user_prompt, temperature=0.9, max_tokens=220,
                                      model=self.model_generation,
                                      label=f"generate_smart_comment @{username or '?'}")
        duration_ms = int((time.time() - t0) * 1000)

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Comment generation failed"), username)
            return result

        # Parse the {reasoning, comment} JSON. Robust fallback: if the model didn't return valid
        # JSON, treat the whole text as the comment (prior behaviour) with no reasoning.
        raw = result["text"].strip()
        reasoning = ""
        comment = raw if not require_relevance_decision else ""
        should_comment = not require_relevance_decision
        try:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                obj = json.loads(raw[start:end + 1])
                parsed_comment = (obj.get("comment") or "").strip()
                reasoning = (obj.get("reasoning") or "").strip()
                if require_relevance_decision:
                    should_comment = (
                        obj.get("should_comment") is True and bool(parsed_comment)
                    )
                    comment = parsed_comment if should_comment else ""
                else:
                    comment = parsed_comment or raw
        except Exception:
            if not require_relevance_decision:
                comment = raw
        comment = comment.strip().strip('"').strip("'")

        if self.ipc and should_comment:
            # Attach the DECISION CONTEXT to the card: WHY (reasoning), what the post was about
            # (vision description + author caption) and the exact image sent to the model.
            screenshot_url = None
            if post_screenshot_path:
                try:
                    screenshot_url = self._image_to_thumbnail_url(post_screenshot_path, max_size=600)
                except Exception:
                    screenshot_url = None
            self.ipc.ai_comment_ready(
                username=username, comment=comment, duration_ms=duration_ms,
                model=result.get("model"), provider="openrouter",
                cost_usd=result.get("cost_usd"),
                reasoning=reasoning, post_description=post_description,
                post_caption=post_caption, screenshot=screenshot_url,
            )

        return {
            "success": True,
            "comment": comment,
            "reasoning": reasoning,
            "should_comment": should_comment,
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }
