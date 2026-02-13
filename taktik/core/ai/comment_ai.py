"""
AI-powered intelligent comment module for TAKTIK.

This is a CONTEXT-AWARE module that adapts to any situation automatically.
It does NOT use hardcoded language, tone, or strategy — the LLM deduces
everything from the UserProfile + post context + comment content.

Core principles:
- UserProfile is the source of truth for WHO we are and WHAT we want
- Language is auto-detected per comment and replied in the SAME language
- Strategy is deduced from context, not configured manually
- Works for any niche, any platform, any use case

Uses fal.ai for:
- Vision analysis (fal-ai/llava-next) to understand post images
- LLM (fal-ai/any-llm) to qualify comments and generate contextual replies
"""

import os
import json
import base64
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from loguru import logger

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    try:
        import requests as _requests
        HAS_REQUESTS = True
    except ImportError:
        HAS_REQUESTS = False


FAL_API_BASE = "https://queue.fal.run"
FAL_VISION_MODEL = "fal-ai/llava-next"
FAL_LLM_MODEL = "fal-ai/any-llm/router"


# =============================================================================
# USER PROFILE — The core identity that drives all AI decisions
# =============================================================================

@dataclass
class UserProfile:
    """
    Represents the bot operator's identity and goals.
    This is configured ONCE and used across ALL AI features (comments, DMs, etc).
    Stored persistently in Electron config.
    """
    # Identity
    username: str = ""
    bio: str = ""
    niche: str = ""
    platform: str = "instagram"

    # Goals & context
    objective: str = ""          # What the user wants to achieve (e.g. "gain clients for my social media agency")
    services: str = ""           # What the user offers (e.g. "organic growth strategies, content creation")
    target_audience: str = ""    # Who the user targets (e.g. "small businesses wanting social media visibility")
    
    # Personality & tone (free text, LLM interprets it)
    personality: str = ""        # e.g. "friendly expert who gives genuine advice"
    
    # Extra context the user wants the AI to know
    custom_context: str = ""     # Free-form additional info

    def to_prompt_block(self) -> str:
        """Convert profile to a prompt block for the LLM."""
        parts = []
        if self.username:
            parts.append(f"Username: @{self.username}")
        if self.bio:
            parts.append(f"Bio: {self.bio}")
        if self.niche:
            parts.append(f"Niche: {self.niche}")
        if self.platform:
            parts.append(f"Platform: {self.platform}")
        if self.objective:
            parts.append(f"Objective: {self.objective}")
        if self.services:
            parts.append(f"Services/Products: {self.services}")
        if self.target_audience:
            parts.append(f"Target audience: {self.target_audience}")
        if self.personality:
            parts.append(f"Personality/Tone: {self.personality}")
        if self.custom_context:
            parts.append(f"Additional context: {self.custom_context}")
        return "\n".join(parts) if parts else "No profile configured."

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """Create from dict, ignoring unknown keys."""
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in known})


# =============================================================================
# FAL.AI REQUEST HELPER
# =============================================================================

def _fal_request(endpoint: str, api_key: str, payload: dict, timeout: int = 60) -> dict:
    """Make a synchronous request to fal.ai API."""
    url = f"{FAL_API_BASE}/{endpoint}"
    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json"
    }

    if HAS_HTTPX:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
    elif HAS_REQUESTS:
        import requests
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    else:
        raise RuntimeError("Neither httpx nor requests is installed. Install one: pip install httpx")


def _call_llm(api_key: str, prompt: str, max_tokens: int = 2000) -> str:
    """Call LLM and return raw text response."""
    payload = {
        "model": "claude-3-5-sonnet-latest",
        "prompt": prompt,
        "system_prompt": "You are a JSON-only assistant. You ALWAYS respond with valid JSON and nothing else. No markdown, no explanation, just JSON.",
        "max_tokens": max_tokens
    }
    result = _fal_request(FAL_LLM_MODEL, api_key, payload, timeout=45)
    return result.get("output", "") or result.get("text", "") or ""


def _parse_json_array(text: str) -> List[Dict]:
    """Extract and parse a JSON array from LLM response text."""
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return json.loads(match.group())
    return []


# =============================================================================
# VISION ANALYSIS
# =============================================================================

