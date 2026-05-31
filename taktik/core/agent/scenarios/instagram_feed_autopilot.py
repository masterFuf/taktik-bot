"""Taktik Agent — autonomous social media workflow (Instagram-first).

Platform-agnostic orchestration layer: inject the right `device_manager`
and the appropriate platform actions, and it works on Instagram, TikTok, etc.

Current implementation: Instagram feed browsing.
  1. Visits own profile → loads account context (niche, persona) from SQLite
  2. Navigates to the home feed
  3. Scrolls through posts, stopping on ~40% of them
  4. For each stopped post: takes a screenshot → AI decides (like / skip / comment / save)
  5. If AI says visit_profile: navigate to author → screenshot → AI decides (follow / skip)
  6. Respects configurable daily quotas; stops when any quota is reached
  7. Emits IPC events throughout for the Taktik Agent panel
"""

import os
import time
import random
import tempfile
from typing import Dict, Any, Optional
from loguru import logger

from taktik.core.database import get_db_service
from taktik.core.ai.comment_ai import UserProfile
from taktik.core.agent.decision.agent_ai import AgentAI
from taktik.core.agent.io.manifest import load_workflow_manifest
from taktik.core.agent.io.plan import agent_plan_from_payload
from taktik.core.agent.kernel.context import AgentContext
from taktik.core.agent.kernel.contracts import AgentAIService, AgentAIServiceFactory, AgentPlan


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# How often the agent checks for stop signal (seconds)
POLL_INTERVAL = 0.5

# Probability (0-100) of stopping on any given post
POST_STOP_RATE = 80

# After this many consecutive AI-analyzed SKIPs, switch to hashtag exploration
CONSECUTIVE_SKIP_THRESHOLD = 7

# Number of hashtag posts to analyze per burst before returning to feed
HASHTAG_POSTS_PER_BURST = 5

# Delays between actions (seconds)
DELAY_AFTER_LIKE = (1.5, 3.5)
DELAY_AFTER_COMMENT = (3.0, 6.0)
DELAY_AFTER_FOLLOW = (2.0, 4.0)
DELAY_SCROLL_TO_NEXT = (1.0, 2.5)
DELAY_AFTER_PROFILE_VISIT = (3.0, 6.0)


