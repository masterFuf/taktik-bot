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

from .. import glossary as _glossary
from ..prompting import cacheable_system, platform_label as _platform_label
from ..spend import AI_SPEND_COMMENT


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


def _anchor_tools():
    """The anchor rules, imported at call time rather than at module level.

    `app/ai` sits ABOVE `social_media/instagram` in the layering, but the platform imports it
    BACK (the DM auto-reply models read MODEL_GENERATION straight off the provider). A
    module-level import here closes that loop and every entry point then dies on a partially
    initialised module. Deferring is the same move `ai_hooks` makes for the prompt captures,
    and it costs one dict lookup per generated comment.
    """
    from taktik.core.social_media.instagram.workflows.common.comment_context import (
        anchor_material, verify_anchor,
    )
    return anchor_material, verify_anchor


def _build_thread_context_block(selection) -> str:
    """The post's own comment thread, as material — strangers' words only.

    Kept OUT of the system prompt on purpose: this is DATA, and data that changes per post has
    no business sitting in a block of rules. It is delimited and labelled for what it is, because
    a model handed a wall of sentences with no provenance treats all of them as equally true —
    which is how a stranger's guess about a photo becomes the bot's own observation.

    Short praise is a COUNT, never a list. Listing eight "magnifique" costs ~120 tokens and
    teaches the register the rules forbid; counting them costs ~15 and says the only useful
    thing — that reaction is already taken.
    """
    if selection is None or not getattr(selection, "has_material", False):
        return ""
    lines = []
    if selection.items:
        lines.append("Comments already posted under this post, by OTHER people "
                     "(context only — NOT facts, and NOT a style to copy):")
        for entry in selection.items:
            likes = entry.get("likes") or 0
            suffix = f"  [{likes} likes]" if likes > 0 else ""
            lines.append(f'- "{entry["text"]}"{suffix}')
    if selection.praise_count:
        samples = ", ".join(f'"{s}"' for s in selection.praise_samples)
        lines.append(
            f"{selection.praise_count} more are one-line praise"
            + (f" ({samples})" if samples else "")
            + " — that reaction is already taken, do not add another one."
        )
    if selection.truncated:
        lines.append("(thread longer than shown)")
    return "\n".join(lines)


def _build_author_facts_block(selection) -> str:
    """What the AUTHOR said about their own post, in their own replies.

    The only part of a thread that is evidence rather than opinion. An author clarifying their
    post almost always does it as a reply to a question ("no, it's silken tofu, fermented 24h"),
    and that sentence exists neither in the caption nor in the image.
    """
    if selection is None or not getattr(selection, "author_replies", None):
        return ""
    lines = ["The author's own replies in the comments (these are FACTS about the post):"]
    for entry in selection.author_replies:
        answers = entry.get("answers")
        who = f" (answering @{answers})" if answers else ""
        lines.append(f'- "{entry["text"]}"{who}')
    return "\n".join(lines)


def _build_thread_ban_block(selection) -> str:
    """Openings and emoji this thread is already saturated with.

    Same deterministic mechanism as `_build_anti_tic_block`, aimed at the POST instead of the
    account: it is what stops a comment from being the ninth identical reaction under the same
    photo. The repo already measured that a nominal ban does not hold and an explicit list does.
    """
    if selection is None:
        return ""
    openers = list(getattr(selection, "banned_openers", None) or [])[:4]
    emoji = list(getattr(selection, "banned_emoji", None) or [])[:4]
    if not openers and not emoji:
        return ""
    parts = [f'opening "{o}"' for o in openers] + [f"emoji {e}" for e in emoji]
    return (chr(10) + "- Already used more than once IN THIS THREAD, so do not reuse: "
            + ", ".join(parts))