def analyze_post_image(api_key: str, image_path: str) -> str:
    """
    Analyze a post screenshot using fal.ai vision model.
    Returns a text description of the image content.
    """
    logger.info(f"Analyzing post image: {image_path}")

    with open(image_path, "rb") as f:
        image_data = f.read()
    b64 = base64.b64encode(image_data).decode('utf-8')
    data_url = f"data:image/png;base64,{b64}"

    payload = {
        "image_url": data_url,
        "prompt": (
            "Describe this Instagram post image in detail. "
            "What is the main subject? What is the visual style? "
            "What product, service, or message is being promoted? "
            "What emotions or reactions might it provoke? "
            "Be concise but thorough (2-3 sentences)."
        )
    }

    try:
        result = _fal_request(FAL_VISION_MODEL, api_key, payload, timeout=30)
        description = result.get("output", "") or result.get("text", "") or str(result)
        logger.info(f"Image analysis: {description[:100]}...")
        return description
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return ""


# =============================================================================
# INTELLIGENT COMMENT QUALIFICATION
# =============================================================================

def qualify_comments(
    api_key: str,
    comments: List[Dict[str, Any]],
    post_context: Dict[str, Any],
    user_profile: Optional[UserProfile] = None,
    custom_criteria: str = ""
) -> List[Dict[str, Any]]:
    """
    Intelligently qualify comments to identify relevant prospects.
    
    The LLM uses the UserProfile to understand WHO we are and WHAT we want,
    then autonomously decides which comments are relevant prospects.
    No hardcoded criteria — the AI deduces from context.
    
    Args:
        api_key: fal.ai API key
        comments: Scraped comments
        post_context: Post context (author, caption, image_description, etc.)
        user_profile: The bot operator's profile (identity, goals, niche)
        custom_criteria: Optional extra criteria hint (not required)
    """
    logger.info(f"Qualifying {len(comments)} comments...")

    # Filter out author comments and emoji-only comments
    candidates = []
    for c in comments:
        if c.get('is_author', False):
            continue
        content = c.get('content', '').strip()
        text_only = re.sub(r'[\U0001F600-\U0001F9FF\U00002702-\U000027B0\U0000FE00-\U0000FE0F\U0001F1E0-\U0001F1FF\s]', '', content)
        if len(text_only) < 3:
            continue
        candidates.append(c)

    if not candidates:
        logger.warning("No candidate comments to qualify")
        return comments

    profile_block = user_profile.to_prompt_block() if user_profile else "No profile configured."

    batch_size = 30
    qualified_usernames = set()

    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start:batch_start + batch_size]

        comments_text = "\n".join([
            f"[{i+1}] @{c['username']}: {c['content'][:200]}"
            for i, c in enumerate(batch)
        ])

        prompt = (
            f"You are an intelligent social media marketing analyst.\n\n"
            f"YOUR CLIENT (the person operating the bot):\n{profile_block}\n\n"
            f"POST BEING ANALYZED:\n"
            f"- Author: @{post_context.get('author_username', 'unknown')}\n"
            f"- Author bio: {post_context.get('target_bio', 'N/A')[:200]}\n"
            f"- Caption: {post_context.get('caption', 'N/A')[:300]}\n"
            f"- Image: {post_context.get('image_description', 'N/A')[:200]}\n\n"
        )

        if custom_criteria:
            prompt += f"ADDITIONAL CRITERIA FROM CLIENT:\n{custom_criteria}\n\n"

        prompt += (
            f"COMMENTS TO ANALYZE:\n{comments_text}\n\n"
            f"TASK: Based on your understanding of the client's profile, goals, and target audience, "
            f"identify which commenters could be relevant prospects or worth engaging with. "
            f"Consider: Does this person seem like they could benefit from the client's services? "
            f"Are they asking questions, expressing needs, showing interest, or expressing dissatisfaction "
            f"that the client could address? Are they part of the target audience?\n\n"
            f"EXCLUDE: emoji-only comments, friend tags, the post author's own replies, "
            f"generic praise with no engagement opportunity.\n\n"
            f"Respond ONLY with a JSON array of qualified comments:\n"
            f'[{{"index": 1, "qualified": true, "reason": "brief reason", "lang": "detected language code (fr/en/es/...)"}}]\n'
            f"Only include qualified=true entries. Include the detected language of each comment."
        )

        try:
            response_text = _call_llm(api_key, prompt)
            qualified_list = _parse_json_array(response_text)

            for item in qualified_list:
                idx = item.get('index', 0) - 1
                if 0 <= idx < len(batch) and item.get('qualified', False):
                    batch[idx]['is_qualified'] = True
                    batch[idx]['qualification_reason'] = item.get('reason', '')
                    batch[idx]['detected_lang'] = item.get('lang', '')
                    qualified_usernames.add(batch[idx]['username'])

            q_count = len([i for i in qualified_list if i.get('qualified')])
            logger.info(f"Batch {batch_start//batch_size + 1}: {q_count} qualified")
        except Exception as e:
            logger.error(f"Qualification batch failed: {e}")
            continue

    # Update original comments list
    for c in comments:
        if c['username'] in qualified_usernames:
            for cand in candidates:
                if cand['username'] == c['username'] and cand.get('is_qualified'):
                    c['is_qualified'] = True
                    c['qualification_reason'] = cand.get('qualification_reason', '')
                    c['detected_lang'] = cand.get('detected_lang', '')
                    break

    qualified_count = len([c for c in comments if c.get('is_qualified')])
    logger.info(f"Total qualified: {qualified_count}/{len(comments)}")
    return comments


