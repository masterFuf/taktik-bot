"""
AI Service for bridge scripts — calls OpenRouter API directly from the Python process.

This avoids round-tripping through Electron IPC for AI operations during automation.
The bridge receives the OpenRouter API key via the session config (ai.openrouterApiKey)
and calls the API directly.

Usage:
    from taktik.core.app.ai.providers.openrouter import AIService

    ai = AIService(api_key="sk-or-...", ipc=_ipc)
    result = ai.classify_profile(username="travel_lover", screenshot_path="/tmp/screenshot.png")
    result = ai.analyze_post(screenshot_path="/tmp/post.png")
    result = ai.generate_smart_comment(post_description="...", username="travel_lover", niche="travel")
"""

import time
import base64
import json
import os
import re
from typing import Optional, Dict, Any, Tuple
from loguru import logger

from taktik.core.shared.actions.optional_call import run_bounded_optional

# Two fixed models by task nature (both multimodal). Single source of truth for every LLM call.
MODEL_ANALYSIS = "google/gemini-3.1-flash-lite"     # classify / analyse / describe (high volume)
MODEL_GENERATION = "google/gemini-3-flash-preview"  # comment / DM / persona / scheduler (quality)
# Back-compat aliases for the few `import DEFAULT_*` sites; both resolve to the analysis model.
DEFAULT_TEXT_MODEL = MODEL_ANALYSIS
DEFAULT_VISION_MODEL = MODEL_ANALYSIS

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# urllib's timeout is a socket-inactivity timeout, not a total request deadline. A
# provider can therefore drip bytes and keep a profile run blocked indefinitely.
OPENROUTER_SOCKET_TIMEOUT_SECONDS = 30.0
OPENROUTER_TOTAL_TIMEOUT_SECONDS = 45.0

# Vision models (Gemini) bill images by 768px tiles — a QUANTIZED step, not a continuous
# cost/quality dial: any long edge in (768, 1536] costs the SAME 2 tiles as 1536 itself
# (ceil(edge/768) doesn't change until you cross a multiple of 768). Raw device screenshots
# are ~1080x2220 PNGs → ~6 tiles (~1550 image tokens) raw. 1536 got that down to 2 tiles
# (~-61%, ~750px wide, safe — Kevin validated no quality loss in production 2026-07-07).
# 768 is the next real step DOWN to 1 tile (~-80% vs raw): width drops to ~375px, which
# is a genuine detail loss for VISUAL judgment (post-thumbnail style/aesthetic, subtle
# gender/age cues) — bio/stats/captions aren't at risk, they're sent as TEXT separately
# (scraped, not OCR'd from the image). Kevin explicitly chose 768 in production after
# reviewing a side-by-side comparison (2026-07-07) — re-validate before going lower.
VISION_IMAGE_MAX_EDGE = 768

# Platform display label for prompts (so the provider is reusable across platforms,
# not hardcoded to Instagram). Defaults keep the Instagram wording byte-equivalent.
_PLATFORM_LABELS = {"instagram": "Instagram", "tiktok": "TikTok"}


def _platform_label(platform: str) -> str:
    return _PLATFORM_LABELS.get((platform or "instagram").lower(), (platform or "Instagram").title())


def parse_json_response(text: str) -> Any:
    """Parse a model answer that is supposed to be JSON, tolerating markdown fences.

    Models wrap JSON in ```json ... ``` about half the time. The three call sites that
    needed this each carried their own `text.split("```")[1]`, which breaks on the one
    input that matters: a response cut off mid-answer opens the fence and never closes it,
    so the split yields a fragment and the failure surfaces as a confusing IndexError or
    "Unterminated string". Observed in production on a profile classification whose whole
    answer was ``` ```json\\n{\\n  "n ``` — the profile silently lost its AI qualification.

    Raises ValueError when the text does not contain usable JSON, so every caller reports
    the same way. Never raises IndexError.
    """
    if not text or not text.strip():
        raise ValueError("empty response")

    candidate = text.strip()
    if "```" in candidate:
        # Take what follows the FIRST fence; the closing one may be missing (truncation).
        after_open = candidate.split("```", 1)[1]
        if after_open.lower().startswith("json"):
            after_open = after_open[4:]
        candidate = after_open.split("```", 1)[0].strip()

    if not candidate:
        raise ValueError("no JSON payload in response")

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc


_LANGUAGE_NAMES = {
    'fr': 'French', 'en': 'English', 'es': 'Spanish', 'pt': 'Portuguese',
    'it': 'Italian', 'de': 'German', 'nl': 'Dutch', 'ar': 'Arabic',
}

# The writing rules validated with Kevin during the model benchmark. Shared by the two
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


