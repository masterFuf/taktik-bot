"""Taktik Agent — autonomous social media workflow (Instagram-first).

Platform-agnostic orchestration layer: inject the right `device_manager`
and the appropriate platform actions, and it works on Instagram, TikTok, etc.

Current implementation: Instagram feed browsing.
  1. Visits own profile → loads account context (niche, persona) from SQLite
  2. Navigates to the home feed
  3. Scrolls through posts, stopping on ~40% of them
  4. For each stopped post: takes a screenshot → AI decides (like / skip / comment / save)
  5. If AI says visit_profile: navigate to author → screenshot → AI decides (follow / skip)
  6. Respects its session quotas and the warmup budget of the account's day, counted gesture by
     gesture (one read of the day each), with the warmup's pace floor after each gesture; stops
     when a quota or a warmup cap is reached, and says which in its final stats
  7. Emits IPC events throughout for the Taktik Agent panel
"""

import time
import random
import tempfile
from typing import Dict, Any, Optional, Tuple
from loguru import logger

from taktik.core.app.ai.spend import AI_SPEND_HASHTAGS

from taktik.core.shared.behavior.tap import tap_element_human
from taktik.core.shared.diagnostics import run_halt
from taktik.core.database import get_db_service
from taktik.core.database.account_health import witness_for
from taktik.core.app.ai.comments.comment_ai import UserProfile
from taktik.core.agent.decision.agent_ai import AgentAI
from taktik.core.agent.io.manifest import load_workflow_manifest
from taktik.core.agent.io.plan import agent_plan_from_payload
from taktik.core.agent.kernel.context import AgentContext
from taktik.core.agent.kernel.contracts import AgentPlan
from taktik.core.agent.kernel.ports import AgentAIService, AgentAIServiceFactory


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