class TaktikAgentWorkflow:
    """Autonomous Instagram agent that behaves like a human user."""

    def __init__(
        self,
        device_manager,
        config: Dict[str, Any],
        ipc=None,
        ai_service: Optional[AgentAIService] = None,
        ai_service_factory: Optional[AgentAIServiceFactory] = None,
    ):
        self.device_manager = device_manager
        self.device = device_manager.device if hasattr(device_manager, 'device') else device_manager
        self.config = config
        self.ipc = ipc
        self._ai_service = ai_service
        self._ai_service_factory = ai_service_factory

        # Session stats
        self.stats = {
            "likes": 0,
            "comments": 0,
            "follows": 0,
            "profile_visits": 0,
            "posts_seen": 0,
            "posts_stopped": 0,
            "session_cost_usd": 0.0,
        }

        # Quotas (overridable from config)
        self.quotas = {
            "max_likes": config.get("max_likes", 80),
            "max_comments": config.get("max_comments", 15),
            "max_follows": config.get("max_follows", 20),
            "max_profile_visits": config.get("max_profile_visits", 40),
            "max_posts_seen": config.get("max_posts_seen", 150),
            "session_duration_min": config.get("session_duration_min", 25),
        }

        self._stop_requested = False
        self._session_start = None
        self._bot_username: Optional[str] = None
        self._account_id: Optional[int] = None
        self._persona_block: str = ""
        self._ai: Optional[Any] = None  # AgentAI instance, set after AI service init
        self._context = AgentContext(platform="instagram")
        # Premium orchestration is prepared by the desktop app and passed in
        # through config. The open-source bot only consumes this runtime context.
        self._desktop_orchestration_context = config.get("desktop_orchestration_context") or {}
        self._agent_plan = self._load_agent_plan(config)
        self._apply_agent_plan_context()

        # Strategy switching
        self._consecutive_skips: int = 0      # consecutive AI-analyzed SKIPs in feed
        self._hashtag_pool: list = []          # AI-generated hashtag pool for exploration
        self._hashtag_index: int = 0           # round-robin pointer into the pool

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def run(self) -> Dict[str, Any]:
        """Run the Taktik Agent session. Returns final stats."""
        self._session_start = time.time()

        try:
            # Step 1: Identify the bot account and load persona
            if not self._initialize_persona():
                return self._fail("Could not identify bot account")

            # Step 2: Consume desktop-provided orchestration context
            self._apply_desktop_orchestration_context()

            # Step 3: Initialize AI decision engine
            if not self._initialize_ai():
                return self._fail("Could not initialize AI service — check API key")

            # Step 4: Navigate to home feed
            self._announce_desktop_step("browse_feed", "Navigating to home feed")
            self._send_status("navigating", "Navigating to home feed…")
            if not self._navigate_to_feed():
                return self._fail("Could not navigate to home feed")

            time.sleep(2)

            # Step 4: Main browsing loop
            self._send_status("running", "Taktik Agent is active")
            self._run_feed_loop()

            # Finalize
            self._context.update_stats(self.stats)
            self._send_status("completed", "Session completed", stats=self.stats)
            return {"success": True, "stats": self.stats}

        except Exception as exc:
            logger.exception(f"[TaktikAgent] Unexpected error: {exc}")
            self._send_status("error", str(exc))
            return {"success": False, "error": str(exc), "stats": self.stats}

    def stop(self):
        """Request graceful stop."""
        self._stop_requested = True

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _initialize_persona(self) -> bool:
        """Visit own profile, detect username, load account context from DB."""
        logger.info("[TaktikAgent] Visiting own profile to detect account…")

        try:
            from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness
            profile_biz = ProfileBusiness(self.device_manager)

            # Navigate to own profile tab
            from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
            tab_nav = NavigationActions(self.device_manager)
            tab_nav.navigate_to_profile_tab()
            time.sleep(1.5)

            # Extract profile info
            profile_info = profile_biz.get_complete_profile_info(navigate_if_needed=False)
            if not profile_info or not profile_info.get("username"):
                logger.error("[TaktikAgent] Could not extract own profile username")
                return False

            self._bot_username = profile_info["username"]
            logger.info(f"[TaktikAgent] Bot account: @{self._bot_username}")

            # Load account profile data from SQLite
            db = get_db_service()
            account_data = db.get_account_by_username(self._bot_username)
            self._account_id = _get(account_data, "account_id")

            # Build UserProfile (persona)
            user_profile = UserProfile(
                username=self._bot_username,
                bio=profile_info.get("biography", "") or "",
                niche=_get(account_data, "niche", ""),
                objective=_get(account_data, "objective", ""),
                services=_get(account_data, "product_service", ""),
                target_audience=_get(account_data, "target_audience", ""),
                personality=_get(account_data, "tone_personality", ""),
                custom_context=_get(account_data, "custom_context", ""),
            )
            self._persona_block = user_profile.to_prompt_block()
            logger.info(f"[TaktikAgent] Persona loaded:\n{self._persona_block}")
            self._context.account_username = self._bot_username
            self._context.account_id = self._account_id
            self._context.persona_block = self._persona_block
            self._context.session_started_at = self._session_start
            self._context.update_stats(self.stats)

            self._send_status(
                "account_detected",
                f"Account @{self._bot_username} detected",
                stats={"username": self._bot_username, "niche": _get(account_data, "niche", "")},
            )
            return True

        except Exception as exc:
            logger.error(f"[TaktikAgent] _initialize_persona error: {exc}")
            return False

    def _apply_desktop_orchestration_context(self) -> None:
        """Apply premium orchestration context prepared by the desktop app."""
        context = self._desktop_orchestration_context
        if not isinstance(context, dict):
            return

        timeline = context.get("timeline") or []
        warnings = context.get("patternWarnings") or []
        if isinstance(timeline, list):
            self._context.recent_timeline = timeline
        if isinstance(warnings, list):
            self._context.pattern_warnings = warnings

        logger.info(
            "[TaktikAgent] Desktop orchestration context loaded: "
            f"{len(self._context.recent_timeline)} episode(s), "
            f"{len(self._context.pattern_warnings)} warning(s)"
        )

        intro = context.get("introMessage")
        if intro:
            self._send_status(
                "orchestration_context",
                str(intro),
                stats={
                    "source": context.get("source") or "desktop",
                    "timeline_count": len(self._context.recent_timeline),
                    "pattern_warnings": self._context.pattern_warnings,
                },
            )

        if self._agent_plan is not None:
            logger.info(
                "[TaktikAgent] Agent plan loaded in runtime context: "
                f"{self._agent_plan.plan_id} ({len(self._agent_plan.steps)} step(s))"
            )

    def _announce_desktop_step(self, tool: str, fallback_message: str) -> None:
        """Emit the desktop-planned next step when available."""
        context = self._desktop_orchestration_context
        steps = context.get("nextSteps") if isinstance(context, dict) else None
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, dict) and step.get("tool") == tool and step.get("message"):
                    self._send_status(
                        "planning",
                        str(step.get("message")),
                        stats={"tool": tool, "source": context.get("source") or "desktop"},
                    )
                    return
        self._send_status("planning", fallback_message, stats={"tool": tool})

    def _load_agent_plan(self, config: Dict[str, Any]) -> Optional[AgentPlan]:
        """Parse an optional frontend/CLI AgentPlan payload."""
        payload = config.get("agent_plan") or config.get("agentPlan")
        if not payload:
            return None

        try:
            return agent_plan_from_payload(payload, manifest=load_workflow_manifest())
        except Exception as exc:
            logger.warning(f"[TaktikAgent] Ignoring invalid agent plan: {exc}")
            return None

    def _apply_agent_plan_context(self) -> None:
        """Expose the parsed plan in the runtime context without executing it yet."""
        if self._agent_plan is None:
            return

        self._context.agent_plan = self._agent_plan
        self._context.agent_plan_id = self._agent_plan.plan_id
        self._context.agent_plan_source = self._agent_plan.source
        self._context.agent_plan_step_count = len(self._agent_plan.steps)

    def _initialize_ai(self) -> bool:
        """Set up the AI service and AgentAI decision engine."""
        try:
            vision_model = self.config.get("vision_model") or None
            text_model = self.config.get("text_model") or None
            ai_service = self._ai_service

            if ai_service is None:
                if self._ai_service_factory is None:
                    logger.error("[TaktikAgent] No AI service or factory injected")
                    return False

                api_key = self.config.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY", "")
                if not api_key:
                    logger.error("[TaktikAgent] No OpenRouter API key configured")
                    return False

                ai_service = self._ai_service_factory(
                    api_key=api_key,
                    ipc=self.ipc,
                    vision_model=vision_model,
                    text_model=text_model,
                )
                self._ai_service = ai_service

            self._ai = AgentAI(ai_service=ai_service, ipc=self.ipc)
            logger.info("[TaktikAgent] AI engine initialized")
            # Generate hashtag pool now that AI is ready
            self._generate_hashtag_pool()
            return True
        except Exception as exc:
            logger.error(f"[TaktikAgent] _initialize_ai error: {exc}")
            return False

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _navigate_to_feed(self) -> bool:
        """Navigate to the home feed tab."""
        try:
            from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
            tab_nav = NavigationActions(self.device_manager)
            return tab_nav.navigate_to_home()
        except Exception as exc:
            logger.error(f"[TaktikAgent] _navigate_to_feed error: {exc}")
            return False

    def _navigate_to_profile(self, username: str) -> bool:
        """Navigate to a user profile via deep link or search."""
        try:
            from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
            nav = NavigationActions(self.device_manager)
            return nav.navigate_to_profile(username)
        except Exception as exc:
            logger.error(f"[TaktikAgent] _navigate_to_profile({username}) error: {exc}")
            return False

    # ------------------------------------------------------------------
    # Main feed loop
    # ------------------------------------------------------------------

    def _run_feed_loop(self):
        """Browse the feed, stopping on posts and making AI decisions."""
        from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness

        feed = FeedBusiness(self.device_manager)
        session_deadline = self._session_start + self.quotas["session_duration_min"] * 60

        logger.info(
            f"[TaktikAgent] Starting feed loop "
            f"(max_likes={self.quotas['max_likes']}, "
            f"max_follows={self.quotas['max_follows']}, "
            f"duration={self.quotas['session_duration_min']}min)"
        )

        while not self._should_stop(session_deadline):
            self.stats["posts_seen"] += 1

            # Randomly decide whether to stop and analyse this post (~40%)
            if random.randint(1, 100) > POST_STOP_RATE:
                feed._scroll_to_next_post()
                time.sleep(random.uniform(*DELAY_SCROLL_TO_NEXT))
                continue

            self.stats["posts_stopped"] += 1

            # Skip ads
            if feed._is_sponsored_post():
                logger.debug("[TaktikAgent] Skipping sponsored post")
                feed._scroll_to_next_post()
                time.sleep(random.uniform(0.8, 1.5))
                continue

            # Skip reels if configured (default: True)
            if self.config.get("skip_reels", True) and feed._is_reel_post():
                logger.debug("[TaktikAgent] Skipping reel")
                feed._scroll_to_next_post()
                time.sleep(random.uniform(0.8, 1.5))
                continue

            # Get post author
            author = feed._get_current_post_author() or "unknown"
            logger.debug(f"[TaktikAgent] Post #{self.stats['posts_stopped']} by @{author} — taking screenshot")

            # Take a screenshot of the current post
            screenshot_path = self._take_screenshot(f"feed_{self.stats['posts_stopped']}")
            if not screenshot_path:
                feed._scroll_to_next_post()
                continue

            # Check stop BEFORE the AI call (can take 5-20s)
            if self._stop_requested:
                break

            # AI decision
            decision = self._ai.decide_feed_action(
                screenshot_path=screenshot_path,
                persona_block=self._persona_block,
                author_username=author,
            )
            self.stats["session_cost_usd"] += decision.get("cost_usd", 0.0)

            action = decision.get("action", "skip")
            logger.info(
                f"[TaktikAgent] @{author} → {action.upper()} "
                f"(visit_profile={decision.get('visit_profile')}) | {decision.get('reason', '')}"
            )

            # Execute action
            if action == "skip":
                self._consecutive_skips += 1
                # Too many consecutive skips → switch to hashtag exploration
                if self._consecutive_skips >= CONSECUTIVE_SKIP_THRESHOLD and self._hashtag_pool:
                    self._run_hashtag_burst(session_deadline)
                    self._consecutive_skips = 0

            elif action in ("like", "like_comment", "like_save"):
                if self.stats["likes"] < self.quotas["max_likes"]:
                    if feed._like_current_post():
                        self.stats["likes"] += 1
                        self._consecutive_skips = 0
                        time.sleep(random.uniform(*DELAY_AFTER_LIKE))

                    if action == "like_comment" and self.stats["comments"] < self.quotas["max_comments"]:
                        comment_text = decision.get("comment", "")
                        if comment_text:
                            self._post_comment(feed, comment_text, author)
                            self._consecutive_skips = 0

            # Profile visit
            if decision.get("visit_profile") and author != "unknown":
                if self.stats["profile_visits"] < self.quotas["max_profile_visits"]:
                    self._consecutive_skips = 0
                    self._handle_profile_visit(author)

            # Scroll to next post
            feed._scroll_to_next_post()
            time.sleep(random.uniform(*DELAY_SCROLL_TO_NEXT))

        logger.info(f"[TaktikAgent] Feed loop ended. Stats: {self.stats}")

    # ------------------------------------------------------------------
    # Strategy switching — hashtag exploration
    # ------------------------------------------------------------------

    def _generate_hashtag_pool(self):
        """Use AI (cheap text model) to generate relevant hashtags from the persona."""
        import re
        import json

        # Extract key persona lines for context
        context_lines = []
        for line in self._persona_block.splitlines():
            if any(k in line for k in ("Niche", "Services", "Target", "Objective")):
                context_lines.append(line.strip())
        context = " | ".join(context_lines)[:600]

        system = (
            "You are an Instagram hashtag expert. "
            "Return ONLY a valid JSON array of strings (no # symbol, lowercase, no spaces). "
            "No explanation, just the array."
        )
        user = (
            "Generate 10 Instagram hashtags to find potential clients/collaborators for this account.\n"
            f"Context: {context}\n\n"
            'Return format: ["hashtag1", "hashtag2", ...]'
        )

        try:
            result = self._ai.ai_service.text_completion(system, user, temperature=0.7, max_tokens=200)
            if result.get("success"):
                content = result.get("content", "")
                match = re.search(r'\[.*?\]', content, re.DOTALL)
                if match:
                    tags = json.loads(match.group())
                    tags = [re.sub(r'[^a-zA-Z0-9_]', '', t) for t in tags if isinstance(t, str)]
                    tags = [t for t in tags if t]
                    if tags:
                        self._hashtag_pool = tags
                        logger.info(f"[TaktikAgent] Hashtag pool: {tags}")
                        return
        except Exception as exc:
            logger.warning(f"[TaktikAgent] Could not generate hashtag pool: {exc}")

        # Fallback: generic social media / growth hashtags
        self._hashtag_pool = [
            "socialmediamarketing", "instagrammarketing", "growthhacking",
            "digitalmarketing", "contentmarketing", "socialmediamanager",
            "marketingdigital", "communitymanager", "marketingstrategy",
            "instagramgrowth",
        ]
        logger.info(f"[TaktikAgent] Using fallback hashtag pool: {self._hashtag_pool}")

    def _run_hashtag_burst(self, session_deadline: float):
        """Browse a hashtag feed for HASHTAG_POSTS_PER_BURST posts when the home feed yields too many skips."""
        hashtag = self._hashtag_pool[self._hashtag_index % len(self._hashtag_pool)]
        self._hashtag_index += 1

        skip_reels = self.config.get("skip_reels", True)

        logger.info(
            f"[TaktikAgent] 🏷️ Strategy switch → #{hashtag} "
            f"(after {self._consecutive_skips} consecutive skips)"
        )
        if self.ipc:
            self.ipc.strategy_switch(from_strategy="feed", to_strategy="hashtag", hashtag=hashtag)

        try:
            from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
            from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness
            from taktik.core.social_media.instagram.workflows.common.post_navigation import open_first_post_of_profile
            from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS

            nav = NavigationActions(self.device_manager)
            feed = FeedBusiness(self.device_manager)

            if not nav.navigate_to_hashtag(hashtag):
                logger.warning(f"[TaktikAgent] Could not navigate to #{hashtag}")
                return

            time.sleep(1.5)

            # Prefer "Recent" tab for fresh discovery
            for sel in DETECTION_SELECTORS.recent_tab_selectors:
                if self.device.xpath(sel).exists:
                    self.device.xpath(sel).click()
                    time.sleep(1.0)
                    break

            # Open first non-reel post from the grid (try up to 6 posts if needed)
            MAX_GRID_ATTEMPTS = 6
            grid_index = 0
            opened = False
            while grid_index < MAX_GRID_ATTEMPTS:
                if grid_index == 0:
                    ok = open_first_post_of_profile(self.device, logger)
                else:
                    ok = self._click_hashtag_grid_post(grid_index)

                if not ok:
                    break

                time.sleep(1.5)

                if skip_reels and self._is_viewing_reel():
                    logger.debug(
                        f"[TaktikAgent] #{hashtag} grid[{grid_index}] is a Reel — "
                        f"pressing back and trying next post"
                    )
                    self._press_instagram_back()
                    time.sleep(1.0)
                    grid_index += 1
                    continue

                opened = True
                break

            if not opened:
                logger.warning(f"[TaktikAgent] No non-reel post found in #{hashtag} grid")
                return

            for i in range(HASHTAG_POSTS_PER_BURST):
                if self._should_stop(session_deadline):
                    break

                # Detect Reel BEFORE screenshot — can appear as we swipe through hashtag posts
                if skip_reels and self._is_viewing_reel():
                    logger.debug(
                        f"[TaktikAgent] Reel encountered mid-burst in #{hashtag} — "
                        f"pressing back and exiting burst"
                    )
                    self._press_instagram_back()
                    return

                self.stats["posts_seen"] += 1
                self.stats["posts_stopped"] += 1

                author = feed._get_current_post_author() or "unknown"
                logger.debug(
                    f"[TaktikAgent] #{hashtag} post {i + 1}/{HASHTAG_POSTS_PER_BURST} by @{author}"
                )

                screenshot_path = self._take_screenshot(f"hashtag_{hashtag}_{i}")
                if not screenshot_path:
                    self._simple_swipe_next_post()
                    time.sleep(random.uniform(*DELAY_SCROLL_TO_NEXT))
                    continue

                decision = self._ai.decide_feed_action(
                    screenshot_path=screenshot_path,
                    persona_block=self._persona_block,
                    author_username=author,
                )
                self.stats["session_cost_usd"] += decision.get("cost_usd", 0.0)

                action = decision.get("action", "skip")
                logger.info(
                    f"[TaktikAgent] #{hashtag} @{author} → {action.upper()} | {decision.get('reason', '')}"
                )

                if action in ("like", "like_comment", "like_save"):
                    if self.stats["likes"] < self.quotas["max_likes"]:
                        if feed._like_current_post():
                            self.stats["likes"] += 1
                            time.sleep(random.uniform(*DELAY_AFTER_LIKE))

                        if action == "like_comment" and self.stats["comments"] < self.quotas["max_comments"]:
                            comment_text = decision.get("comment", "")
                            if comment_text:
                                self._post_comment(feed, comment_text, author)

                if decision.get("visit_profile") and author != "unknown":
                    if self.stats["profile_visits"] < self.quotas["max_profile_visits"]:
                        self._handle_profile_visit(author)
                        # _handle_profile_visit navigates back to feed — exit burst
                        return

                self._simple_swipe_next_post()
                time.sleep(random.uniform(*DELAY_SCROLL_TO_NEXT))

        except Exception as exc:
            logger.error(f"[TaktikAgent] _run_hashtag_burst({hashtag}) error: {exc}")
        finally:
            logger.info(f"[TaktikAgent] Returning to home feed after #{hashtag} burst")
            self._navigate_to_feed()
            time.sleep(1.5)
            if self.ipc:
                self.ipc.strategy_switch(from_strategy="hashtag", to_strategy="feed", hashtag=hashtag)

    # ------------------------------------------------------------------
    # Hashtag burst helpers
    # ------------------------------------------------------------------

    def _is_viewing_reel(self) -> bool:
        """Return True if we're currently inside a fullscreen Reel player."""
        from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS, FEED_SELECTORS
        # reel_player_indicators: audio/sound controls present only in the Reel player UI
        for sel in POST_SELECTORS.reel_player_indicators:
            try:
                if self.device.xpath(sel).exists:
                    return True
            except Exception:
                pass
        # feed reel_indicators: content-desc "Reel de …" / "Reel by …" visible in feed & hashtag viewer
        for sel in FEED_SELECTORS.reel_indicators:
            try:
                if self.device.xpath(sel).exists:
                    return True
            except Exception:
                pass
        return False

    def _press_instagram_back(self):
        """Click the Instagram in-app back arrow; fall back to the system back button."""
        from taktik.core.social_media.instagram.ui.selectors import POST_SELECTORS
        for sel in POST_SELECTORS.back_button_selectors:
            try:
                el = self.device.xpath(sel)
                if el.exists:
                    el.click()
                    return
            except Exception:
                pass
        self.device.press('back')

    def _click_hashtag_grid_post(self, index: int) -> bool:
        """Click the post at *index* (0-based) in the currently visible hashtag grid."""
        from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS, POST_SELECTORS
        try:
            posts = self.device.xpath(DETECTION_SELECTORS.post_thumbnail_selectors[0]).all()
            if not posts:
                posts = self.device.xpath(POST_SELECTORS.first_post_grid).all()
            if posts and index < len(posts):
                posts[index].click()
                time.sleep(2.5)
                return True
        except Exception as exc:
            logger.debug(f"[TaktikAgent] _click_hashtag_grid_post({index}) error: {exc}")
        return False

    def _simple_swipe_next_post(self):
        """Single vertical swipe to the next post — used in hashtag burst (no smart alignment needed)."""
        try:
            screen_h = self.device.info.get('displayHeight', 1920)
            screen_w = self.device.info.get('displayWidth', 1080)
            self.device.swipe_coordinates(
                screen_w // 2, int(screen_h * 0.72),
                screen_w // 2, int(screen_h * 0.22),
                duration=0.3,
            )
        except Exception as exc:
            logger.debug(f"[TaktikAgent] _simple_swipe_next_post error: {exc}")

    # ------------------------------------------------------------------
    # Profile visit
    # ------------------------------------------------------------------

    def _handle_profile_visit(self, username: str):
        """Navigate to a profile, take a screenshot, and let AI decide whether to follow."""
        logger.info(f"[TaktikAgent] Visiting profile @{username}")

        if not self._navigate_to_profile(username):
            logger.warning(f"[TaktikAgent] Could not navigate to @{username}")
            return

        self.stats["profile_visits"] += 1
        time.sleep(1.5)

        screenshot_path = self._take_screenshot(f"profile_{username}")
        if not screenshot_path:
            self._navigate_to_feed()
            return

        decision = self._ai.decide_profile_follow(
            screenshot_path=screenshot_path,
            persona_block=self._persona_block,
            profile_username=username,
        )
        self.stats["session_cost_usd"] += decision.get("cost_usd", 0.0)

        logger.info(
            f"[TaktikAgent] @{username} → {'FOLLOW' if decision['follow'] else 'SKIP'} "
            f"(extra_likes={decision['extra_likes']}) | {decision.get('reason', '')}"
        )

        if decision["follow"] and self.stats["follows"] < self.quotas["max_follows"]:
            self._do_follow(username)
            time.sleep(random.uniform(*DELAY_AFTER_FOLLOW))

        # Extra likes on the profile
        extra = min(decision.get("extra_likes", 0), 2)
        if extra > 0 and self.stats["likes"] < self.quotas["max_likes"]:
            self._like_profile_posts(username, extra)

        time.sleep(random.uniform(*DELAY_AFTER_PROFILE_VISIT))

        # Return to feed
        self._navigate_to_feed()
        time.sleep(1.5)

    # ------------------------------------------------------------------
    # Low-level actions
    # ------------------------------------------------------------------

    def _do_follow(self, username: str):
        """Follow the currently visible profile."""
        try:
            from taktik.core.social_media.instagram.actions.atomic.interaction.profile_interaction import ProfileInteractionActions
            profile_interaction = ProfileInteractionActions(self.device_manager)
            success = profile_interaction.follow_user(username)
            if success:
                self.stats["follows"] += 1
                logger.info(f"[TaktikAgent] ✅ Followed @{username}")
                if self.ipc:
                    self.ipc.send("follow", username=username, success=True)
        except Exception as exc:
            logger.error(f"[TaktikAgent] _do_follow({username}) error: {exc}")

    def _like_profile_posts(self, username: str, count: int):
        """Like up to `count` posts on the currently visible profile grid."""
        try:
            from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import LikeBusiness
            like_biz = LikeBusiness(self.device_manager)
            liked = 0
            for _ in range(count):
                if liked >= count or self.stats["likes"] >= self.quotas["max_likes"]:
                    break
                if like_biz.like_next_profile_post():
                    self.stats["likes"] += 1
                    liked += 1
                    time.sleep(random.uniform(1.5, 3.0))
        except Exception as exc:
            logger.debug(f"[TaktikAgent] _like_profile_posts({username}, {count}) error: {exc}")

    def _post_comment(self, feed, comment_text: str, author: str):
        """Type and post a comment on the current feed post."""
        try:
            if feed._comment_current_post({"custom_comments": [comment_text]}):
                self.stats["comments"] += 1
                logger.info(f"[TaktikAgent] 💬 Commented on @{author}'s post")
                time.sleep(random.uniform(*DELAY_AFTER_COMMENT))
                if self.ipc:
                    self.ipc.send("comment", username=author, comment=comment_text, success=True)
        except Exception as exc:
            logger.error(f"[TaktikAgent] _post_comment error: {exc}")

    def _take_screenshot(self, label: str) -> Optional[str]:
        """Take a device screenshot and save to a temp file. Returns path or None."""
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", prefix=f"taktik_agent_{label}_", delete=False
            )
            tmp.close()
            self.device.screenshot(tmp.name)
            return tmp.name
        except Exception as exc:
            logger.error(f"[TaktikAgent] screenshot({label}) error: {exc}")
            return None

    # ------------------------------------------------------------------
    # Quota / stop helpers
    # ------------------------------------------------------------------

    def _should_stop(self, deadline: float) -> bool:
        if self._stop_requested:
            logger.info("[TaktikAgent] Stop requested by user")
            return True
        if time.time() > deadline:
            logger.info("[TaktikAgent] Session duration limit reached")
            return True
        if self.stats["posts_seen"] >= self.quotas["max_posts_seen"]:
            logger.info("[TaktikAgent] Max posts seen reached")
            return True
        if (self.stats["likes"] >= self.quotas["max_likes"] and
                self.stats["follows"] >= self.quotas["max_follows"] and
                self.stats["comments"] >= self.quotas["max_comments"]):
            logger.info("[TaktikAgent] All quotas reached")
            return True
        return False

    # ------------------------------------------------------------------
    # IPC helpers
    # ------------------------------------------------------------------

    def _send_status(self, status: str, message: str = "", stats: dict = None):
        if self.ipc:
            self.ipc.agent_status(status=status, message=message, stats=stats or self.stats)

    def _fail(self, error: str) -> Dict[str, Any]:
        self._send_status("error", error)
        return {"success": False, "error": error, "stats": self.stats}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _get(d: Optional[Dict], key: str, default: Any = None) -> Any:
    """Safe dict getter that handles None dict."""
    if d is None:
        return default
    return d.get(key) or default
