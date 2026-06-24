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
from typing import Optional, Dict, Any
from loguru import logger

# Default models
DEFAULT_TEXT_MODEL = "google/gemini-2.5-flash-lite"
DEFAULT_VISION_MODEL = "google/gemini-2.5-flash"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Platform display label for prompts (so the provider is reusable across platforms,
# not hardcoded to Instagram). Defaults keep the Instagram wording byte-equivalent.
_PLATFORM_LABELS = {"instagram": "Instagram", "tiktok": "TikTok"}


def _platform_label(platform: str) -> str:
    return _PLATFORM_LABELS.get((platform or "instagram").lower(), (platform or "Instagram").title())


class AIService:
    """Lightweight OpenRouter client for Bot AI operations."""

    def __init__(self, api_key: str, ipc=None, text_model: str = None, vision_model: str = None,
                 niche_taxonomy: Dict[str, list] = None):
        self.api_key = api_key
        self.ipc = ipc
        self.text_model = text_model or DEFAULT_TEXT_MODEL
        self.vision_model = vision_model or DEFAULT_VISION_MODEL
        # Premium niche taxonomy injected by the desktop app via the bridge config
        # (slug -> [sub-niche labels]). The open-source bot does NOT own this list;
        # when nothing is injected, profile classification stays free-form so the
        # standalone bot keeps working without the premium taxonomy.
        self.niche_taxonomy: Dict[str, list] = niche_taxonomy or {}

    # ------------------------------------------------------------------
    # Low-level API call
    # ------------------------------------------------------------------

    def _call_openrouter(self, model: str, messages: list, temperature: float = 0.7,
                         max_tokens: int = 2000) -> Dict[str, Any]:
        """Call OpenRouter chat completions API. Returns dict with success, text, usage, cost."""
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

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choice = data.get("choices", [{}])[0]
                text = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {})
                # OpenRouter returns cost in usage.cost (not usage.total_cost)
                cost = usage.get("cost") or usage.get("total_cost")
                return {
                    "success": True,
                    "text": text.strip(),
                    "model": data.get("model", model),
                    "provider": "openrouter",
                    "usage": usage,
                    "cost_usd": cost,
                }
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            logger.error(f"[AIService] OpenRouter HTTP {e.code}: {error_body[:300]}")
            return {"success": False, "error": f"HTTP {e.code}: {error_body[:200]}"}
        except Exception as e:
            logger.error(f"[AIService] OpenRouter error: {e}")
            return {"success": False, "error": str(e)}

    def _image_to_base64_url(self, image_path: str) -> Optional[str]:
        """Convert an image file to a data URL for vision models."""
        if not os.path.isfile(image_path):
            return None
        ext = os.path.splitext(image_path)[1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext.lstrip("."), "image/png")
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"

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
                        temperature: float = 0.7, max_tokens: int = 2000) -> Dict[str, Any]:
        """Simple text completion via the text model."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self._call_openrouter(self.text_model, messages, temperature, max_tokens)

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

        for i in range(0, len(clean), batch_size):
            batch = clean[i:i + batch_size]
            user_prompt = "Classify these Instagram usernames:\n" + "\n".join(f"- {u}" for u in batch)
            try:
                result = self.text_completion(system_prompt, user_prompt, temperature=0.1, max_tokens=1200)
                if not result.get("success"):
                    logger.warning(f"[AIService] classify_following_usernames_batch failed: {result.get('error')}")
                    continue
                text = result["text"].strip()
                # Strip markdown fences if present
                if "```" in text:
                    parts = text.split("```")
                    text = parts[1] if len(parts) > 1 else text
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                batch_result = json.loads(text)
                known_sub_niches = self._known_sub_niches
                for username, data in batch_result.items():
                    if isinstance(data, dict):
                        niche_val = str(data.get("niche") or "Other")
                        if niche_val not in known_sub_niches and niche_val != "Other":
                            logger.info(f"[AIService] Proposed new sub-niche '{niche_val}' for @{username}")
                        results[username] = {
                            "niche_category": str(data.get("niche_category") or "other"),
                            "niche": niche_val,
                            "gender": str(data.get("gender") or "unknown"),
                        }
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"[AIService] classify_following_usernames_batch batch error: {e}")
                continue

        return results

    # ------------------------------------------------------------------
    # Vision completion
    # ------------------------------------------------------------------

    def vision_completion(self, system_prompt: str, user_prompt: str, image_path: str,
                          temperature: float = 0.3, max_tokens: int = 1500) -> Dict[str, Any]:
        """Vision completion — sends an image + prompt to the vision model."""
        image_url = self._image_to_base64_url(image_path)
        if not image_url:
            return {"success": False, "error": f"Image not found: {image_path}"}

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image_url}},
                {"type": "text", "text": user_prompt},
            ]},
        ]
        return self._call_openrouter(self.vision_model, messages, temperature, max_tokens)

    def _extract_partial_classification(self, text: str) -> Optional[Dict[str, Any]]:
        """Fallback parser: extract key fields from a truncated/malformed JSON string."""
        import re
        result: Dict[str, Any] = {}

        for field in ("niche_category", "niche", "summary", "language", "content_type"):
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

        Returns None when the block is missing/garbage so callers cleanly fall back to the
        non-AI behaviour. `relevant` defaults to the OR of follow/comment/like; a missing
        sub-flag is False; score is clamped to [0,1]."""
        if not isinstance(raw, dict):
            return None

        def _b(v) -> bool:
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() in ("true", "yes", "1")
            return bool(v) if isinstance(v, (int, float)) else False

        follow = _b(raw.get("follow"))
        comment = _b(raw.get("comment"))
        like = _b(raw.get("like"))
        relevant = raw.get("relevant")
        relevant = _b(relevant) if relevant is not None else (follow or comment or like)

        score = raw.get("score")
        try:
            score = max(0.0, min(1.0, float(score)))
        except (TypeError, ValueError):
            score = None

        reason = raw.get("reason")
        reason = reason.strip()[:200] if isinstance(reason, str) else None

        return {
            "relevant": relevant,
            "follow": follow,
            "comment": comment,
            "like": like,
            "score": score,
            "reason": reason,
        }

    def classify_profile_niche(self, username: str, screenshot_path: str,
                               profile_context: dict = None,
                               response_language: str = 'en',
                               include_engagement: bool = False,
                               account_niche: str = None,
                               account_sub_niche: str = None,
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
            account_niche / account_sub_niche: the niche of the account being automated, so the
                             engagement verdict is judged RELATIVE to it (adjacency-aware). When
                             absent the verdict falls back to a generic "is this a good engagement
                             target" judgement.
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
            )

        niche_map = self._niche_map_text()
        _lang_map = {'fr': 'French', 'en': 'English', 'de': 'German', 'es': 'Spanish', 'pt': 'Portuguese', 'it': 'Italian', 'nl': 'Dutch'}
        _lang_full = _lang_map.get(response_language, 'English')

        # Optional engagement-relevance verdict (Lot 1 of the AI-relevance spec). Opt-in so the
        # scraping path pays no extra tokens. Judged vs the operated account's niche when known.
        engagement_instr = ""
        engagement_json = ""
        if include_engagement:
            if account_niche:
                who = f"a '{account_niche}'" + (f" / '{account_sub_niche}'" if account_sub_niche else "") + " account"
                relativity = (
                    f"We are GROWING {who}. Judge whether engaging THIS profile is worthwhile for that "
                    "account: consider niche ADJACENCY (e.g. fitness ↔ bodybuilding ↔ nutrition are adjacent), "
                    "audience overlap, and whether it's a real, active, human-ish account (not a spam/store/bot). "
                )
            else:
                relativity = (
                    "Judge whether THIS profile is a worthwhile engagement target in general: a real, active, "
                    "niche-coherent, human-ish account (not a spam/store/bot). "
                )
            engagement_instr = (
                "\nENGAGEMENT RELEVANCE: " + relativity +
                "Be SELECTIVE — not every profile deserves a follow or a comment. Return an 'engagement' object: "
                "'relevant' (bool), 'follow' (bool: worth following), 'comment' (bool: worth a comment — STRICTER "
                "than follow), 'like' (bool: worth liking its posts), 'score' (0.0-1.0 relevance confidence), "
                "'reason' (one short sentence).\n"
            )
            engagement_json = (
                ', "engagement": {"relevant": true, "follow": true, "comment": false, '
                '"like": true, "score": 0.8, "reason": "short reason"}'
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
            f"Write the 'summary' and 'following_insights' text fields in {_lang_full}. "
            "All structured fields (niche_category, niche, language, content_type, tags, cities, profession, profession_tags, gender, age_group) must remain in English.\n"
            "For 'gender': determine if this is a 'female', 'male', 'brand' (company/organization/product page), or 'unknown' account. Base this on profile photo, name, and bio cues.\n"
            "For 'age_group': estimate the person's age range as 'teen' (<18), 'young_adult' (18-24), 'adult' (25-34), 'mature' (35+), or 'unknown'. Use 'unknown' for brands or if unclear.\n"
            + engagement_instr +
            "Respond ONLY with valid JSON — no extra text:\n"
            '{"niche_category": "travel", "niche": "Adventure & Backpacking", '
            '"summary": "2-3 sentences describing the account in detail.", '
            '"following_insights": "What the following sample reveals about this person, or null.", '
            '"language": "en", "content_type": "creator", "tags": ["tag1", "tag2"], '
            '"cities": [], "profession": null, "profession_tags": [], '
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

        result = self.vision_completion(system_prompt, user_prompt, screenshot_path,
                                        temperature=0.2, max_tokens=1100 if include_engagement else 900)
        duration_ms = int((time.time() - t0) * 1000)

        logger.debug(
            f"[AIService] classify_profile_niche @{username} — raw response:\n"
            f"{'─' * 60}\n{result.get('text', '(no text)')}\n{'─' * 60}"
        )

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Classification failed"), username)
            return result

        try:
            text = result["text"]
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            classification = json.loads(text)
        except (json.JSONDecodeError, IndexError) as e:
            # Fallback: extract key fields via regex when JSON is truncated mid-string
            classification = self._extract_partial_classification(result["text"])
            if classification:
                logger.warning(f"[AIService] classify_profile_niche used partial extraction after: {e}")
            else:
                logger.warning(f"[AIService] classify_profile_niche parse error: {e}")
                if self.ipc:
                    self.ipc.ai_error(f"JSON parse error: {e}", username)
                return {"success": False, "error": f"JSON parse error: {e}", "raw": result["text"]}

        # Normalize the optional engagement verdict (defensive: coerce types, drop if unusable).
        if include_engagement:
            classification["engagement"] = self._normalize_engagement(classification.get("engagement"))

        niche = classification.get("niche", "?")
        niche_cat = classification.get("niche_category", "other")
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

        result = self.vision_completion(system_prompt, user_prompt, screenshot_path,
                                        temperature=0.2, max_tokens=500)
        duration_ms = int((time.time() - t0) * 1000)

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Classification failed"), username)
            return result

        # Parse JSON from response
        try:
            text = result["text"]
            # Strip markdown code fences if present
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            classification = json.loads(text)
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"[AIService] Failed to parse classification JSON: {e}")
            if self.ipc:
                self.ipc.ai_error(f"JSON parse error: {e}", username)
            return {"success": False, "error": f"JSON parse error: {e}", "raw": result["text"]}

        # Build result summary for AgentPanel
        niche = classification.get("niche", "?")
        score = classification.get("score", 0)
        niche_cat = classification.get("niche_category", "")
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

    def analyze_post(self, screenshot_path: str, username: str = None) -> Dict[str, Any]:
        """
        Analyze a post screenshot to understand its content.
        Returns a text description of the post.
        Emits IPC events for the AgentPanel.
        """
        t0 = time.time()

        if self.ipc:
            screenshot_thumb = self._image_to_thumbnail_url(screenshot_path)
            self.ipc.ai_screenshot_analyzing(username, prompt="Analyzing post content", model=self.vision_model,
                                             image_url=screenshot_thumb)

        system_prompt = """You are an expert at analyzing Instagram posts. Describe the post concisely (2-4 sentences).
Identify: main subject, visual style, mood, any visible text (quote it exactly).
At the end, on a new line, write: "Post language: <language>" based on the text and context visible.
No markdown formatting."""

        user_prompt = "Describe this Instagram post. Be concise and precise."

        result = self.vision_completion(system_prompt, user_prompt, screenshot_path,
                                        temperature=0.2, max_tokens=300)
        duration_ms = int((time.time() - t0) * 1000)

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Post analysis failed"), username)
            return result

        description = result["text"]

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
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }

    def generate_smart_comment(self, post_description: str, username: str,
                                niche: str = "general", language: str = "auto",
                                post_caption: str = "", account_persona: dict = None,
                                platform: str = "instagram") -> Dict[str, Any]:
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

        if self.ipc:
            self.ipc.ai_comment_generating(username, prompt=f"Smart comment for @{username} ({niche})",
                                           model=self.text_model)

        system_prompt = f"""You are a {_platform_label(platform)} engagement expert for the "{niche}" niche.
Generate an authentic, short (1-2 sentences max), natural comment that matches the post content.
{brand_block}Rules:
- No hashtags
- Maximum 1-2 emojis (optional)
- Sound genuinely interested, not generic
- Match the energy/tone of the post
- If the author's caption is provided, react to what THEY said (their announcement, question or joke), not only the visual
- {"Write in the same language as the post" if language == "auto" else f"Write in {language}"}
Reply ONLY with the comment text, nothing else."""

        parts = []
        if post_description:
            parts.append(f'What the post shows (vision analysis): "{post_description}"')
        if post_caption:
            parts.append(f'The author\'s caption: "{post_caption[:1000]}"')
        user_prompt = "\n\n".join(parts) + "\n\nGenerate a natural, engaging comment."

        result = self.text_completion(system_prompt, user_prompt, temperature=0.9, max_tokens=100)
        duration_ms = int((time.time() - t0) * 1000)

        if not result["success"]:
            if self.ipc:
                self.ipc.ai_error(result.get("error", "Comment generation failed"), username)
            return result

        comment = result["text"].strip().strip('"').strip("'")

        if self.ipc:
            self.ipc.ai_comment_ready(
                username=username, comment=comment, duration_ms=duration_ms,
                model=result.get("model"), provider="openrouter",
                cost_usd=result.get("cost_usd"),
            )

        return {
            "success": True,
            "comment": comment,
            "model": result.get("model"),
            "provider": "openrouter",
            "cost_usd": result.get("cost_usd"),
            "duration_ms": duration_ms,
        }