# Delays between actions (seconds). After a gesture (like, comment, follow), never under the
# warmup's pace floor (`_pause_after_gesture`).
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
        warmup=None,
    ):
        self.device_manager = device_manager
        self.device = device_manager.device if hasattr(device_manager, 'device') else device_manager
        # Imported here: the Instagram package imports the Agent kernel.
        from taktik.core.social_media.instagram.workflows.agent.payload import taktik_agent_request_from_payload

        # The payload is read once, by the reader the launcher and the app's contract share.
        self.request = taktik_agent_request_from_payload(config)
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
            # Profiles skipped because a relationship already existed.
            "profiles_skipped_relationship": 0,
        }

        self.quotas = self.request.quotas

        # The agent is a GROWTH path. A profile already in a relationship is not a target: it
        # is skipped BEFORE the screenshot and the qualification call, which saves the vision
        # cost, and its follow button is never tapped again — tapping an already-following
        # one would unfollow. On by default, and disableable if the agent should one day
        # re-engage its own audience.
        self._skip_related_profiles = self.request.skip_related_profiles
        self._skip_reels = self.request.skip_reels

        # The warmup budget of the account's day, the automation's counter (`WarmupBudget`), handed
        # by the launcher on the caps of the file; None when constructed without one (no cap). It
        # reads the day from the ledger, where each like, comment and follow of this session is
        # filed: asked before each of them, it counts the session gesture by gesture. Its pace
        # floor lengthens the pause after each of them.
        self._warmup = warmup
        if warmup is not None:
            warmup.count_against_account(lambda: self._account_id)
        # The warmup cap that ended the session, once reached: no gesture after it.
        self._warmup_stop = ""

        self._stop_requested = False
        self._session_start = None
        self._bot_username: Optional[str] = None
        self._account_id: Optional[int] = None
        self._persona_block: str = ""
        self._ai: Optional[Any] = None  # AgentAI instance, set after AI service init
        self._context = AgentContext(platform="instagram")
        # Premium orchestration is prepared by the desktop app and passed in
        # through config. The open-source bot only consumes this runtime context.
        self._orchestration = self.request.orchestration
        self._agent_plan = self._load_agent_plan(self.request.agent_plan)
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
        # A block seen anywhere in this run becomes one entry of the account's health history.
        run_halt.configurer_temoin(witness_for(
            "instagram", lambda: self._bot_username, source_type=lambda: "AGENT"))

        try:
            # Step 0: the app's language, before any localized selector (AGENTS.md invariant).
            # Without it the active language stayed unknown for the whole session, and the
            # block detector took any Instagram alert for a block on its ids alone.
            try:
                from taktik.core.social_media.instagram.ui.language import detect_and_optimize

                detect_and_optimize(self.device)
            except Exception as exc:
                logger.warning(f"[TaktikAgent] Language detection failed (non-fatal): {exc}")

            # Step 1: Identify the bot account and load persona
            if not self._initialize_persona():
                return self._fail("Could not identify bot account", message_key="agentStatusErrNoAccount")

            # Step 2: Consume desktop-provided orchestration context
            self._apply_desktop_orchestration_context()

            # Step 3: Initialize AI decision engine
            if not self._initialize_ai():
                return self._fail("Could not initialize AI service — check API key",
                                  message_key="agentStatusErrNoAi")

            # Step 4: Navigate to home feed
            self._announce_desktop_step("browse_feed", "Navigating to home feed",
                                        message_key="agentStatusNavigating")
            self._send_status("navigating", "Navigating to home feed…", message_key="agentStatusNavigating")
            if not self._navigate_to_feed():
                return self._fail("Could not navigate to home feed", message_key="agentStatusErrNoFeed")

            time.sleep(2)

            # Step 4: Main browsing loop
            self._send_status("running", "Taktik Agent is active", message_key="agentStatusActive")
            self._run_feed_loop()

            # Finalize. A stop on the run's lock goes in the stats (the status stays "completed":
            # the app has no status for it yet). Its sentences carry no number.
            halt = run_halt.arret_demande()
            if halt:
                self._note_stop_reason(halt["code"], {})
            self._context.update_stats(self.stats)
            self._send_status("completed", "Session completed", stats=self.stats,
                              message_key="agentStatusCompleted")
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
                message_key="agentStatusAccountDetected",
            )
            return True

        except Exception as exc:
            logger.error(f"[TaktikAgent] _initialize_persona error: {exc}")
            return False

    def _apply_desktop_orchestration_context(self) -> None:
        """Apply premium orchestration context prepared by the desktop app."""
        context = self._orchestration
        self._context.recent_timeline = context.timeline
        self._context.pattern_warnings = context.pattern_warnings

        logger.info(
            "[TaktikAgent] Desktop orchestration context loaded: "
            f"{len(self._context.recent_timeline)} episode(s), "
            f"{len(self._context.pattern_warnings)} warning(s)"
        )

        intro = context.intro_message
        if intro:
            self._send_status(
                "orchestration_context",
                str(intro),
                stats={
                    "source": context.source,
                    "timeline_count": len(self._context.recent_timeline),
                    "pattern_warnings": self._context.pattern_warnings,
                },
            )

        if self._agent_plan is not None:
            logger.info(
                "[TaktikAgent] Agent plan loaded in runtime context: "
                f"{self._agent_plan.plan_id} ({len(self._agent_plan.steps)} step(s))"
            )

    def _announce_desktop_step(self, tool: str, fallback_message: str, message_key: str = None) -> None:
        """Emit the desktop-planned next step when available.

        The desktop-provided step message is already localized (no key); only the English
        fallback carries `message_key` so the desktop can localize it too."""
        context = self._orchestration
        for step in context.next_steps:
            if isinstance(step, dict) and step.get("tool") == tool and step.get("message"):
                self._send_status(
                    "planning",
                    str(step.get("message")),
                    stats={"tool": tool, "source": context.source},
                )
                return
        self._send_status("planning", fallback_message, stats={"tool": tool}, message_key=message_key)

    def _load_agent_plan(self, payload: Any) -> Optional[AgentPlan]:
        """Parse an optional frontend/CLI AgentPlan payload."""
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
            vision_model = self.request.vision_model
            text_model = self.request.text_model
            ai_service = self._ai_service

            if ai_service is None:
                if self._ai_service_factory is None:
                    logger.error("[TaktikAgent] No AI service or factory injected")
                    return False

                api_key = self.request.openrouter_api_key
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

            self._ai = AgentAI(ai_service=ai_service, ipc=self.ipc, language=self.request.language)
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
        feed = self._feed_business()
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
            if self._skip_reels and feed._is_reel_post():
                logger.debug("[TaktikAgent] Skipping reel")
                feed._scroll_to_next_post()
                time.sleep(random.uniform(0.8, 1.5))
                continue

            # Get post author. None when unreadable: the post is then not engaged (see
            # `_engage_post`), and the AI is told "unknown".
            author = feed._get_current_post_author()
            logger.debug(f"[TaktikAgent] Post #{self.stats['posts_stopped']} by @{author or 'unknown'} — taking screenshot")

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
                author_username=author or "unknown",
            )
            self.stats["session_cost_usd"] += decision.get("cost_usd", 0.0)

            action = decision.get("action", "skip")
            logger.info(
                f"[TaktikAgent] @{author or 'unknown'} → {action.upper()} "
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
                engaged, blocked = self._engage_post(feed, author, action, decision)
                if engaged:
                    self._consecutive_skips = 0
                if blocked:
                    break

            # Profile visit
            if decision.get("visit_profile") and author:
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
            result = self._ai.ai_service.text_completion(system, user, temperature=0.7, max_tokens=200,
                                                         label='autopilot_hashtags', kind=AI_SPEND_HASHTAGS)
            if result.get("success"):
                content = result.get("text", "")
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
        logger.warning(f"[TaktikAgent] No hashtags from the model; using the generic fallback pool: {self._hashtag_pool}")

    def _run_hashtag_burst(self, session_deadline: float):
        """Browse a hashtag feed for HASHTAG_POSTS_PER_BURST posts when the home feed yields too many skips."""
        hashtag = self._hashtag_pool[self._hashtag_index % len(self._hashtag_pool)]
        self._hashtag_index += 1

        skip_reels = self._skip_reels

        logger.info(
            f"[TaktikAgent] 🏷️ Strategy switch → #{hashtag} "
            f"(after {self._consecutive_skips} consecutive skips)"
        )
        if self.ipc:
            self.ipc.strategy_switch(from_strategy="feed", to_strategy="hashtag", hashtag=hashtag)

        try:
            from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
            from taktik.core.social_media.instagram.workflows.common.post_navigation import open_first_post_of_profile
            from taktik.core.social_media.instagram.ui.selectors import DETECTION_SELECTORS

            nav = NavigationActions(self.device_manager)
            feed = self._feed_business()

            if not nav.navigate_to_hashtag(hashtag):
                logger.warning(f"[TaktikAgent] Could not navigate to #{hashtag}")
                return

            time.sleep(1.5)

            # Prefer "Recent" tab for fresh discovery
            for sel in DETECTION_SELECTORS.recent_tab_selectors:
                _recent = self.device.xpath(sel)
                if _recent.exists:
                    if not tap_element_human(self.device, _recent, logger=logger):
                        _recent.click()
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

                author = feed._get_current_post_author()
                logger.debug(
                    f"[TaktikAgent] #{hashtag} post {i + 1}/{HASHTAG_POSTS_PER_BURST} by @{author or 'unknown'}"
                )

                screenshot_path = self._take_screenshot(f"hashtag_{hashtag}_{i}")
                if not screenshot_path:
                    self._simple_swipe_next_post()
                    time.sleep(random.uniform(*DELAY_SCROLL_TO_NEXT))
                    continue

                decision = self._ai.decide_feed_action(
                    screenshot_path=screenshot_path,
                    persona_block=self._persona_block,
                    author_username=author or "unknown",
                )
                self.stats["session_cost_usd"] += decision.get("cost_usd", 0.0)

                action = decision.get("action", "skip")
                logger.info(
                    f"[TaktikAgent] #{hashtag} @{author or 'unknown'} → {action.upper()} | {decision.get('reason', '')}"
                )

                if action in ("like", "like_comment", "like_save"):
                    _engaged, blocked = self._engage_post(feed, author, action, decision)
                    if blocked:
                        return

                if decision.get("visit_profile") and author:
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
                if not tap_element_human(self.device, posts[index], logger=logger):
                    posts[index].click()
                time.sleep(2.5)
                return True
        except Exception as exc:
            logger.debug(f"[TaktikAgent] _click_hashtag_grid_post({index}) error: {exc}")
        return False

    def _simple_swipe_next_post(self):
        """Single vertical advance to the next post — used in hashtag burst (no smart alignment needed)."""
        try:
            # Humanized fling (coast) to the next post instead of a fixed-coordinate swipe.
            self.device.human_scroll("down", distance_ratio=0.5, coast=True)
        except Exception as exc:
            logger.debug(f"[TaktikAgent] _simple_swipe_next_post error: {exc}")

    # ------------------------------------------------------------------
    # Profile visit
    # ------------------------------------------------------------------

    def _handle_profile_visit(self, username: str):
        """Navigate to a profile, take a screenshot, and let AI decide whether to follow."""
        logger.info(f"[TaktikAgent] Visiting profile @{username}")

        # The run's lock, set in the hashtag burst, on the feed or during a navigation: no
        # visit, no paid AI call, no follow after a block.
        if run_halt.arret_demande():
            logger.warning("[TaktikAgent] Run stop requested — no profile visit")
            return
        # A warmup cap reached on the post: no visit, no paid AI call for a follow it would refuse.
        if self._warmup_spent():
            return

        if not self._navigate_to_profile(username):
            logger.warning(f"[TaktikAgent] Could not navigate to @{username}")
            return
        # The navigation itself looks for problem pages and may have just seen the block.
        if run_halt.arret_demande():
            logger.warning("[TaktikAgent] Run stop requested during the navigation — no AI call, no follow")
            self._navigate_to_feed()
            return

        self.stats["profile_visits"] += 1
        time.sleep(1.5)

        # RELATIONSHIP guard, the profile being on screen: the same source of truth as the
        # manual workflows. The skip happens BEFORE the screenshot and the qualification, so
        # the vision is not paid on a non-target and the follow is never reached on an
        # already-followed profile. An unreadable state lets the profile through, so no
        # instable).
        if self._skip_related_profiles:
            state = self._read_follow_state()
            if state in ("following", "requested", "follow_back", "message"):
                logger.info(f"[TaktikAgent] @{username} ignore — relation existante ({state})")
                self.stats["profiles_skipped_relationship"] += 1
                self._navigate_to_feed()
                return

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

        if (decision["follow"] and self.stats["follows"] < self.quotas["max_follows"]
                and self._warmup_allows("follow")):
            self._do_follow(username)
            self._pause_after_gesture(DELAY_AFTER_FOLLOW)
            if self._block_seen("follow"):
                self._navigate_to_feed()
                return

        # Extra likes on the profile
        extra = min(decision.get("extra_likes", 0), 2)
        if extra > 0 and self.stats["likes"] < self.quotas["max_likes"]:
            if self._like_profile_posts(username, extra):
                self._pause_after_gesture(DELAY_AFTER_LIKE)
            # A refusal here sets the run's lock; `_should_stop` ends the loop on its next turn.
            self._block_seen("like")

        time.sleep(random.uniform(*DELAY_AFTER_PROFILE_VISIT))

        # Return to feed
        self._navigate_to_feed()
        time.sleep(1.5)

    # ------------------------------------------------------------------
    # Low-level actions
    # ------------------------------------------------------------------

    def _read_follow_state(self) -> str:
        """State of the profile header action button, the profile being already on screen.
        Unreadable states let the caller through, fail-open."""
        try:
            from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions
            return ClickActions(self.device).get_follow_button_state()
        except Exception as exc:
            logger.debug(f"[TaktikAgent] _read_follow_state error: {exc}")
            return "unknown"

    def _do_follow(self, username: str):
        """Follow the currently visible profile."""
        try:
            # ClickActions compose ProfileInteractionMixin (follow_user + get_follow_button_state).
            # NB: the former import did not exist, so the error was swallowed by this handler and
            # the agent NEVER followed. Fixed here.
            from taktik.core.social_media.instagram.actions.atomic.interaction import ClickActions
            profile_interaction = ClickActions(self.device)
            # Safety net: the follow action taps the button without checking its state, so on an
            # already-followed profile it would UNFOLLOW. The pre-check already covers that case
            # when the skip is enabled; this guard also protects when it is not.
            state = profile_interaction.get_follow_button_state()
            if state in ("following", "requested", "message"):
                logger.info(f"[TaktikAgent] @{username} deja suivi ({state}) — pas de re-follow")
                return
            success = profile_interaction.follow_user(username)
            if success:
                self.stats["follows"] += 1
                logger.info(f"[TaktikAgent] ✅ Followed @{username}")
                self._record_follow(username)
                if self.ipc:
                    self.ipc.send("follow", username=username, success=True)
        except Exception as exc:
            logger.error(f"[TaktikAgent] _do_follow({username}) error: {exc}")

    def _record_follow(self, username: str) -> None:
        """The ledger row of a follow, the interaction engine's `_record_action(username,
        'FOLLOW', 1)` on a business object carrying the account. The autopilot's follows were
        counted on its card and nowhere else: no row, so they escaped the daily follow cap and
        the unfollow never knew the bot had followed them (`not_followed_by_bot`)."""
        try:
            self._feed_business()._record_action(username, 'FOLLOW', 1)
        except Exception as exc:
            logger.error(f"[TaktikAgent] Follow of @{username} not recorded: {exc}")

    def _like_profile_posts(self, username: str, count: int) -> int:
        """Like up to `count` posts of the profile on screen, through the production sequence
        of the target workflows (`LikeBusiness.like_profile_posts`), which files its likes in
        one batch at the end of the profile. The likes given (0 on a failure, which is logged).

        The autopilot called a `like_next_profile_post` that never existed, from a module that does
        not export `LikeBusiness`: the exception was swallowed and no extra like was ever given."""
        count = min(count, self.quotas["max_likes"] - self.stats["likes"])
        # Filed in one batch at the end of the profile: cut to what the warmup leaves first.
        left = self._warmup.actions_left(self._written_actions()) if self._warmup is not None else None
        if left is not None:
            count = min(count, left)
        if count <= 0:
            return 0
        try:
            from taktik.core.social_media.instagram.actions.business.actions.like import LikeBusiness
            like_biz = LikeBusiness(self.device_manager, automation=self._automation_identity())
            result = like_biz.like_profile_posts(username, max_likes=count, navigate_to_profile=False)
            liked = int(result.get("posts_liked", 0))
            self.stats["likes"] += liked
            return liked
        except Exception as exc:
            logger.error(f"[TaktikAgent] _like_profile_posts({username}, {count}) error: {exc}")
            return 0

    def _automation_identity(self):
        """The account the gestures are filed under. The agent has no session row, so its rows
        carry the account only."""
        from types import SimpleNamespace

        return SimpleNamespace(active_account_id=self._account_id, current_session_id=None)

    def _feed_business(self):
        """The Feed's business object, filed under the operator's account.

        The autopilot likes and comments through the Feed's own gestures, and so through its
        recording: `_like_current_post(record_as=author)` (`LikeBusiness.record_post_like`) and
        `_comment_feed_post` (`CommentAction.comment_on_post(username=author)`). Built without
        an identity, the ledger write refused every row: the autopilot's likes and comments left
        no trace and escaped the daily caps."""
        from taktik.core.social_media.instagram.actions.business.workflows.feed import FeedBusiness

        return FeedBusiness(self.device_manager, automation=self._automation_identity())

    def _engage_post(self, feed, author: Optional[str], action: str,
                     decision: Dict[str, Any]) -> tuple:
        """Like, then comment when the AI asked for it, the post on screen. (engaged, blocked).

        A post whose author cannot be read is not engaged: without an author there is no ledger
        row, no deduplication and no cap (the Feed's rule). The comment follows a like that has
        just landed, as in the Feed: once the like cap was reached the autopilot went on
        commenting posts it no longer liked."""
        if not author:
            logger.info("[TaktikAgent] Post author unreadable: post not engaged, it could not be recorded")
            return False, False
        engaged = False
        if self.stats["likes"] < self.quotas["max_likes"] and self._warmup_allows("like"):
            if feed._like_current_post(record_as=author):
                self.stats["likes"] += 1
                engaged = True
                # After the pause that follows a like (the dialog comes from the server and can
                # take a moment), before the comment touches the screen.
                self._pause_after_gesture(DELAY_AFTER_LIKE)
                if self._block_seen("like"):
                    return engaged, True

        if (engaged and action == "like_comment" and self.stats["comments"] < self.quotas["max_comments"]
                and self._warmup_allows("comment")):
            comment_text = decision.get("comment", "")
            if comment_text:
                self._post_comment(feed, comment_text, author)
                engaged = True
                if self._block_seen("comment"):
                    return engaged, True
        return engaged, False

    def _post_comment(self, feed, comment_text: str, author: str):
        """Post the AI's comment on the current post, filed under its author.

        The Feed's comment (`FeedBusiness._comment_feed_post`, i.e.
        `CommentAction.comment_on_post(username=author)`): the comment is filed at the send,
        "Try again later" is looked for, and the sheet is closed by the production closer. The
        autopilot used `_comment_current_post`, which recorded nothing and closed the sheet with
        the facade's back key, ignored by uiautomator2."""
        try:
            result = feed._comment_feed_post(author, {}, comment_text=comment_text)
            if result.get("commented"):
                self.stats["comments"] += 1
                logger.info(f"[TaktikAgent] 💬 Commented on @{author}'s post")
                self._pause_after_gesture(DELAY_AFTER_COMMENT)
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

    def _block_seen(self, action: str) -> bool:
        """After a write: is Instagram refusing it ("Try again later")? One dump, never raises.

        The one look of every Instagram writing path (`look_for_action_block`); the detector sets
        the run's lock, which `_should_stop` reads: one sighting ends the session.
        """
        from taktik.core.shared.diagnostics.action_block import look_for_action_block
        from taktik.core.social_media.instagram.ui.detectors.problematic_page import (
            ProblematicPageDetector,
        )
        return look_for_action_block(ProblematicPageDetector(self.device), after=action)

    def _should_stop(self, deadline: float) -> bool:
        if self._stop_requested:
            logger.info("[TaktikAgent] Stop requested by user")
            return True
        # The run's lock: a block ("Try again later") seen by the detector, a lost phone.
        # The autopilot never read it (2026-09-24).
        halt = run_halt.arret_demande()
        if halt:
            logger.warning(f"[TaktikAgent] Run stop requested: {halt.get('code')}")
            return True
        if self._warmup_spent():
            return True
        if time.time() > deadline:
            logger.info("[TaktikAgent] Session duration limit reached")
            return True
        if self.stats["posts_seen"] >= self.quotas["max_posts_seen"]:
            logger.info("[TaktikAgent] Max posts seen reached")
            return True
        # A comment follows a like (`_engage_post`): once the likes are spent, so are the
        # comments, whatever their own counter says.
        if (self.stats["likes"] >= self.quotas["max_likes"] and
                self.stats["follows"] >= self.quotas["max_follows"]):
            logger.info("[TaktikAgent] All quotas reached")
            return True
        return False

    # ------------------------------------------------------------------
    # Warmup budget of the account's day
    # ------------------------------------------------------------------

    def _written_actions(self) -> int:
        """This session's written actions (likes + follows + comments), the unit of the warmup's
        session cap, as in the automation."""
        return self.stats["likes"] + self.stats["follows"] + self.stats["comments"]

    def _warmup_spent(self) -> bool:
        """Has a warmup cap ended the session: the day's actions, the run's actions, or a day that
        can no longer be read? One read of the day; the first reason is kept for the final stats."""
        if self._warmup is None:
            return False
        if self._warmup_stop:
            return True
        return self._ends_the_session(self._warmup.stop_reason(self._written_actions()))

    def _warmup_allows(self, intent: str) -> bool:
        """May this written gesture (`like`, `comment`, `follow`) be made under the warmup budget?

        Asked just before it, on ONE read of the day (`WarmupBudget.check`): a gesture that would
        pass a cap is not made. A spent daily quota of follows or comments disables that gesture
        only, the session goes on (the automation's rule). Two reads per gesture doubled the failed
        reads a busy base counts toward `daily_budget_unreadable`.
        """
        if self._warmup is None:
            return True
        if self._warmup_stop:
            return False
        check = self._warmup.check(self._written_actions())
        if self._ends_the_session(check.stop_reason):
            return False
        return intent not in check.exhausted_intents

    def _ends_the_session(self, reason) -> bool:
        """Keep the warmup cap that ends the session, if `reason` is one: no gesture after it."""
        if not reason:
            return False
        self._warmup_stop = reason
        self._note_stop_reason(reason.code, reason.params)
        logger.info(f"[TaktikAgent] Warmup budget reached: {reason}")
        return True

    def _note_stop_reason(self, code: str, params: Dict[str, Any]) -> None:
        """Why the session stopped before its own quotas, in the final stats: the code the app
        words, and the numbers its sentence shows ("Budget du jour atteint (50/50)")."""
        self.stats["stop_reason"] = code
        self.stats["stop_reason_params"] = dict(params)

    def _pause_after_gesture(self, bounds: Tuple[float, float]) -> None:
        """The pause after a like, a comment or a follow: its own range, never under the warmup's
        pace floor (`minActionGapSeconds`, up to 45 s on a cold account). The automation's rule
        between two actions, the same draw (`WarmupBudget.action_gap`)."""
        low, high = bounds
        time.sleep(self._warmup.action_gap(low, high) if self._warmup is not None else random.uniform(low, high))

    # ------------------------------------------------------------------
    # IPC helpers
    # ------------------------------------------------------------------

    def _send_status(self, status: str, message: str = "", stats: dict = None,
                     message_key: str = None):
        if self.ipc:
            self.ipc.agent_status(status=status, message=message, stats=stats or self.stats,
                                  message_key=message_key)

    def _fail(self, error: str, message_key: str = None) -> Dict[str, Any]:
        # `error` stays as the English fallback / machine error; `message_key` (when the failure is a
        # fixed, known one) lets the desktop show it in the app language.
        self._send_status("error", error, message_key=message_key)
        return {"success": False, "error": error, "stats": self.stats}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _get(d: Optional[Dict], key: str, default: Any = None) -> Any:
    """Safe dict getter that handles None dict."""
    if d is None:
        return default
    return d.get(key) or default