class AIService:
    """Lightweight OpenRouter client for Bot AI operations."""

    def __init__(self, api_key: str, ipc=None, text_model: str = None, vision_model: str = None,
                 niche_taxonomy: Dict[str, list] = None):
        self.api_key = api_key
        self.ipc = ipc
        # Two fixed models by task. The desktop app no longer injects models; the text_model/
        # vision_model params remain for signature compatibility but are ignored.
        self.model_analysis = MODEL_ANALYSIS
        self.model_generation = MODEL_GENERATION
        # Back-compat aliases: some callers read .vision_model / .text_model for display labels;
        # both point at the analysis model (classification/vision is the common case).
        self.vision_model = MODEL_ANALYSIS
        self.text_model = MODEL_ANALYSIS
        # Premium niche taxonomy injected by the desktop app via the bridge config
        # (slug -> [sub-niche labels]). The open-source bot does NOT own this list;
        # when nothing is injected, profile classification stays free-form so the
        # standalone bot keeps working without the premium taxonomy.
        self.niche_taxonomy: Dict[str, list] = niche_taxonomy or {}

    # ------------------------------------------------------------------
    # Low-level API call
    # ------------------------------------------------------------------

    def _call_openrouter(self, model: str, messages: list, temperature: float = 0.7,
                         max_tokens: int = 2000, label: str = "") -> Dict[str, Any]:
        """Call OpenRouter chat completions API. Returns dict with success, text, usage, cost.

        `label` names the calling operation (classify / comment / post…) for the one-line
        cost log emitted on success — without it a finished run gave no way to tell which
        model actually served a call, nor what each call cost."""
        import urllib.request
        import urllib.error

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://taktik-bot.com",
            "X-Title": "TAKTIK Bot",
        }
        body = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(OPENROUTER_API_URL, data=body, headers=headers, method="POST")

        def request_once() -> Dict[str, Any]:
            try:
                with urllib.request.urlopen(
                    req, timeout=OPENROUTER_SOCKET_TIMEOUT_SECONDS
                ) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    choice = data.get("choices", [{}])[0]
                    text = choice.get("message", {}).get("content", "")
                    usage = data.get("usage", {})
                    # OpenRouter returns cost in usage.cost (not usage.total_cost)
                    cost = usage.get("cost") or usage.get("total_cost")
                    finish_reason = choice.get("finish_reason")
                    # Keep the finish reason so an upstream cut-off is distinguishable
                    # from a malformed model answer.
                    if finish_reason == "length":
                        logger.warning(
                            f"[AIService] {model} hit the {max_tokens}-token ceiling "
                            f"(completion={usage.get('completion_tokens')}); response is truncated"
                        )
                    return {
                        "success": True,
                        "text": text.strip(),
                        "model": data.get("model", model),
                        "provider": "openrouter",
                        "usage": usage,
                        "cost_usd": cost,
                        "finish_reason": finish_reason,
                    }
            except urllib.error.HTTPError as exc:
                error_body = ""
                try:
                    error_body = exc.read().decode("utf-8")
                except Exception:
                    pass
                logger.error(
                    f"[AIService] OpenRouter HTTP {exc.code}: {error_body[:300]}"
                )
                return {
                    "success": False,
                    "error": f"HTTP {exc.code}: {error_body[:200]}",
                }
            except Exception as exc:
                logger.error(f"[AIService] OpenRouter error: {exc}")
                return {"success": False, "error": str(exc)}

        # The worker only performs the HTTP read and has no IPC/UI side effects.
        # If it outlives the deadline, the profile pipeline resumes and emits one
        # normal ai_error from the caller thread; a late response cannot revive a
        # stale Agent card.
        bounded = run_bounded_optional(
            request_once,
            timeout_seconds=OPENROUTER_TOTAL_TIMEOUT_SECONDS,
            label=f"OpenRouter {model} request",
        )
        if bounded.timed_out:
            message = (
                f"OpenRouter request exceeded its "
                f"{OPENROUTER_TOTAL_TIMEOUT_SECONDS:.0f}s total deadline"
            )
            logger.error(f"[AIService] {message}")
            return {"success": False, "error": message}
        if bounded.error is not None:
            logger.error(f"[AIService] OpenRouter worker error: {bounded.error}")
            return {"success": False, "error": str(bounded.error)}
        result = bounded.value
        if not result:
            return {
                "success": False,
                "error": "OpenRouter request ended without a response",
            }
        if result.get("success"):
            # Single audit line per LLM call: which model ACTUALLY served it (the API may
            # route elsewhere than the requested slug), how many tokens, and what it cost.
            # Previously both were captured and silently dropped, so a post-hoc audit of a
            # finished run could not answer "which model ran?" or "where did the cost go?".
            usage = result.get("usage") or {}
            cost = result.get("cost_usd")
            cost_txt = f"${cost:.6f}" if isinstance(cost, (int, float)) else "n/a"
            served = result.get("model") or model
            routed = "" if served == model else f" (requested {model})"
            logger.info(
                f"[AIService] {label or 'call'} · model={served}{routed} · "
                f"tokens={usage.get('prompt_tokens', '?')}+{usage.get('completion_tokens', '?')} · "
                f"cost={cost_txt}"
            )
        return result

    def _image_to_base64_url(self, image_path: str) -> Optional[str]:
        """Convert an image file to a data URL for vision models."""
        if not os.path.isfile(image_path):
            return None
        ext = os.path.splitext(image_path)[1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext.lstrip("."), "image/png")
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"

    def _image_for_vision(self, image_path: str) -> Optional[str]:
        """Downscale + JPEG-encode a screenshot before sending it to the vision model.

        Device screenshots are ~1080x2220 PNGs; sent raw they tile into ~1550 image
        tokens per call on Gemini (the dominant cost of each profile/post analysis).
        Capping the long edge at VISION_IMAGE_MAX_EDGE drops a portrait shot to ~2 tiles
        (~-67%) while keeping the width near 750px, so text stays legible (and
        classify_profile_niche also feeds bio/name as text). Falls back to the raw image
        if PIL is unavailable — never worse than before.
        """
        if not os.path.isfile(image_path):
            return None
        try:
            from PIL import Image as PILImage
            import io
            with PILImage.open(image_path) as img:
                img = img.convert("RGB")
                img.thumbnail((VISION_IMAGE_MAX_EDGE, VISION_IMAGE_MAX_EDGE), PILImage.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85, optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                return f"data:image/jpeg;base64,{b64}"
        except ImportError:
            # PIL missing (open-source standalone): send the raw image, as before.
            return self._image_to_base64_url(image_path)
        except Exception:
            return self._image_to_base64_url(image_path)

    def _image_to_thumbnail_url(self, image_path: str, max_size: int = 400) -> Optional[str]:
        """Convert image to a small JPEG thumbnail for IPC display (lightweight, ~30-60KB)."""
        if not os.path.isfile(image_path):
            return None
        try:
            from PIL import Image as PILImage
            import io
            with PILImage.open(image_path) as img:
                img = img.convert("RGB")
                img.thumbnail((max_size, max_size), PILImage.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=60, optimize=True)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                return f"data:image/jpeg;base64,{b64}"
        except ImportError:
            # PIL not available — send full image (capped at first 200KB of base64)
            return self._image_to_base64_url(image_path)
        except Exception:
            return None

    def _extract_avatar_thumbnail(self, image_path: str, size: int = 64) -> Optional[str]:
        """Crop the profile picture area from an Instagram profile screenshot.

        Instagram Android layout: the avatar circle is in the top-left of the profile
        header, just below the navigation bar. Coordinates are expressed as a fraction
        of image width so they stay consistent across device densities (1080p, 720p…).
        """
        if not os.path.isfile(image_path):
            return None
        try:
            from PIL import Image as PILImage
            import io
            with PILImage.open(image_path) as img:
                img = img.convert("RGB")
                w, h = img.size
                # Only crop when the image is portrait (i.e. a real full screenshot,
                # not an already-resized thumbnail).
                if h > w:
                    x1 = int(0.02 * w)
                    y1 = int(0.19 * w)
                    crop_size = int(0.32 * w)
                    x2 = min(x1 + crop_size, w)
                    y2 = min(y1 + crop_size, h)
                    img = img.crop((x1, y1, x2, y2))
                img = img.resize((size, size), PILImage.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=75)
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                return f"data:image/jpeg;base64,{b64}"
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Text completion
    # ------------------------------------------------------------------

    def text_completion(self, system_prompt: str, user_prompt: str,
                        temperature: float = 0.7, max_tokens: int = 2000,
                        model: str = None, label: str = "text") -> Dict[str, Any]:
        """Simple text completion. Defaults to the analysis model; generation callers pass
        `model=self.model_generation` explicitly."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_openrouter(model or self.model_analysis, messages, temperature,
                                     max_tokens, label=label)

    def classify_following_usernames_batch(
        self,
        usernames: list,
        batch_size: int = 20,
    ) -> Dict[str, Dict[str, str]]:
        """
        Infer niche_category, niche and gender for a list of Instagram usernames
        using text-only LLM (no screenshot required — username is the sole signal).

        Uses the same niche taxonomy as classify_profile_niche for consistency.
        Processes in batches of *batch_size* to keep prompt size manageable.

        Returns a dict: {username: {"niche_category": ..., "niche": ..., "gender": ...}}
        Unclassifiable usernames get niche_category="other", niche="Other", gender="unknown".
        """
        if not usernames:
            return {}

        niche_map = self._niche_map_text()
        system_prompt = (
            "You are an Instagram username analyst.\n"
            "Given a list of Instagram usernames, infer for each:\n"
            "  - niche_category: choose from the keys below\n"
            "  - niche: choose from that category's sub-niches (after the colon)\n"
            "  - gender: 'male', 'female', 'brand' (company/org/product), or 'unknown'\n\n"
            "Niche taxonomy (category: sub-niche1 | sub-niche2 | ...):\n"
            + niche_map + "\n\n"
            "Base your inference solely on the username (words, patterns, name cues, brand signals).\n"
            "IMPORTANT: always try to match an existing sub-niche first. "
            "Only if the account genuinely doesn't fit ANY listed sub-niche, pick the closest niche_category "
            "and write a short descriptive sub-niche label freely (e.g. 'Associative & Non-Profit', 'Motorsport & Racing'). "
            "Do NOT invent a new sub-niche just to be more specific — use the existing one whenever reasonable.\n"
            "Use 'other' / 'Other' / 'unknown' only when no category applies at all.\n"
            "Respond ONLY with a valid JSON object, keys are usernames:\n"
            '{"username1": {"niche_category": "travel", "niche": "Adventure & Backpacking", "gender": "female"}, '
            '"username2": {"niche_category": "other", "niche": "Other", "gender": "unknown"}}'
        )

        results: Dict[str, Dict[str, str]] = {}
        clean = [u for u in usernames if u]

        known_sub_niches = self._known_sub_niches
        # Scale the token budget with the batch size: each username yields a small JSON object, and a
        # full batch of 20 overflowed the old flat 1200 cap — the response was truncated
        # ("Unterminated string") and the WHOLE batch was dropped.
        max_tokens = max(1200, 220 + batch_size * 140)

        def _ingest(username: str, data: Any) -> None:
            if not isinstance(data, dict):
                return
            niche_val = str(data.get("niche") or "Other")
            if niche_val not in known_sub_niches and niche_val != "Other":
                logger.info(f"[AIService] Proposed new sub-niche '{niche_val}' for @{username}")
            results[username] = {
                "niche_category": self._canonicalize_niche_category(data.get("niche_category")),
                "niche": niche_val,
                "gender": str(data.get("gender") or "unknown"),
            }

        for i in range(0, len(clean), batch_size):
            batch = clean[i:i + batch_size]
            user_prompt = "Classify these Instagram usernames:\n" + "\n".join(f"- {u}" for u in batch)
            text = ""
            try:
                result = self.text_completion(system_prompt, user_prompt, temperature=0.1,
                                              max_tokens=max_tokens,
                                              label=f"classify_following_batch ({len(batch)})")
                if not result.get("success"):
                    logger.warning(f"[AIService] classify_following_usernames_batch failed: {result.get('error')}")
                    continue
                text = result["text"].strip()
                batch_result = parse_json_response(text)
                for username, data in batch_result.items():
                    _ingest(username, data)
            except Exception as e:
                # A truncated/malformed batch used to be dropped whole. Salvage every COMPLETE
                # "username": {...} entry so a cut-off tail loses only its last (partial) item.
                salvaged = self._salvage_batch_entries(text)
                for username, data in salvaged.items():
                    _ingest(username, data)
                logger.warning(
                    f"[AIService] classify_following_usernames_batch batch error: {e}; "
                    f"salvaged {len(salvaged)}/{len(batch)} entr(y/ies)"
                )
                continue

        return results

    # ------------------------------------------------------------------
    # Vision completion
    # ------------------------------------------------------------------

    def vision_completion(self, system_prompt: str, user_prompt: str, image_path: str,
                          temperature: float = 0.3, max_tokens: int = 1500,
                          label: str = "vision") -> Dict[str, Any]:
        """Vision completion — sends an image + prompt to the vision model."""
        # Downscaled + JPEG (see _image_for_vision): device screenshots are huge PNGs and
        # the image dominates each vision call's token cost. Never sends more than the raw.
        image_url = self._image_for_vision(image_path)
        if not image_url:
            return {"success": False, "error": f"Image not found: {image_path}"}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": user_prompt},
            ]},
        ]
        return self._call_openrouter(self.vision_model, messages, temperature, max_tokens,
                                     label=label)

    def vision_json_completion(self, system_prompt: str, user_prompt: str, image_path: str,
                               temperature: float = 0.3, max_tokens: int = 1500,
                               label: str = "vision") -> Dict[str, Any]:
        """Vision completion whose answer must be JSON — retried once if it comes back unusable.

        Upstream truncation is rare but real: replaying the exact production call 9 times in a
        row returned clean JSON every time (~230-390 completion tokens against a 1100 ceiling),
        yet a live run got a completion cut after four characters. A single retry therefore
        recovers it with very high probability, and costs nothing on the normal path.

        Returns the usual completion dict plus `payload` (the parsed JSON) on success, or
        success=False with `error`/`raw` when both attempts failed to parse.
        """
        last: Dict[str, Any] = {}
        for attempt in (1, 2):
            last = self.vision_completion(system_prompt, user_prompt, image_path,
                                          temperature=temperature, max_tokens=max_tokens,
                                          label=label)
            if not last.get("success"):
                return last  # transport/HTTP failure: retrying here would just double the wait

            try:
                last["payload"] = parse_json_response(last.get("text", ""))
                return last
            except ValueError as exc:
                finish = last.get("finish_reason")
                if attempt == 1:
                    logger.warning(
                        f"[AIService] {label}: unusable answer ({exc}; finish_reason={finish}) — retrying once"
                    )
                    continue
                logger.warning(f"[AIService] {label}: unusable answer after retry ({exc}; finish_reason={finish})")
                return {
                    "success": False,
                    "error": f"JSON parse error: {exc}",
                    "raw": last.get("text", ""),
                    "finish_reason": finish,
                }
        return last

    def _extract_partial_classification(self, text: str) -> Optional[Dict[str, Any]]:
        """Fallback parser: extract key fields from a truncated/malformed JSON string."""
        import re
        result: Dict[str, Any] = {}

        for field in ("niche_category", "niche", "summary", "language", "content_type", "country"):
            m = re.search(rf'"{field}"\s*:\s*"([^"]*)', text)
            if m:
                result[field] = m.group(1)
        # cities array fallback
        m = re.search(r'"cities"\s*:\s*\[([^\]]*)', text)
        if m:
            raw = m.group(1)
            result["cities"] = [t.strip().strip('"') for t in raw.split(',') if t.strip().strip('"')]

        # tags array (may also be truncated)
        m = re.search(r'"tags"\s*:\s*\[([^\]]*)', text)
        if m:
            raw_tags = m.group(1)
            result["tags"] = [t.strip().strip('"') for t in raw_tags.split(",") if t.strip().strip('"')]

        return result if result.get("niche_category") else None

    def _salvage_batch_entries(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Recover complete '"username": { ... }' objects from a truncated/malformed batch JSON,
        so a cut-off response loses only its last (incomplete) entry instead of the whole batch.
        The batch entries are flat objects (no nesting), so a non-greedy brace match is enough."""
        import re
        salvaged: Dict[str, Dict[str, Any]] = {}
        if not text:
            return salvaged
        for m in re.finditer(r'"([^"\\]+)"\s*:\s*(\{[^{}]*\})', text):
            try:
                salvaged[m.group(1)] = json.loads(m.group(2))
            except json.JSONDecodeError:
                continue
        return salvaged

    # ------------------------------------------------------------------
    # High-level AI operations
    # ------------------------------------------------------------------

    # Ordered list of supported niche categories (must match NICHE_CATEGORIES in niche-taxonomy.ts)
    NICHE_CATEGORIES = [
        "lifestyle", "travel", "fitness_sports", "food_drink", "fashion",
        "beauty_wellness", "tech_education", "business_marketing", "music_entertainment",
        "art_design", "finance", "health_family", "home_interior", "events_services",
        "community_causes", "other",
    ]

    # Free-text drift the model actually produces, mapped back onto the canonical buckets.
    # Built from real runs (626/627, 2026-07-24): the model returned `fashion_and_beauty`,
    # `personal_blog`, `spam`, and four spellings of arts_* despite the prompt listing the keys.
    _NICHE_CATEGORY_SYNONYMS = {
        # entertainment / culture cluster
        "arts_and_entertainment": "music_entertainment",
        "arts_entertainment": "music_entertainment",
        "entertainment": "music_entertainment",
        "arts_and_culture": "music_entertainment",
        "music": "music_entertainment",
        "cinema": "music_entertainment",
        "film_and_cinema": "music_entertainment",
        "media": "music_entertainment",
        # visual arts / craft / literature
        "art": "art_design",
        "arts": "art_design",
        "design": "art_design",
        "art_and_design": "art_design",
        "arts_and_crafts": "art_design",
        "crafts": "art_design",
        "photography": "art_design",
        "books_and_literature": "art_design",
        "literature": "art_design",
        # beauty
        "beauty": "beauty_wellness",
        "wellness": "beauty_wellness",
        "cosmetics": "beauty_wellness",
        "fashion_and_beauty": "beauty_wellness",
        # lifestyle
        "personal_lifestyle": "lifestyle",
        "personal_blog": "lifestyle",
        "lifestyle_blog": "lifestyle",
        "blog": "lifestyle",
        "blogger": "lifestyle",
        # food
        "food": "food_drink",
        "food_and_drink": "food_drink",
        "food_and_beverage": "food_drink",
        "restaurant": "food_drink",
        "cooking": "food_drink",
        # business
        "business": "business_marketing",
        "business_and_entrepreneurship": "business_marketing",
        "entrepreneurship": "business_marketing",
        "marketing": "business_marketing",
        # home
        "home_improvement": "home_interior",
        "home_and_garden": "home_interior",
        "home_decor": "home_interior",
        "interior_design": "home_interior",
        # fitness / sports
        "fitness": "fitness_sports",
        "sports": "fitness_sports",
        "health_and_fitness": "fitness_sports",
        # health / family
        "health": "health_family",
        "family": "health_family",
        "parenting": "health_family",
        "family_and_parenting": "health_family",
        "health_and_family": "health_family",
        # tech / education
        "tech": "tech_education",
        "technology": "tech_education",
        "education": "tech_education",
        # travel
        "travel_and_tourism": "travel",
        "tourism": "travel",
        # finance
        "finance_and_investing": "finance",
        "investing": "finance",
        # events / services
        "events": "events_services",
        "services": "events_services",
        # community
        "community": "community_causes",
        "causes": "community_causes",
        "nonprofit": "community_causes",
        # junk / non-buckets
        "spam": "other",
        "scam": "other",
        "spam_and_scam": "other",
        "unknown": "other",
        "none": "other",
    }

    @classmethod
    def _canonicalize_niche_category(cls, raw: Any) -> str:
        """Clamp a model-emitted niche_category onto the 16 canonical buckets.

        The classification prompt lists the allowed keys, but the output was never
        validated: real runs persisted free-text slugs into the indexed
        profile_following.niche_category column, fragmenting one concept across
        several spellings. Resolution order: exact match, then synonym remap, then
        single-token overlap; anything ambiguous fails closed to 'other'.
        """
        if not raw:
            return "other"
        slug = re.sub(r"[^a-z0-9]+", "_", str(raw).strip().lower()).strip("_")
        if not slug:
            return "other"
        if slug in cls.NICHE_CATEGORIES:
            return slug
        mapped = cls._NICHE_CATEGORY_SYNONYMS.get(slug)
        if mapped:
            return mapped
        # Last resort: token overlap with the canonical buckets (unique winner only).
        stop = {"and", "the", "of", "a"}
        tokens = {t for t in slug.split("_") if t and t not in stop}
        best, best_overlap, tied = "other", 0, False
        for cat in cls.NICHE_CATEGORIES:
            overlap = len(tokens & set(cat.split("_")))
            if overlap > best_overlap:
                best, best_overlap, tied = cat, overlap, False
            elif overlap == best_overlap and overlap > 0:
                tied = True
        if best_overlap > 0 and not tied:
            logger.debug(f"[AIService] niche_category '{raw}' clamped to '{best}' (token overlap)")
            return best
        logger.debug(f"[AIService] niche_category '{raw}' not recognized — clamped to 'other'")
        return "other"

    @property
    def _known_sub_niches(self) -> set:
        """Flat set of all injected sub-niche labels (premium taxonomy, may be empty)."""
        return {s for subs in self.niche_taxonomy.values() for s in subs}

    def _niche_map_text(self) -> str:
        """Render the injected taxonomy as a 'category: sub1 | sub2' block.

        Returns a free-form hint when no premium taxonomy is injected, so the
        standalone open-source bot still produces a usable classification.
        """
        if not self.niche_taxonomy:
            return "  (no taxonomy provided — infer a concise niche_category slug and a short niche label)"
        return "\n".join(
            f"  {cat}: {' | '.join(subs)}" for cat, subs in self.niche_taxonomy.items()
        )

    @staticmethod
    def _normalize_engagement(raw: Any) -> Optional[Dict[str, Any]]:
        """Coerce the model's `engagement` block into a safe, typed verdict (or None).

        The semantic tier is mandatory. Weak, missing or malformed evidence fails
        closed. An adjacent profile may receive a discovery like, but never a
        follow or comment from this profile-level verdict alone.
        """
        if not isinstance(raw, dict):
            return None

        score = raw.get("score")
        try:
            score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            score = None

        reason = raw.get("reason")
        reason = reason.strip()[:200] if isinstance(reason, str) else None
        evidence = raw.get("evidence")
        evidence = evidence.strip()[:240] if isinstance(evidence, str) else None

        tier = str(raw.get("relevance_tier") or "").strip().lower()
        if tier not in {"direct", "adjacent", "weak", "none"}:
            tier = "none"
        if tier in {"direct", "adjacent"} and not evidence:
            tier = "weak"

        # The model chooses one semantic tier; deterministic code derives the
        # permitted candidates. This avoids asking a small model for four
        # correlated booleans that it can copy mechanically from an example.
        relevant = tier in {"direct", "adjacent"}
        follow = tier == "direct"
        comment = tier == "direct"
        like = tier in {"direct", "adjacent"}

        if tier == "adjacent":
            if score is not None:
                score = min(score, 0.79)
        elif tier == "weak":
            relevant = False
            follow = comment = like = False
            if score is not None:
                score = min(score, 0.44)
        elif tier == "none":
            relevant = False
            follow = comment = like = False
            if score is not None:
                score = min(score, 0.20)
        return {
            "relevant": relevant,
            "relevance_tier": tier,
            "evidence": evidence,
            "follow": follow,
            "comment": comment,
            "like": like,
            "score": score,
            "reason": reason,
        }

    @staticmethod
    def _engagement_relativity(
        account_niche: Optional[str],
        account_sub_niche: Optional[str],
        account_persona: Optional[Dict[str, Any]] = None,
    ) -> str:
        """The shared 'judge THIS profile relative to OUR account' instruction — single source for
        both the vision classification and the text-only cached-profile verdict, so the two paths
        can never drift apart in what 'relevant' means."""
        persona = account_persona if isinstance(account_persona, dict) else {}
        niche = account_niche or persona.get("niche")
        if niche:
            identity = f"Niche: {niche}"
            if account_sub_niche:
                identity += f" / {account_sub_niche}"
            details = [identity]
            for label, key in (
                ("Product/service", "productService"),
                ("Objective", "objective"),
                ("Target audience", "targetAudience"),
                ("Unique selling point", "uniqueSellingPoint"),
                ("Additional context", "customContext"),
            ):
                value = persona.get(key)
                if isinstance(value, str) and value.strip():
                    details.append(f"{label}: {value.strip()[:500]}")
            account_context = "\n".join(details)
        else:
            account_context = "No operated-account persona is available."

        return (
            "We are evaluating acquisition targets for the operated account below:\n"
            f"{account_context}\n"
            "Judge MARKET FIT, not whether the candidate has the same job title and not whether "
            "the candidate personally performs the operated account's objective. The objective "
            "describes what OUR account wants to achieve; it is not a job description that every "
            "valuable target must satisfy.\n"
            "Evaluate these independent fit paths and use the strongest one supported by an "
            "observed candidate fact:\n"
            "1. core ecosystem: same field, supply chain, professional community or creator scene;\n"
            "2. target audience: the candidate is explicitly one of the people the account serves;\n"
            "3. shared customer/problem: both address the same concrete clientele, need or business problem;\n"
            "4. complementary market: the candidate offers a credible one-hop complementary service "
            "or reaches the same concrete audience;\n"
            "5. distribution/context: explicit media, event, community or geographic fit that makes "
            "the candidate a credible participant in this market.\n"
            "Use this evidence-based relevance ladder:\n"
            "- direct: a concrete candidate fact places the profile in the core ecosystem, explicit "
            "target audience, or same customer/problem market. Exact job-title equality is unnecessary.\n"
            "- adjacent: a concrete candidate fact shows a credible one-hop complementary market, "
            "shared audience, distribution channel or professional community.\n"
            "- weak: only a broad theme, vague aspiration, hypothetical collaboration, generic "
            "lifestyle/culture/creativity/business wording, or a multi-hop connection can be invented.\n"
            "- none: no credible overlap, spam, generic store/service, or unrelated fan account.\n"
            "Broad words such as culture, events, community, lifestyle, visual or creativity are NOT "
            "evidence by themselves; an observed profession, service, audience, portfolio topic, "
            "business category, bio claim or repeated content theme can be evidence. A cinema account "
            "versus a generic hair salon or football fan is weak/none, while an actor, filmmaker or "
            "cinematographer is direct and a working musician, photographer or cultural journalist can "
            "be adjacent when the operated persona targets the broader cultural ecosystem. For a "
            "business-coaching account serving beauty institutes, institute owners and estheticians are "
            "direct; a coach, marketer, trainer or wellness professional is adjacent only when a concrete "
            "shared clientele, entrepreneurial problem or complementary service is visible. Do not infer "
            "relevance merely because the candidate follows the source account or because both profiles "
            "are generically entrepreneurial or creative. "
            "For direct/adjacent, 'evidence' must cite the concrete candidate fact that overlaps; "
            "phrases such as 'could interest', 'might be useful' or 'potential collaboration' are weak. "
            "Consistency check before answering: if the extracted profession, tags or bio explicitly "
            "name a role inside the operated account's core ecosystem or target audience, do not return "
            "weak/none. If you return weak/none despite a concrete profession, verify that none of the "
            "five fit paths above is actually supported. "
        )

    def engagement_verdict_for_known_profile(
        self,
        username: str,
        cached: Dict[str, Any],
        account_niche: str = None,
        account_sub_niche: str = None,
        account_persona: Dict[str, Any] = None,
        response_language: str = 'en',
    ) -> Dict[str, Any]:
        """Engagement verdict for a profile whose AI classification is ALREADY stored — TEXT-ONLY
        (no screenshot, no vision tokens). Judges the KNOWN niche/profession/bio against the
        operated account's niche, so relevance gating also covers cached profiles (they used to
        fail-open: qualification reused, verdict never computed, gate had nothing to act on).
        The verdict is account-relative, so it is recomputed per run and never persisted.

        Returns {"success": True, "engagement": {...normalized...}} or {"success": False, ...}."""
        t0 = time.time()
        _lang_map = {'fr': 'French', 'en': 'English', 'de': 'German', 'es': 'Spanish', 'pt': 'Portuguese', 'it': 'Italian', 'nl': 'Dutch'}
        _lang_full = _lang_map.get(response_language, 'English')

        system_prompt = (
            "You judge Instagram engagement targets for an account we operate.\n"
            + self._engagement_relativity(
                account_niche, account_sub_niche, account_persona
            ) +
            "Choose the semantic tier only; deterministic code derives the permitted action "
            "candidates from it. 'score' is 0.0-1.0 relevance confidence.\n"
            f"Write 'reason' (one short sentence) in {_lang_full}.\n"
            "Respond ONLY with valid JSON using this schema (the placeholders are not a verdict):\n"
            '{"relevant": "<true for direct/adjacent, otherwise false>", '
            '"relevance_tier": "<direct|adjacent|weak|none>", '
            '"evidence": "<concrete observed fit, or null>", '
            '"score": "<number 0.0-1.0>", "reason": "<short reason>"}'
        )

        parts = [f"Profile @{username} — already-classified data:"]
        if cached.get("niche_category") or cached.get("niche"):
            parts.append(f"Niche: {cached.get('niche_category') or '?'} / {cached.get('niche') or '?'}")
        if cached.get("profession"):
            parts.append(f"Profession: {cached['profession']}")
        profession_tags = cached.get("profession_tags")
        if isinstance(profession_tags, list) and profession_tags:
            parts.append(f"Profession tags: {', '.join(str(tag) for tag in profession_tags[:8])}")
        tags = cached.get("tags")
        if isinstance(tags, list) and tags:
            parts.append(f"Content tags: {', '.join(str(tag) for tag in tags[:10])}")
        bio = (cached.get("biography") or "").strip()
        if bio:
            parts.append(f"Bio: {bio[:400]}")
        summary = (cached.get("summary") or "").strip()
        if summary:
            parts.append(f"Profile summary: {summary[:500]}")
        following_insights = (cached.get("following_insights") or "").strip()
        if following_insights:
            parts.append(f"Audience/community signals: {following_insights[:400]}")
        if cached.get("full_name"):
            parts.append(f"Full name: {cached['full_name']}")
        if cached.get("is_business"):
            parts.append("Business account: yes")
        user_prompt = "\n".join(parts)

        result = self.text_completion(system_prompt, user_prompt, temperature=0.2, max_tokens=220,
                                      label=f"engagement_verdict @{username}")
        duration_ms = int((time.time() - t0) * 1000)
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "verdict failed"), "duration_ms": duration_ms}

        raw = (result.get("text") or "").strip()
        engagement = None
        try:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end > start:
                engagement = self._normalize_engagement(json.loads(raw[start:end + 1]))
        except Exception:
            engagement = None
        if engagement is None:
            return {"success": False, "error": "unparseable verdict", "raw": raw, "duration_ms": duration_ms}
        return {
            "success": True,
            "engagement": engagement,
            "duration_ms": duration_ms,
            "model": result.get("model"),
            "cost_usd": result.get("cost_usd"),
        }

    def classify_profile_niche(self, username: str, screenshot_path: str,
                               profile_context: dict = None,
                               response_language: str = 'en',
                               include_engagement: bool = False,
                               account_niche: str = None,
                               account_sub_niche: str = None,
                               account_persona: Dict[str, Any] = None,
                               platform: str = "instagram") -> Dict[str, Any]:
        """
        Classify an Instagram profile from a screenshot into a niche (scraping mode).
        No relevance score — focus is on niche classification + profile summary.
        Emits IPC events for the AgentPanel.

        Args:
            profile_context: Optional dict with enriched profile data (bio, website,
                             business_category, linked_accounts, full_name) to augment
                             the vision classification with text hints.
            include_engagement: When True, ALSO return an `engagement` verdict
                             {relevant, follow, comment, like, score, reason} judging whether
                             engaging this profile is worthwhile (opt-in so the scraping path,
                             which reuses this call, pays no extra tokens). See
                             `internal docs`.
            account_niche / account_sub_niche / account_persona: factual context for the
                             operated account, so the verdict is judged relative to its real
                             market rather than a broad niche label alone.
        """
        t0 = time.time()

        # ── Build a human-readable context summary for the AgentPanel ────────────
        context_lines: list[str] = []
        if profile_context:
            bio = (profile_context.get('biography') or '').strip()
            if bio:
                bio_short = bio[:120] + ('…' if len(bio) > 120 else '')
                context_lines.append(f"Bio: {bio_short}")
            cat = profile_context.get('business_category') or ''
            if cat:
                context_lines.append(f"Category: {cat}")
            following_sample = profile_context.get('_following_sample') or []
            if following_sample:
                preview = ', '.join(f"@{u}" for u in following_sample[:5])
                extra = len(following_sample) - 5
                extra_str = f' +{extra} more' if extra > 0 else ''
                context_lines.append(f"Following ({len(following_sample)}): {preview}{extra_str}")
            known = profile_context.get('_known_followings') or []
            if known:
                context_lines.append(f"{len(known)} already-classified in DB")
        ipc_prompt = '\n'.join(context_lines) if context_lines else f"Classifying @{username}"

        # Avatar crop coordinates are Instagram-Android-specific; skip on other platforms.
        _plat_label = _platform_label(platform)
        if self.ipc:
            screenshot_thumb = self._image_to_thumbnail_url(screenshot_path)
            avatar_thumb = self._extract_avatar_thumbnail(screenshot_path) if platform == "instagram" else None
            self.ipc.ai_profile_analyzing(
                username,
                prompt=ipc_prompt,
                model=self.vision_model,
                image_url=screenshot_thumb,
                avatar_url=avatar_thumb,
                prompt_key="promptClassifyProfile",
            )

        niche_map = self._niche_map_text()
        _lang_map = {'fr': 'French', 'en': 'English', 'de': 'German', 'es': 'Spanish', 'pt': 'Portuguese', 'it': 'Italian', 'nl': 'Dutch'}
        _lang_full = _lang_map.get(response_language, 'English')

        # Optional engagement-relevance verdict (Lot 1 of the AI-relevance spec). Opt-in so the
        # scraping path pays no extra tokens. Judged vs the operated account's niche when known.
        engagement_instr = ""
        engagement_json = ""
        if include_engagement:
            relativity = self._engagement_relativity(
                account_niche, account_sub_niche, account_persona
            )
            engagement_instr = (
                "\nENGAGEMENT RELEVANCE: " + relativity +
                "Return an 'engagement' object consistent with the ladder: 'relevance_tier' "
                "(direct|adjacent|weak|none), 'evidence' (a concrete observed overlap, otherwise null), "
                "'relevant' (true only for direct/adjacent), 'score' (0.0-1.0), and 'reason' "
                "(one short sentence). Do not choose individual actions: deterministic code derives "
                "them from the tier, then evaluates any comment against the real post.\n"
            )
            engagement_json = (
                ', "engagement": {"relevant": "<true for direct/adjacent, otherwise false>", '
                '"relevance_tier": "<direct|adjacent|weak|none>", '
                '"evidence": "<concrete observed fit, or null>", '
                '"score": "<number 0.0-1.0>", "reason": "<short reason>"}'
            )

        system_prompt = (
            f"You are a {_plat_label} profile classifier.\n"
            "Analyze this profile screenshot and identify the account's niche.\n"
            "Choose niche_category from the keys below, then choose niche from that category's sub-niches:\n"
            + niche_map + "\n"
            "IMPORTANT: always match an existing sub-niche when possible. "
            "Only if the account genuinely doesn't fit any listed sub-niche, pick the closest niche_category "
            "and write a short descriptive sub-niche label freely (e.g. 'Associative & Non-Profit', 'Motorsport & Racing'). "
            "Do NOT invent a new sub-niche just to be more specific — use the existing one whenever reasonable.\n"
            "Extract all cities explicitly mentioned in the bio (e.g. 'Paris - Metz' → both cities). Use empty array if none.\n"
            "If the person has a clear professional trade (Actor, Director, Screenwriter, Photographer, Chef, Coach, Tattoo Artist, Musician, Model, etc.), set profession to that trade in the profile language. "
            "Set profession_tags to up to 3 subcategory tags (e.g. ['UGC', 'short film', 'coaching'] for an actor). "
            "If no clear profession is identifiable, set profession to null and profession_tags to [].\n"
            "For 'summary': write 2-3 sentences describing who this person is, their content style, typical audience, and likely purpose. Be specific and insightful — avoid generic descriptions.\n"
            "For 'following_insights': if a following sample was provided, write 1-2 sentences explaining what it reveals about this person (interests, community circles, cultural background, location signals, professional network, etc.). "
            "Be concrete: name specific patterns you observe. Set to null if no following data was provided.\n"
            f"Write the human-readable text fields — 'summary', 'following_insights' and the engagement 'reason' — in {_lang_full} (they are shown to the user in the app). "
            "All structured fields (niche_category, niche, language, content_type, tags, cities, country, profession, profession_tags, gender, age_group) must remain in English.\n"
            "For 'country': the country this account is most likely based in, as an English country name "
            "(e.g. 'France', 'Switzerland', 'United States'). Infer it from the bio, the cities, the writing "
            "language and the following sample. Only answer when the signals reasonably support one country; "
            "set null when you would just be guessing.\n"
            "For 'gender': determine if this is a 'female', 'male', 'brand' (company/organization/product page), or 'unknown' account. Base this on profile photo, name, and bio cues.\n"
            "For 'age_group': estimate the person's age range as 'teen' (<18), 'young_adult' (18-24), 'adult' (25-34), 'mature' (35+), or 'unknown'. Use 'unknown' for brands or if unclear.\n"
            + engagement_instr +
            "Respond ONLY with valid JSON — no extra text:\n"
            '{"niche_category": "travel", "niche": "Adventure & Backpacking", '
            '"summary": "2-3 sentences describing the account in detail.", '
            '"following_insights": "What the following sample reveals about this person, or null.", '
            '"language": "en", "content_type": "creator", "tags": ["tag1", "tag2"], '
            '"cities": [], "country": null, "profession": null, "profession_tags": [], '
            '"gender": "female", "age_group": "young_adult"'
            + engagement_json + '}'
        )

        # Build user prompt — include enriched text context when available
        user_prompt = f"Classify this {_plat_label} profile: @{username}"
        if profile_context:
            ctx_parts = []
            if profile_context.get('full_name'):
                ctx_parts.append(f"Full name: {profile_context['full_name']}")
            if profile_context.get('biography'):
                ctx_parts.append(f"Bio: {profile_context['biography']}")
            if profile_context.get('website'):
                ctx_parts.append(f"Website: {profile_context['website']}")
            if profile_context.get('business_category'):
                ctx_parts.append(f"Instagram category: {profile_context['business_category']}")
            if profile_context.get('linked_accounts'):
                names = [a.get('name', '') for a in profile_context['linked_accounts'] if a.get('name')]
                if names:
                    ctx_parts.append(f"Linked accounts: {', '.join(names)}")
            if ctx_parts:
                user_prompt += "\n\nAdditional profile context (use to improve classification accuracy):\n" + "\n".join(ctx_parts)

            # Deep qualify context — following sample + already-classified profiles from DB
            following_sample = profile_context.get('_following_sample') or []
            known_followings = profile_context.get('_known_followings') or []

            if following_sample:
                user_prompt += (
                    f"\n\nFollowing sample ({len(following_sample)} accounts this user follows):\n"
                    + ", ".join(f"@{u}" for u in following_sample)
                )

            if known_followings:
                lines = []
                for kf in known_followings[:20]:  # cap at 20 to keep prompt size reasonable
                    parts = [f"@{kf.get('username', '?')}"]
                    if kf.get('niche_category'):
                        parts.append(f"niche={kf['niche_category']}")
                    if kf.get('niche'):
                        parts.append(f"({kf['niche']})")
                    if kf.get('cities'):
                        parts.append(f"city={kf['cities']}")
                    if kf.get('profession'):
                        parts.append(f"profession={kf['profession']}")
                    if kf.get('tags') and isinstance(kf['tags'], list):
                        parts.append(f"tags=[{', '.join(kf['tags'][:4])}]")
                    lines.append(' '.join(parts))
                user_prompt += (
                    "\n\nAlready-classified profiles from following list "
                    "(use to infer interests, location, community):\n"
                    + "\n".join(f"  • {l}" for l in lines)
                )

        logger.debug(
            f"[AIService] classify_profile_niche @{username} — prompt sent:\n"
            f"{'─' * 60}\n{user_prompt}\n{'─' * 60}"
        )

        result = self.vision_json_completion(system_prompt, user_prompt, screenshot_path,
                                             temperature=0.2,
                                             max_tokens=1100 if include_engagement else 900,
                                             label=f"classify_profile_niche @{username}")
        duration_ms = int((time.time() - t0) * 1000)

        logger.debug(
            f"[AIService] classify_profile_niche @{username} — raw response:\n"
            f"{'─' * 60}\n{result.get('text', '(no text)')}\n{'─' * 60}"
        )

        classification = result.get("payload")
        if not result["success"] or classification is None:
            # Both attempts came back unusable. Salvage whatever fields survived a partial
            # answer before giving up — a truncated classification still often carries the
            # niche, which is most of the value.
            classification = self._extract_partial_classification(result.get("raw") or result.get("text") or "")
            if classification:
                logger.warning(
                    f"[AIService] classify_profile_niche @{username} used partial extraction "
                    f"after: {result.get('error')}"
                )
            else:
                if self.ipc:
                    self.ipc.ai_error(result.get("error", "Classification failed"), username)
                return result

        # Normalize the optional engagement verdict (defensive: coerce types, drop if unusable).
        if include_engagement:
            classification["engagement"] = self._normalize_engagement(classification.get("engagement"))

        niche = classification.get("niche", "?")
        # Clamp the model's category onto the 16 canonical buckets and write it back so the
        # emitted event AND the persisted row both carry the canonical slug (never free text).
        niche_cat = self._canonicalize_niche_category(classification.get("niche_category"))
        classification["niche_category"] = niche_cat
        # Detect proposed sub-niches (not in canonical taxonomy) for monitoring
        if niche and niche not in self._known_sub_niches and niche != "Other":
            logger.info(f"[AIService] Proposed new sub-niche '{niche}' for @{username} (cat: {niche_cat})")
        summary = classification.get("summary", "")
        result_text = f"[{niche_cat}] {niche}"
        if summary:
            result_text += f" · {summary}"

        # Inject deep-qualify context so the frontend card can display it
        following_sample = (profile_context or {}).get('_following_sample') or []
        if following_sample:
            classification['following_sample'] = following_sample

        if self.ipc:
            screenshot_b64 = self._image_to_thumbnail_url(screenshot_path, max_size=800)
            self.ipc.ai_profile_analyzed(
                username=username,
                result=result_text,
                duration_ms=duration_ms,
                model=result.get("model"),
                provider="openrouter",
                cost_usd=result.get("cost_usd"),
                classification=classification,
                screenshot=screenshot_b64,
            )

        return {
            "success": True,
            "classification": classification,
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }

    def classify_profile(self, username: str, screenshot_path: str,
                         account_username: str = None) -> Dict[str, Any]:
        """
        Classify an Instagram profile from a screenshot.
        Returns niche, score, summary etc.
        Emits IPC events for the AgentPanel.
        """
        t0 = time.time()

        # Signal start
        if self.ipc:
            prompt_text = f"Classifying @{username}" + (f" (scored for @{account_username})" if account_username else "")
            screenshot_thumb = self._image_to_thumbnail_url(screenshot_path)
            self.ipc.ai_profile_analyzing(username, prompt=prompt_text, model=self.vision_model,
                                          image_url=screenshot_thumb)

        sub_niche_list = " | ".join(self.niche_taxonomy) or "(infer a concise niche)"
        system_prompt = (
            "You are an expert Instagram profile analyst. Given a screenshot of an Instagram profile page, extract and analyze:\n"
            "1. The niche/category of the account\n"
            "2. A relevance score (0-100) indicating how relevant this profile is as a potential follower/engagement target\n"
            "3. A quality score (0-100) indicating the quality of the account\n"
            "4. Content type (creator, brand, personal, business, media, etc.)\n"
            "5. Engagement level (low, medium, high, very_high)\n"
            "6. Language of the account\n"
            "7. A brief summary (1 sentence)\n\n"
            f"Choose niche from exactly one of these predefined sub-niches: {sub_niche_list}\n\n"
            "Respond ONLY with valid JSON in this exact format:\n"
            '{\n'
            '  "niche": "Adventure & Backpacking",\n'
            '  "niche_category": "travel",\n'
            '  "score": 75,\n'
            '  "relevance_score": 80,\n'
            '  "quality_score": 70,\n'
            '  "content_type": "creator",\n'
            '  "engagement_level": "medium",\n'
            '  "language": "en",\n'
            '  "audience_type": "general",\n'
            '  "tags": ["tag1", "tag2"],\n'
            '  "summary": "Brief description"\n'
            '}'
        )

        user_prompt = f"Analyze this Instagram profile: @{username}"
        if account_username:
            user_prompt += f"\nScore relevance relative to the automation account @{account_username}."

        result = self.vision_json_completion(system_prompt, user_prompt, screenshot_path,
                                             temperature=0.2, max_tokens=500,
                                             label=f"analyze_profile_screenshot @{username}")
        duration_ms = int((time.time() - t0) * 1000)

        classification = result.get("payload")
        if not result["success"] or classification is None:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Classification failed"), username)
            return result

        # Build result summary for AgentPanel
        niche = classification.get("niche", "?")
        score = classification.get("score", 0)
        niche_cat = self._canonicalize_niche_category(classification.get("niche_category"))
        classification["niche_category"] = niche_cat
        summary = classification.get("summary", "")
        result_text = f"[{niche_cat}] {niche} — Score: {score}/100"
        if summary:
            result_text += f" · {summary}"

        if self.ipc:
            screenshot_b64 = self._image_to_thumbnail_url(screenshot_path, max_size=800)
            self.ipc.ai_profile_analyzed(
                username=username, result=result_text, duration_ms=duration_ms,
                model=result.get("model"), provider="openrouter",
                cost_usd=result.get("cost_usd"),
                classification=classification,
                screenshot=screenshot_b64,
            )

        return {
            "success": True,
            "classification": classification,
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }

    def analyze_post(self, screenshot_path: str, username: str = None, response_language: str = 'en',
                     post_caption: str = '') -> Dict[str, Any]:
        """
        Analyze a post screenshot to understand its content.
        Returns a text description of the post.
        `response_language` is the APP language: the human-readable DESCRIPTION is written in it so
        the desktop panel shows it in the user's language. The "Post language:" line stays in English
        (a stable token) so the comment-language logic can parse the post's ACTUAL language.
        Emits IPC events for the AgentPanel.
        """
        t0 = time.time()

        if self.ipc:
            screenshot_thumb = self._image_to_thumbnail_url(screenshot_path)
            self.ipc.ai_screenshot_analyzing(username, prompt="Analyzing post content", model=self.vision_model,
                                             image_url=screenshot_thumb, prompt_key="promptAnalyzePost")

        _lang_full = {'fr': 'French', 'en': 'English', 'de': 'German', 'es': 'Spanish',
                      'pt': 'Portuguese', 'it': 'Italian', 'nl': 'Dutch'}.get(response_language, 'English')
        system_prompt = f"""You are an expert at analyzing Instagram posts. Describe the post concisely (2-4 sentences) in {_lang_full}.
Identify: main subject, visual style, mood, any visible text (quote it exactly).
At the end, on a new line, write in ENGLISH: "Post language: <language>" — the ACTUAL language the post is written in (e.g. "Post language: French"), regardless of the description language above. Determine it from the author's CAPTION when one is provided (it is the most reliable signal — an image can carry English design text while the post is French); otherwise from the visible text.
No markdown formatting."""

        caption_block = ''
        if post_caption and post_caption.strip():
            # The author's own words are the most reliable language signal (the screenshot's overlay
            # text is often stylised/English while the post is another language). Feed it to the model.
            caption_block = f"\n\nAuthor's caption (authoritative for the post language):\n{post_caption.strip()[:600]}"
        user_prompt = f"Describe this Instagram post. Be concise and precise.{caption_block}"

        result = self.vision_completion(system_prompt, user_prompt, screenshot_path,
                                        temperature=0.2, max_tokens=300,
                                        label=f"analyze_post @{username or '?'}")
        duration_ms = int((time.time() - t0) * 1000)

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Post analysis failed"), username)
            return result

        description = result["text"]

        # The model appends a "Post language: <language>" trailer (always written in English) so the
        # comment-language policy can read the POST's real language without it leaking into what the
        # operator sees. Split it out: the displayed description stays in the app language; the
        # detected language is returned as a separate, normalized field (lowercase English name).
        import re
        post_language = None
        kept_lines = []
        for line in description.splitlines():
            match = re.match(r'\s*post\s+language\s*:\s*(.+?)\s*$', line, re.IGNORECASE)
            if match:
                post_language = match.group(1).strip().rstrip('.').strip().lower() or None
            else:
                kept_lines.append(line)
        description = "\n".join(kept_lines).strip()

        if self.ipc:
            screenshot_b64 = self._image_to_thumbnail_url(screenshot_path, max_size=600)
            self.ipc.ai_screenshot_analyzed(
                result=description[:200], username=username, duration_ms=duration_ms,
                model=result.get("model"), provider="openrouter",
                cost_usd=result.get("cost_usd"),
                screenshot=screenshot_b64,
            )

        return {
            "success": True,
            "description": description,
            "post_language": post_language,
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }

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