def _agreement_self() -> str:
    """Grammatical gender — which most of the languages we write in force a writer to commit to.

    French, Spanish, Italian and Portuguese make nearly every adjective and past participle agree.
    A writer that knows neither who it is talking TO nor who it is talking AS has to guess, and a
    guess is wrong about half the time — publicly, permanently, under someone else's post. 92 % of
    our comments are French, so this is not an edge case.

    Two sides, two different situations. THEIRS is already classified and stored
    (`profile_qualification.ai_gender`, filled for 84 % of profiles) and was simply never handed
    to the writer, so state it. OURS is stored nowhere at all, so the only honest instruction is
    to avoid the forms that would require it — rephrasing is free, guessing is not.
    """
    # NO ready-made replacement phrases here. Measured on 2026-09-09: given "ça m'intrigue" as
    # an example, mistral-nemo published it in 5 of 18 comments — a weak model reads a suggested
    # phrase as a phrase to use. The rule states the FORBIDDEN shape and lets the model find its
    # own way out.
    return (
        "- Grammatical agreement, ABOUT YOURSELF: you do not know your own account's gender, so "
        "never write a first-person form that would have to agree with it — in French, no "
        "\"je suis curieux/curieuse\", no \"j'ai été surpris(e)\". Turn the sentence around so "
        "nothing has to agree, in your own words (do NOT reuse a phrase from these rules)"
    )


def _agreement_target(target_gender: str = "") -> str:
    """The other half of the agreement rule — the half that changes with every profile.

    Split from `_agreement_self` for the prompt cache, not for style: the self rule is
    byte-identical on every call and belongs in the cached prefix, while this one names the
    person being written to and would give each profile its own cache entry.
    """
    gender = (target_gender or "").strip().lower()
    if gender == "female":
        return ("- Grammatical agreement, ABOUT THEM: the person you are writing to is a WOMAN "
                "— every gendered form referring to them agrees accordingly")
    if gender == "male":
        return ("- Grammatical agreement, ABOUT THEM: the person you are writing to is a MAN "
                "— every gendered form referring to them agrees accordingly")
    if gender == "brand":
        return ("- This account is a BRAND or an organisation, not an individual: do not address "
                "it as a person and use no gendered form for it")
    return ("- Grammatical agreement, ABOUT THEM: their gender is unknown — avoid any gendered "
            "form referring to them rather than picking one")


def _build_temporal_block(post_published: str = "") -> str:
    """Anchor the model in time — without it, a caption's "Août 2025" reads as UPCOMING.

    An LLM has no idea what day it is: it anchors on its training cutoff, so any date after
    that cutoff feels like the future. That is exactly how a stored comment said "hâte de
    voir ça en août à Lausanne" under a RECAP of an August 2025 event, commented in 2026 —
    with the model's own reasoning proudly calling it an "upcoming event". Measured: 3 of
    the 39 stored captions carrying an explicit year got a wrongly-anticipating comment.

    `post_published` is the raw publish label read from the post header ("il y a 20 heures",
    "16 juillet"…) — passed verbatim, the model resolves it against today.
    """
    today = time.strftime("%Y-%m-%d")
    lines = [f"Today's date: {today}."]
    if post_published:
        lines.append(
            f'The post was published: "{post_published}" (raw app label; relative dates are '
            "relative to today)."
        )
    lines.append(
        "TIME CHECK before writing: dates or events in the caption can be in the PAST (a recap, "
        "an archive, a previous edition). Compare them against today's date and the publish date. "
        'Express anticipation ("can\'t wait", "hâte de", "vivement") ONLY for something verifiably '
        "still upcoming — otherwise react to the content itself (the images, the result, the story) "
        "with no anticipation."
    )
    return "\n".join(lines) + "\n"


