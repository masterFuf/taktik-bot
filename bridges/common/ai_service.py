"""
AI Service for bridge scripts — calls OpenRouter API directly from the Python process.

This avoids round-tripping through Electron IPC for AI operations during automation.
The bridge receives the OpenRouter API key via the session config (ai.openrouterApiKey)
and calls the API directly.

Usage:
    from bridges.common.ai_service import AIService

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
DEFAULT_TEXT_MODEL = "anthropic/claude-3.5-haiku"
DEFAULT_VISION_MODEL = "google/gemini-2.5-flash"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class AIService:
    """Lightweight OpenRouter client for bridge AI operations."""

    def __init__(self, api_key: str, ipc=None, text_model: str = None, vision_model: str = None):
        self.api_key = api_key
        self.ipc = ipc
        self.text_model = text_model or DEFAULT_TEXT_MODEL
        self.vision_model = vision_model or DEFAULT_VISION_MODEL

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

    # ------------------------------------------------------------------
    # High-level AI operations
    # ------------------------------------------------------------------

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

        system_prompt = """You are an expert Instagram profile analyst. Given a screenshot of an Instagram profile page, extract and analyze:
1. The niche/category of the account
2. A relevance score (0-100) indicating how relevant this profile is as a potential follower/engagement target
3. A quality score (0-100) indicating the quality of the account
4. Content type (creator, brand, personal, business, media, etc.)
5. Engagement level (low, medium, high, very_high)
6. Language of the account
7. A brief summary (1 sentence)

Respond ONLY with valid JSON in this exact format:
{
  "niche": "main niche",
  "sub_niche": "sub-niche or null",
  "niche_category": "standardized category",
  "score": 75,
  "relevance_score": 80,
  "quality_score": 70,
  "content_type": "creator",
  "engagement_level": "medium",
  "language": "en",
  "audience_type": "general",
  "tags": ["tag1", "tag2"],
  "summary": "Brief description"
}"""

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
            self.ipc.ai_profile_analyzed(
                username=username, result=result_text, duration_ms=duration_ms,
                model=result.get("model"), provider="openrouter",
                cost_usd=result.get("cost_usd"),
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
            self.ipc.ai_screenshot_analyzed(
                result=description[:200], username=username, duration_ms=duration_ms,
                model=result.get("model"), provider="openrouter",
                cost_usd=result.get("cost_usd"),
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
                                niche: str = "general", language: str = "auto") -> Dict[str, Any]:
        """
        Generate a contextual smart comment based on post analysis.
        Emits IPC events for the AgentPanel.
        """
        t0 = time.time()

        if self.ipc:
            self.ipc.ai_comment_generating(username, prompt=f"Smart comment for @{username} ({niche})",
                                           model=self.text_model)

        system_prompt = f"""You are an Instagram engagement expert for the "{niche}" niche.
Generate an authentic, short (1-2 sentences max), natural comment that matches the post content.
Rules:
- No hashtags
- Maximum 1-2 emojis (optional)
- Sound genuinely interested, not generic
- Match the energy/tone of the post
- {"Write in the same language as the post" if language == "auto" else f"Write in {language}"}
Reply ONLY with the comment text, nothing else."""

        user_prompt = f"Post content: \"{post_description}\"\n\nGenerate a natural, engaging comment."

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