# =============================================================================
# INTELLIGENT REPLY GENERATION
# =============================================================================

def generate_replies(
    api_key: str,
    qualified_comments: List[Dict[str, Any]],
    post_context: Dict[str, Any],
    user_profile: Optional[UserProfile] = None,
    custom_instructions: str = ""
) -> List[Dict[str, Any]]:
    """
    Generate intelligent, contextual replies for qualified comments.
    
    Key behaviors:
    - Each reply is in the SAME LANGUAGE as the original comment (auto-detected)
    - The tone and strategy are deduced from the UserProfile
    - Replies are natural, varied, and don't look like spam
    - No hardcoded templates — the LLM adapts to each situation
    
    Args:
        api_key: fal.ai API key
        qualified_comments: Comments that passed qualification
        post_context: Post context
        user_profile: The bot operator's profile
        custom_instructions: Optional extra instructions (not required)
    """
    logger.info(f"Generating replies for {len(qualified_comments)} comments...")

    if not qualified_comments:
        return qualified_comments

    profile_block = user_profile.to_prompt_block() if user_profile else "No profile configured."

    batch_size = 10

    for batch_start in range(0, len(qualified_comments), batch_size):
        batch = qualified_comments[batch_start:batch_start + batch_size]

        comments_text = "\n".join([
            f"[{i+1}] @{c['username']} (lang:{c.get('detected_lang', '?')}): {c['content'][:200]} "
            f"[reason: {c.get('qualification_reason', 'N/A')}]"
            for i, c in enumerate(batch)
        ])

        prompt = (
            f"You are acting as an authentic social media user. You must reply to comments "
            f"on a post in a way that is natural, helpful, and strategically aligned with your goals.\n\n"
            f"YOUR IDENTITY & GOALS:\n{profile_block}\n\n"
            f"POST CONTEXT:\n"
            f"- Author: @{post_context.get('author_username', 'unknown')}\n"
            f"- Author bio: {post_context.get('target_bio', 'N/A')[:200]}\n"
            f"- Caption: {post_context.get('caption', 'N/A')[:300]}\n"
            f"- Image: {post_context.get('image_description', 'N/A')[:200]}\n\n"
        )

        if custom_instructions:
            prompt += f"ADDITIONAL INSTRUCTIONS:\n{custom_instructions}\n\n"

        prompt += (
            f"COMMENTS TO REPLY TO:\n{comments_text}\n\n"
            f"RULES:\n"
            f"- CRITICAL: Reply in the SAME LANGUAGE as each comment. If the comment is in French, reply in French. If in English, reply in English. If in Spanish, reply in Spanish. Etc.\n"
            f"- Be natural and authentic — you are a real person, not a bot\n"
            f"- Each reply must be UNIQUE and DIFFERENT from the others\n"
            f"- Keep replies short (1-2 sentences, 50-150 characters)\n"
            f"- Use 0-1 emoji maximum per reply\n"
            f"- NEVER directly promote, drop links, or mention brand names\n"
            f"- Add value: answer questions, share insight, empathize with concerns\n"
            f"- Subtly position yourself as someone knowledgeable in the field\n"
            f"- Adapt your tone to match the conversation naturally\n\n"
            f"Respond ONLY with a JSON array:\n"
            f'[{{"index": 1, "reply": "your reply here", "lang": "language code used"}}]'
        )

        try:
            response_text = _call_llm(api_key, prompt)
            replies_list = _parse_json_array(response_text)

            for item in replies_list:
                idx = item.get('index', 0) - 1
                if 0 <= idx < len(batch):
                    reply = item.get('reply', '').strip()
                    if reply:
                        batch[idx]['generated_reply'] = reply

            generated = len([i for i in replies_list if i.get('reply')])
            logger.info(f"Batch {batch_start//batch_size + 1}: {generated} replies generated")
        except Exception as e:
            logger.error(f"Reply generation batch failed: {e}")
            continue

    generated_count = len([c for c in qualified_comments if c.get('generated_reply')])
    logger.info(f"Total replies generated: {generated_count}/{len(qualified_comments)}")
    return qualified_comments