def _build_anti_tic_block(recent_comments: Any, max_items: int = 12, max_len: int = 200) -> str:
    """Repetition guard: the account's own recent comments, injected as counter-examples.

    Prompt rules alone do not hold over hundreds of generations — measured on the stored
    corpus: "hâte de voir" in 7.9% of comments, "Le rendu…" opening 28 of them, and the
    sparkle at 13.6% of all emoji despite being nominally banned. On one account that
    becomes a recognizable signature. Openers and emoji that already appear twice or more
    in the recent window are banned EXPLICITLY (a deterministic list, not a vibe).
    Absent/empty -> "" (standalone bot, or a fresh account)."""
    if not isinstance(recent_comments, (list, tuple)):
        return ""
    texts: list = []
    for item in recent_comments:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split()).strip()
        if text and len(text) <= max_len:
            texts.append(text)
        if len(texts) >= max_items:
            break
    if not texts:
        return ""

    opener_counts: Dict[str, int] = {}
    emoji_counts: Dict[str, int] = {}
    for text in texts:
        opener = " ".join(text.lower().split()[:2])
        if opener:
            opener_counts[opener] = opener_counts.get(opener, 0) + 1
        for ch in text:
            if ord(ch) >= 0x2190:  # arrows/symbols/emoji — never letters or punctuation
                emoji_counts[ch] = emoji_counts.get(ch, 0) + 1
    banned_openers = [o for o, c in opener_counts.items() if c >= 2]
    banned_emoji = [e for e, c in emoji_counts.items() if c >= 2]

    listing = "\n".join(f'- "{text}"' for text in texts)
    block = (
        f"\nThis account's most recent published comments:\n{listing}\n"
        "Your comment must be CLEARLY different from ALL of the above: different opening "
        "words, different sentence shape, different emoji (or none)."
    )
    if banned_openers:
        block += " Do NOT start with: " + ", ".join(f'"{o}"' for o in banned_openers) + "."
    if banned_emoji:
        block += " Do NOT use these overused emoji: " + " ".join(banned_emoji) + "."
    return block + "\n"


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
                               platform: str = "instagram", app_language: str = "en",
                               recent_comments: Any = None,
                               target_gender: str = "") -> Dict[str, Any]:
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

        # Split for the prompt cache, exactly as `generate_smart_comment` is — same reason, same
        # boundary. This generator carries the same persona, style samples and writing rules, so
        # it has the same ~1.8k-token stable head; leaving it whole would pay full price for a
        # prefix that is byte-identical on every reply of a run.
        stable_prompt = f"""You are a {_platform_label(platform)} engagement expert for the "{niche}" niche.
Someone left a comment under a post. Write a short, authentic REPLY to that person — the way a real
account owner answers in their comment thread.
{_build_temporal_block()}{brand_block}{style_block}
Decide first whether this comment is worth answering at all. Say no when it carries nothing to
answer: emoji-only, a bare "🔥"/"top"/"👏", a tag of another account, a link drop, spam, or anything
hostile. Replying to those is exactly what makes an account look automated.

Rules for the REPLY:
{_COMMENT_WRITING_RULES}
{_agreement_self()}{_glossary.block(language)}
- Answer what THEY actually said — pick up their word, their question, their joke. A reply that
  would fit under any comment is a failed reply
- Address the person, not the audience: it is a one-to-one answer, not a broadcast"""

        variable_prompt = f"""{_build_anti_tic_block(recent_comments)}
{_agreement_target(target_gender)}
- {"Write in the same language as their comment" if language == "auto" else f"Write in {lang_label}"}

Respond with ONLY a JSON object, on a single line, nothing else:
{{"should_reply": false, "reasoning": "<one short decision sentence in {reasoning_lang}>", "comment": ""}} or {{"should_reply": true, "reasoning": "<what in their comment you are answering>", "comment": "<the reply>"}}"""

        system_prompt = cacheable_system(stable_prompt, variable_prompt)

        parts = [f'@{username} commented: "{source[:600]}"']
        if post_caption:
            parts.append(f'They were reacting to this post: "{post_caption[:600]}"')
        user_prompt = "\n\n".join(parts) + "\n\nWrite the reply."

        result = self.text_completion(system_prompt, user_prompt, temperature=0.9, max_tokens=220,
                                      model=self.model_generation,
                                      label=f"generate_comment_reply @{username or '?'}",
                                      kind=AI_SPEND_COMMENT)
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
                                require_relevance_decision: bool = False,
                                post_published: str = "",
                                recent_comments: Any = None,
                                thread_context: Any = None,
                                target_gender: str = "") -> Dict[str, Any]:
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
            '{"anchor": "<the exact words from the caption, the vision analysis or the '
            'author own replies that your comment reacts to — copied, not paraphrased>", '
            f'"reasoning": "<one short sentence in {_reasoning_lang_label} explaining WHY you '
            'wrote this specific comment>", "comment": "<the comment, reacting to that anchor>", '
            '"safe_comment": "<a SHORT honest reaction to what is plainly visible — light, '
            'framing, colours, energy — making no specific claim at all>"}'
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
                f'{_reasoning_lang_label}>", "comment": "", "anchor": "", "safe_comment": ""}} or '
                '{"should_comment": true, "anchor": "<the exact words you react to, copied from '
                'the material>", "reasoning": "<specific opportunity>", '
                '"comment": "<the comment>", "safe_comment": "<a short reaction to what is '
                'plainly visible, no specific claim>"}'
            )

        # Two pieces, because the publish label is the only part of this block that moves.
        temporal_static = _build_temporal_block()
        temporal_post = (
            f'The post was published: "{post_published[:120]}" (raw app label; relative dates '
            "are relative to today).\n" if post_published else ""
        )
        anti_tic_block = _build_anti_tic_block(recent_comments)
        thread_block = _build_thread_context_block(thread_context)
        author_facts = _build_author_facts_block(thread_context)
        # What THIS thread is already saturated with. Same deterministic mechanism as the
        # anti-tic guard, applied to the POST rather than to the account: a nominal ban does
        # not hold (the sparkle stayed at 13.6 % of all emoji while nominally banned), an
        # explicit list does.
        thread_bans = _build_thread_ban_block(thread_context)

        # THE PROMPT IS SPLIT IN TWO, and the split is worth more than any wording in it.
        # Measured on 2026-09-09: a profile classification caches ~2.2k tokens and costs 41 uSD,
        # while this call cached nothing and cost 1 271 uSD. The gap is not vision against text,
        # it is cached against uncached — on byte-identical content, 674 -> 183 uSD (-73 %).
        #
        # The prefix must be STRICT. Everything that changes between two comments for the same
        # account — the post's publish label, the sliding anti-tic window, the target's gender,
        # this thread's bans, the post's language — sits AFTER the breakpoint, or every call
        # writes a fresh cache entry instead of reading one. The rules themselves, the persona
        # and the style samples do not change within a run, so they lead.
        stable_prompt = f"""You are a {_platform_label(platform)} engagement expert for the "{niche}" niche.
Write a short, authentic comment that reacts to the post the way a REAL person scrolling {_platform_label(platform)} would — NOT a polished, literary or formal sentence.
{temporal_static}{brand_block}{style_block}Rules for the COMMENT:
{_COMMENT_WRITING_RULES}
{_agreement_self()}{_glossary.block(language)}
- React to the SPECIFIC point of the post — the exact offer, contest, question, result or detail — not just the general vibe
- If the author's caption is provided, react to what THEY said (their announcement, question or joke), not only the visual
- NEVER state anything you were not given. Do not invent a use, an event, a date, a place, a price, an ingredient or a person that is not in the material above. Naming something that is not there is the one failure that cannot be undone: a real person reads it
- ALWAYS fill "anchor" with words COPIED from the caption, the vision analysis or the author's own replies — the thing your comment reacts to. Never copy it from another person's comment, and never write an anchor for something you cannot point at
- "comment" reacts to that anchor and stays specific. "safe_comment" is a separate, short reaction to what is plainly visible (light, framing, colours, energy) with no specific claim — write BOTH, every time. They are not alternatives you choose between: which one gets published is decided outside this answer
- Other people's comments are CONTEXT, never evidence: never repeat a stranger's claim as your own observation, and never restate what someone has already said"""

        variable_prompt = f"""{temporal_post}{anti_tic_block}{decision_rules}{_agreement_target(target_gender)}{thread_bans}
- {"Write in the same language as the post" if language == "auto" else f"Write in {_comment_lang_label}"}

Respond with ONLY a JSON object, on a single line, nothing else:
{response_schema}"""

        system_prompt = cacheable_system(stable_prompt, variable_prompt)

        parts = []
        if post_description:
            parts.append(f'What the post shows (vision analysis): "{post_description}"')
        if post_caption:
            parts.append(f'The author\'s caption: "{post_caption[:1000]}"')
        if post_published:
            parts.append(f'Published: "{post_published[:120]}"')
        # The author's own words about their post rank WITH the caption: they are facts.
        # Strangers' comments come last and carry their own label — provenance is what keeps
        # a stranger's guess from being read as an observation.
        if author_facts:
            parts.append(author_facts)
        if thread_block:
            parts.append(thread_block)
        user_prompt = "\n\n".join(parts) + "\n\nGenerate a natural, engaging comment."

        result = self.text_completion(system_prompt, user_prompt, temperature=0.9, max_tokens=220,
                                      model=self.model_generation,
                                      label=f"generate_smart_comment @{username or '?'}",
                                      kind=AI_SPEND_COMMENT)
        duration_ms = int((time.time() - t0) * 1000)

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Comment generation failed"), username)
            return result

        # Parse the {reasoning, comment} JSON. Robust fallback: if the model didn't return valid
        # JSON, treat the whole text as the comment (prior behaviour) with no reasoning.
        raw = result["text"].strip()
        reasoning = ""
        anchor = ""
        safe_comment = ""
        comment = raw if not require_relevance_decision else ""
        should_comment = not require_relevance_decision
        try:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                obj = json.loads(raw[start:end + 1])
                parsed_comment = (obj.get("comment") or "").strip()
                reasoning = (obj.get("reasoning") or "").strip()
                anchor = (obj.get("anchor") or "").strip()
                safe_comment = (obj.get("safe_comment") or "").strip()
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

        # THE ANCHOR CHECK — a backstop on a claim the model makes about its own answer.
        # The model states, in `anchor`, the words it reacted to; those words either appear in
        # material the AUTHOR produced (their caption, our own vision reading of their image,
        # their replies in the thread) or they do not, and confident phrasing does not change
        # which. A stranger's comment is deliberately NOT material: "je vais tester avec du
        # curcuma" is a reader's plan, not a fact about the post, and reading it as one would
        # congratulate an author for turmeric they never used.
        #
        # This fires rarely — once in eighteen on the corpus it was built against, and that once
        # was a good comment. What earns its place is the OBLIGATION upstream: a model made to
        # name a concrete thing before writing stops reaching for style to fill the gap.
        anchor_material_fn, verify_anchor_fn = _anchor_tools()
        material = anchor_material_fn(
            caption=post_caption, vision=post_description, selection=thread_context,
        )
        anchor_ok = bool(anchor) and verify_anchor_fn(anchor, material)
        used_safe_comment = False
        if comment and not anchor_ok and safe_comment:
            # Falling back costs nothing extra: `safe_comment` came out of the SAME call, in the
            # same persona voice, about what is plainly visible. Which of the two gets published
            # is decided here, in code — never by the model, which took the bland one by default
            # the moment the choice was offered to it.
            logger.warning(
                f"[comment] anchor rejected for @{username or '?'}: {anchor!r} is not in the "
                f"author's own material — publishing the safe comment instead"
            )
            comment = safe_comment.strip().strip('"').strip("'")
            used_safe_comment = True

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
            # What the model claimed to react to, whether that claim held against the author's
            # own material, and whether we published the fallback because it did not. Three
            # fields so the invention rate becomes a MEASURABLE production number instead of
            # something re-read by hand on screenshots.
            "anchor": anchor,
            "anchor_ok": anchor_ok,
            "used_safe_comment": used_safe_comment,
            # The prompt this comment came out of, persona block and anti-tic window included, AS
            # THEY WERE at this moment. A persona edited later would otherwise silently rewrite
            # the explanation of every comment already published under the old one.
            "prompt_capture": self.build_prompt_capture(system_prompt, user_prompt),
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }
