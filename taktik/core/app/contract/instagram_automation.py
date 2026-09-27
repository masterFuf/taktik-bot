"""Instagram automation (`instagram.automation.*`): the file `desktop_bridge` reads.

Nine workflows share one launcher (`run_instagram_automation`), one reader
(`build_instagram_automation_config`) and one bridge; `workflowType` picks the workflow. Each key
names where the reader puts its value (`attr`, a dotted path in the built config), or the function
it is handed to (`via`: the AI hooks, the AI service, the pacing profile). `tests/unit/app/contract`
holds the reader and the bridge to it.

The lines the app reads come from the bridge (status, the settings echo, the final counters),
from the run (session, sources, sync, stop) and from what a run does on a profile or a post
(`IPCEmitter`, the AI service, the decision round trip). Every line of the family is declared once:
a workflow prints the lines of what it does.

The reader refuses `workflowType: notifications`: reading the activity feed is the notifications
bridge's (`instagram.engagement.notifications`, `instagram_notifications.py`).
"""

from __future__ import annotations

from .schema import HOST, Computed, Event, Field, ListOf, MapOf, OneOf, Shape, WorkflowContract
from .shared import (
    AI_EVENTS,
    ERROR_EVENT,
    LOG_EVENT,
    NETWORK_RESET_COMPLETE_EVENT,
    STATUS_EVENT,
    device_field,
    network_reset_field,
)

_CORE = "taktik.core.social_media.instagram.workflows.core"
_BUILDER = f"{_CORE}.config_builder:build_instagram_automation_config"
_LAUNCHER = f"{_CORE}.agent_handler:run_instagram_automation"
_AI_HOOKS = f"{_CORE}.ai_hooks:install_instagram_ai_hooks"
_AI_SERVICE = "taktik.core.app.ai.factory:create_ai_service"
_PACING = "taktik.core.shared.behavior.policy:parse_behavior_policy"

#: `SUPPORTED_WORKFLOW_TYPES` of the reader, in the manifest's order.
WORKFLOW_TYPES = (
    "target_followers",
    "target_following",
    "target_profiles",
    "hashtags",
    "post_url",
    "unfollow",
    "feed",
    "sync_following",
    "sync_followers_following",
)

_FEED = {"workflowType": "feed"}
_UNFOLLOW = {"workflowType": "unfollow"}
_DECIDE = {"ai.decision.mode": "decide"}

_ACTION = "actions.0"

LIMITS = Shape(
    name="InstagramAutomationLimits",
    doc="The run's budget.",
    fields=(
        Field("maxProfiles", "int", "Profiles to interact with; posts to browse for the feed.", default=20,
              attr=f"{_ACTION}.max_interactions"),
        Field("minLikesPerProfile", "int", "Fewest posts liked on a profile.", default=1,
              attr=f"{_ACTION}.min_likes_per_profile"),
        Field("maxLikesPerProfile", "int", "Most posts liked on a profile.", default=2,
              attr=f"{_ACTION}.max_likes_per_profile"),
        Field("maxFeedStoryProfiles", "int", "Story authors of the feed to watch, when `feedStories` omits it.",
              default=5, attr=f"{_ACTION}.max_feed_story_profiles", when=_FEED),
    ),
)

PROBABILITIES = Shape(
    name="InstagramAutomationProbabilities",
    doc="Chances of each action on a profile, in percent; decision mode replaces them with its plan.",
    fields=(
        Field("like", "number", "Like its posts.", default=80, attr=f"{_ACTION}.probabilities.like_percentage"),
        Field("follow", "number", "Follow it.", default=20, attr=f"{_ACTION}.probabilities.follow_percentage"),
        Field("comment", "number", "Comment a post.", default=5, attr=f"{_ACTION}.probabilities.comment_percentage"),
        Field("watchStories", "number", "Watch its stories.", default=15,
              attr=f"{_ACTION}.probabilities.story_percentage"),
        Field("likeStories", "number", "Like a story.", default=10,
              attr=f"{_ACTION}.probabilities.story_like_percentage"),
        Field("feedStoryReaction", "number", "React to a story of the feed.", default=0,
              attr=f"{_ACTION}.feed_story_reaction_percentage", when=_FEED),
    ),
)

FILTERS = Shape(
    name="InstagramAutomationFilters",
    doc="Which profiles deserve an interaction.",
    fields=(
        Field("minFollowers", "int", "Fewest followers.", default=50, attr=f"{_ACTION}.min_followers"),
        Field("maxFollowers", "int", "Most followers; 0: no limit.", default=50000, attr=f"{_ACTION}.max_followers"),
        Field("minPosts", "int", "Fewest posts.", default=5, attr=f"{_ACTION}.min_posts"),
        Field("maxFollowing", "int", "Most accounts followed; 0: no limit.", default=7500,
              attr=f"{_ACTION}.max_following"),
        Field("skipFollowsUs", "bool", "Leave profiles that follow the account.", default=False,
              attr=f"{_ACTION}.skip_follows_us"),
        Field("skipAlreadyFollowing", "bool", "Leave profiles the account follows.", default=False,
              attr=f"{_ACTION}.skip_already_following"),
        Field("reinteractionDays", "int", "Days before interacting again with a profile; 0: never. Absent: the bot's.",
              attr=f"{_ACTION}.reinteraction_days"),
        Field("refilterDays", "int", "Days before filtering a refused profile again; 0: never. Absent: the bot's.",
              attr=f"{_ACTION}.refilter_days"),
        Field("allowPrivate", "bool", "Accept private profiles.", default=False, attr=f"{_ACTION}.allow_private"),
        Field("maxConsecutivePrivateProfiles", "int", "Private profiles in a row before leaving the zone. Absent: the bot's.",
              attr=f"{_ACTION}.max_consecutive_private_profiles"),
        Field("allowVerified", "bool", "Accept verified accounts.", default=True, attr=f"{_ACTION}.allow_verified"),
        Field("allowBusiness", "bool", "Accept professional accounts.", default=True, attr=f"{_ACTION}.allow_business"),
        Field("minPostLikes", "int", "Fewest likes of a feed post worth engaging; 0: no bound.", default=0,
              attr=f"{_ACTION}.min_post_likes", when=_FEED),
        Field("maxPostLikes", "int", "Most likes of a feed post worth engaging; 0: no bound.", default=0,
              attr=f"{_ACTION}.max_post_likes", when=_FEED),
    ),
)

SESSION = Shape(
    name="InstagramAutomationSession",
    doc="How long the run lasts and when it gives up on a source.",
    fields=(
        Field("durationMinutes", "int", "Stop after this many minutes.", default=60,
              attr="session_settings.session_duration_minutes"),
        Field("minDelay", "number", "Shortest pause between actions, in seconds. Absent: the pacing profile's.",
              attr="session_settings.delay_between_actions.min"),
        Field("maxDelay", "number", "Longest pause between actions, in seconds. Absent: the pacing profile's.",
              attr="session_settings.delay_between_actions.max"),
        Field("maxConsecutiveKnownUsernames", "int", "Known usernames in a row before leaving a source list.",
              attr="session_settings.max_consecutive_known_usernames"),
        Field("maxNoNewUsernamesScrolls", "int", "Scrolls without a new username before leaving a source list.",
              attr="session_settings.max_no_new_usernames_scrolls"),
    ),
)

COMMENTS = Shape(
    name="InstagramAutomationComments",
    doc="Comments written by the operator.",
    fields=(
        Field("customComments", ListOf("string"), "Comments to pick from; empty when the AI writes them.", default=(),
              attr=f"{_ACTION}.comment_settings.custom_comments"),
    ),
)

FEED_STORIES = Shape(
    name="InstagramAutomationFeedStories",
    doc="The stories of the feed (feed).",
    fields=(
        Field("enabled", "bool", "Watch them.", default=Computed("on when probabilities.watchStories is above 0"),
              attr=f"{_ACTION}.view_feed_stories"),
        Field("maxProfiles", "int", "Story authors to watch.", default=5, attr=f"{_ACTION}.max_feed_story_profiles"),
        Field("reaction", "string", "The quick reaction sent.", default="laugh", attr=f"{_ACTION}.feed_story_reaction"),
    ),
)

FEED = Shape(
    name="InstagramAutomationFeed",
    doc="How the feed is walked (feed).",
    fields=(
        Field("skipSuggested", "bool", "Scroll past suggested posts.", default=True, attr=f"{_ACTION}.skip_suggested"),
        Field("readCaptions", "bool", "Open long captions.", default=True, attr=f"{_ACTION}.read_captions"),
        Field("browseCarousels", "bool", "Swipe through carousels.", default=True, attr=f"{_ACTION}.browse_carousels"),
        Field("captureAds", "bool", "Record the sponsored posts crossed; none is opened.", default=False,
              attr=f"{_ACTION}.capture_ads"),
        Field("interactWithPostAuthor", "bool", "Visit the author of an engaged post.", default=False,
              attr=f"{_ACTION}.interact_with_post_author"),
        Field("interactWithPostLikers", "bool", "Walk the likers of an engaged post.", default=False,
              attr=f"{_ACTION}.interact_with_post_likers"),
        Field("maxLikersPerPost", "int", "Likers walked per post.", default=5, attr=f"{_ACTION}.max_likers_per_post"),
        Field("skipReels", "bool", "Leave the reels of the feed.", default=False, attr=f"{_ACTION}.skip_reels"),
        Field("followSuggestions", "bool", "Follow from the suggestions carousel when it shows.", default=False,
              attr=f"{_ACTION}.follow_suggestions"),
        Field("suggestionsOnly", "bool", "Only the carousel: no like, comment or story.", default=False,
              attr=f"{_ACTION}.suggestions_only"),
        Field("maxCarouselScrolls", "int", "Scrolls to find the carousel.", default=12,
              attr=f"{_ACTION}.max_carousel_scrolls"),
        Field("maxSuggestionFollows", "int", "Follows per pass of suggestions.", default=20,
              attr=f"{_ACTION}.max_suggestion_follows"),
        Field("allowContactsAccess", "bool", "Grant the contacts access Instagram asks for; refused otherwise.",
              default=False, via=_BUILDER),
        Field("maxSuggestionPasses", "int", "Passes of suggestions.", default=1, attr=f"{_ACTION}.max_suggestion_passes"),
    ),
)

UNFOLLOW = Shape(
    name="InstagramAutomationUnfollow",
    doc="Who to unfollow and how fast (unfollow).",
    fields=(
        Field("maxUnfollows", "int", "Stop after this many unfollows.", default=Computed("limits.maxProfiles"),
              attr=f"{_ACTION}.max_unfollows"),
        Field("unfollowMode", OneOf(("non-followers", "mutual", "oldest", "all")), "Which accounts.",
              default="non-followers", attr=f"{_ACTION}.unfollow_mode"),
        Field("minDelay", "number", "Shortest pause between two unfollows, in seconds.", default=2,
              attr=f"{_ACTION}.min_delay"),
        Field("maxDelay", "number", "Longest pause between two unfollows, in seconds.", default=5,
              attr=f"{_ACTION}.max_delay"),
        Field("skipVerified", "bool", "Keep verified accounts.", default=True, attr=f"{_ACTION}.skip_verified"),
        Field("skipBusiness", "bool", "Keep professional accounts.", default=False, attr=f"{_ACTION}.skip_business"),
        Field("minDaysSinceFollow", "int", "Keep accounts followed fewer days ago.", default=3,
              attr=f"{_ACTION}.min_days_since_follow"),
        Field("botFollowsOnly", "bool", "Only accounts the bot followed; manual follows are kept.", default=True,
              attr=f"{_ACTION}.bot_follows_only"),
        Field("whitelist", ListOf("string"), "Never unfollowed.", default=(), attr=f"{_ACTION}.whitelist"),
        Field("blacklist", ListOf("string"), "Unfollowed first.", default=(), attr=f"{_ACTION}.blacklist"),
    ),
)

SYNC = Shape(
    name="InstagramAutomationSync",
    doc="The two-list synchronisation (sync_followers_following).",
    fields=(
        Field("mode", OneOf(("fast", "enriched")), "Usernames only, or each profile opened.", default="fast",
              attr=f"{_ACTION}.mode"),
    ),
)

POST_CRITERIA = Shape(
    name="InstagramAutomationPostCriteria",
    doc="Which post of a hashtag is worth opening. Absent: the workflow's own bounds.",
    fields=(
        Field("minLikes", "int", "Fewest likes; 0: no bound.", attr=f"{_ACTION}.post_criteria.min_likes"),
        Field("maxLikes", "int", "Most likes; 0: no bound.", attr=f"{_ACTION}.post_criteria.max_likes"),
    ),
)

BEHAVIOR_POLICY = Shape(
    name="InstagramAutomationBehaviorPolicy",
    doc="The pacing profile: the rhythm when no explicit delay is set.",
    fields=(
        Field("profileId", OneOf(("natural", "strict_test", "balanced", "careful", "slow_reader", "fast", "fast_debug")),
              "The profile; an unknown one is natural."),
    ),
)

WARMUP_POLICY = Shape(
    name="InstagramAutomationWarmupPolicy",
    doc="The warmup caps the desktop computes from the account's age; 0 or absent: no cap.",
    fields=(
        Field("maxActionsPerDay", "int", "Actions per day.", attr="session_settings.warmup_policy.max_actions_per_day"),
        Field("maxFollowsPerDay", "int", "Follows per day.", attr="session_settings.warmup_policy.max_follows_per_day"),
        Field("maxCommentsPerDay", "int", "Comments per day.",
              attr="session_settings.warmup_policy.max_comments_per_day"),
        Field("maxUnfollowsPerDay", "int", "Unfollows per day, a budget of their own.",
              attr="session_settings.warmup_policy.max_unfollows_per_day"),
        Field("minActionGapSeconds", "number", "Shortest gap between two actions, in seconds.",
              attr="session_settings.warmup_policy.min_action_gap_seconds"),
        Field("maxActionsPerSession", "int", "Actions in this run.",
              attr="session_settings.warmup_policy.max_actions_per_session"),
    ),
)

DECISION_CAPABILITIES = Shape(
    name="InstagramAutomationAiDecisionCapabilities",
    doc="What the per-profile plans may do; absent: not allowed.",
    fields=tuple(
        Field(key, "bool", doc, attr=f"{_ACTION}.ai_decision_capabilities.{key}")
        for key, doc in (
            ("like", "Like posts."),
            ("follow", "Follow."),
            ("comment", "Comment."),
            ("watchStories", "Watch stories."),
            ("likeStories", "Like stories."),
        )
    ),
)

DECISION = Shape(
    name="InstagramAutomationAiDecision",
    doc="Decision mode: the desktop plans each profile, the bot executes the plan.",
    fields=(
        Field("mode", OneOf(("off", "enrich", "decide")), "`decide` hands every profile to the desktop's plan.",
              via=_BUILDER),
        Field("dryRun", "bool", "Narrate the plans without executing any.", default=True,
              attr=f"{_ACTION}.ai_decision_dry_run", when=_DECIDE),
        Field("capabilities", DECISION_CAPABILITIES, "What the plans may do.", when=_DECIDE),
    ),
)

RELEVANCE_GATING = Shape(
    name="InstagramAutomationRelevanceGating",
    doc="Skip the profiles the AI verdict judges irrelevant, or drop their actions.",
    fields=(
        Field("enabled", "bool", "Enforce the verdict; otherwise it is only shown."),
        Field("minScore", "number", "Lowest relevance score kept."),
        Field("maskIntents", "bool", "Drop the actions the verdict refuses rather than the profile."),
        Field("dryRun", "bool", "Report what would be skipped, skip nothing."),
    ),
)

ACCOUNT_PERSONA = Shape(
    name="InstagramAccountPersona",
    doc="The operated account as its profile describes it; what the AI writes and judges against.",
    fields=(
        Field("displayName", "string", "Its name."),
        Field("niche", "string", "Its niche."),
        Field("productService", "string", "What it sells."),
        Field("objective", "string", "What it wants."),
        Field("targetAudience", "string", "Who it talks to."),
        Field("tonePersonality", "string", "Its voice."),
        Field("uniqueSellingPoint", "string", "What sets it apart."),
        Field("customContext", "string", "Free context."),
        Field("language", "string", "The language it writes in."),
        Field("writingStyleSamples", ListOf("string"), "Messages it wrote, for its voice."),
    ),
)

AI = Shape(
    name="InstagramAutomationAi",
    doc="The AI of the run: comments, profile and post analysis, decision mode.",
    fields=(
        Field("enabled", "bool", "AI mode; without a key the run goes on without AI.", default=False, via=_AI_SERVICE),
        Field("smartComments", "bool", "The AI writes the comments.", default=False, via=_AI_HOOKS),
        Field("profileAnalysis", "bool", "The AI judges each profile before the interaction.", default=False,
              via=_AI_HOOKS),
        Field("postAnalysis", "bool", "The AI reads each post before the like.", default=False, via=_AI_HOOKS),
        Field("relevanceGating", RELEVANCE_GATING, "Act on the profile verdict.", aliases=("relevance_gating",),
              via=_AI_HOOKS),
        Field("decision", DECISION, "Decision mode."),
        Field("accountNiche", "string", "The operated account's niche; injected by the host.",
              aliases=("account_niche",), via=_AI_HOOKS, by=HOST),
        Field("accountSubNiche", "string", "The operated account's sub-niche.", aliases=("account_sub_niche",),
              via=_AI_HOOKS, app=False),
        Field("accountProfile", ACCOUNT_PERSONA, "The operated account's persona; injected by the host.",
              via=_AI_HOOKS, by=HOST),
        Field("openrouterApiKey", "string", "The key the AI calls with; injected by the host.", via=_AI_SERVICE, by=HOST),
        Field("visionModel", "string", "The model that reads screenshots; injected by the host.", via=_AI_SERVICE,
              by=HOST),
        Field("textModel", "string", "The model that writes.", via=_AI_SERVICE, app=False),
        Field("nicheTaxonomy", MapOf(ListOf("string")), "Category -> sub-niche labels, the premium taxonomy; injected by the host.",
              aliases=("niche_taxonomy",), via=_AI_SERVICE, by=HOST),
    ),
)


# ------------------------------------------------------------------------------------ lines

SESSION_CONFIG_ECHO = Shape(
    name="InstagramAutomationSessionConfigEcho",
    doc="`build_instagram_session_config_event`: the run's settings as the bot read them, for display.",
    fields=(
        Field("deviceId", "string", "The phone.", nullable=True),
        Field("workflowType", "string", "The workflow.", nullable=True),
        Field("target", "string", "The targets, comma-joined.", nullable=True),
        Field("limits", Shape(name="InstagramAutomationLimitsEcho", fields=(
            Field("maxProfiles", "number", "Profiles to interact with."),
            Field("maxLikesPerProfile", "number", "Most posts liked on a profile."),
        )), "The budget."),
        Field("probabilities", Shape(name="InstagramAutomationProbabilitiesEcho", fields=(
            Field("like", "number", "Like, in percent."),
            Field("follow", "number", "Follow, in percent."),
            Field("comment", "number", "Comment, in percent."),
            Field("watchStories", "number", "Watch stories, in percent."),
            Field("likeStories", "number", "Like a story, in percent."),
        )), "Chances of each action."),
        Field("filters", Shape(name="InstagramAutomationFiltersEcho", fields=(
            Field("minFollowers", "number", "Fewest followers."),
            Field("maxFollowers", "number", "Most followers."),
            Field("minPosts", "number", "Fewest posts."),
            Field("maxFollowing", "number", "Most accounts followed."),
        )), "Profile filters."),
        Field("session", Shape(name="InstagramAutomationSessionEcho", fields=(
            Field("durationMinutes", "number", "Minutes."),
            Field("minDelay", "number", "Explicit shortest pause; absent when the pacing profile rules.",
                  optional=True),
            Field("maxDelay", "number", "Explicit longest pause.", optional=True),
            Field("maxConsecutiveKnownUsernames", "number", "Known usernames before leaving a source.",
                  optional=True),
            Field("maxNoNewUsernamesScrolls", "number", "Scrolls without news before leaving a source.",
                  optional=True),
        )), "Duration and pauses."),
        Field("behaviorPolicy", "json", "The pacing profile, as sent.", optional=True),
        Field("ai", Shape(name="InstagramAutomationAiEcho", fields=(
            Field("enabled", "bool", "AI mode."),
            Field("smartComments", "bool", "The AI writes the comments."),
            Field("profileAnalysis", "bool", "The AI judges each profile."),
            Field("postAnalysis", "bool", "The AI reads each post."),
            Field("relevanceGating", "json", "Acting on the verdict, as sent.", optional=True),
            Field("decision", "json", "Decision mode, as sent.", optional=True),
        )), "The AI modes; only when the AI service is on.", optional=True),
    ),
)

RUN_STATS = Shape(
    name="InstagramAutomationRunStats",
    doc="`BaseStatsManager`'s counters, after each change.",
    fields=tuple(Field(key, "int", doc) for key, doc in (
        ("profiles_visited", "Profiles opened."),
        ("profiles_interacted", "Profiles acted on."),
        ("profiles_filtered", "Profiles refused by a filter."),
        ("private_profiles", "Private profiles met."),
        ("likes", "Likes."),
        ("follows", "Follows."),
        ("comments", "Comments."),
        ("stories_watched", "Stories watched."),
        ("story_likes", "Stories liked."),
        ("errors", "Errors."),
        ("posts_engaged", "Posts engaged without opening a profile (feed, hashtag posts)."),
    )),
)

DECISION_ENGAGEMENT = Shape(
    name="InstagramAgentDecisionEngagement",
    doc="The AI verdict on the profile.",
    fields=(
        Field("relevant", "bool", "Relevant to the account."),
        Field("score", "number", "Relevance score.", nullable=True),
        Field("reason", "string", "Why.", nullable=True),
        Field("relevanceTier", "string", "`direct`, `adjacent`, `weak`, `none`.", nullable=True),
        Field("evidence", "string", "What it saw.", nullable=True),
        Field("like", "bool", "Worth a like."),
        Field("follow", "bool", "Worth a follow."),
        Field("comment", "bool", "Worth a comment."),
    ),
)

DECISION_PROFILE = Shape(
    name="InstagramAgentDecisionProfile",
    doc="What the profile shows.",
    fields=(
        Field("followersCount", "int", "Followers."),
        Field("followingCount", "int", "Accounts followed."),
        Field("postsCount", "int", "Posts."),
        Field("followButtonState", "string", "The follow button as read.", nullable=True),
        Field("relationship", "string", "Its relation to the account.", nullable=True),
        Field("niche", "string", "Its niche.", nullable=True),
        Field("nicheCategory", "string", "Its niche category.", nullable=True),
    ),
)

DECISION_BUDGET = Shape(
    name="InstagramAgentDecisionBudget",
    doc="What the account spent and may spend.",
    fields=(
        Field("daily", Shape(name="InstagramAgentDecisionDailyUsage", fields=(
            Field("total", "int", "Actions today."),
            Field("follows", "int", "Follows today."),
            Field("comments", "int", "Comments today."),
        )), "Today."),
        Field("session", Shape(name="InstagramAgentDecisionSessionUsage", fields=(
            Field("total", "int", "Actions this run."),
            Field("likes", "int", "Likes this run."),
            Field("follows", "int", "Follows this run."),
            Field("comments", "int", "Comments this run."),
        )), "This run."),
        Field("caps", Shape(name="InstagramAgentDecisionCaps", fields=(
            Field("maxActionsPerDay", "int", "Actions per day; 0: no cap."),
            Field("maxFollowsPerDay", "int", "Follows per day."),
            Field("maxCommentsPerDay", "int", "Comments per day."),
            Field("maxActionsPerSession", "int", "Actions per run."),
        )), "The warmup caps."),
    ),
)

DECISION_LIMITS = Shape(
    name="InstagramAgentDecisionLimits",
    doc="The run's per-profile limits.",
    fields=tuple(Field(key, "int", doc) for key, doc in (
        ("maxLikesPerProfile", "Most likes."),
        ("minLikesPerProfile", "Fewest likes."),
        ("maxCommentsPerProfile", "Most comments."),
        ("maxStoriesPerProfile", "Most stories watched."),
        ("maxStoryLikesPerProfile", "Most stories liked."),
    )),
)

ACTION_PROFILE = Shape(
    name="InstagramActionProfileData",
    doc="A profile's counters, as read before the action (`InteractionEngineMixin._emit_*_event`).",
    fields=(
        Field("followers_count", "int", "Its followers."),
        Field("following_count", "int", "The accounts it follows."),
        Field("posts_count", "int", "Its posts."),
    ),
)

_SOURCE_WORKFLOWS = OneOf(("target", "hashtag", "post_url"))
_SYNC_LIST = OneOf(("following", "followers"))

EVENTS = (
    STATUS_EVENT,
    ERROR_EVENT,
    LOG_EVENT,
    NETWORK_RESET_COMPLETE_EVENT,
    Event("session_config", doc="The run's settings as the bot read them.", fields=(
        Field("config", SESSION_CONFIG_ECHO, "The echo."),
    )),
    Event("session_start", doc="The run's `sessions` row.", fields=(
        Field("session_id", "int", "Its id."),
    )),
    Event("active_account", doc="The account the run acts as, read on its profile.", fields=(
        Field("username", "string", "Its handle."),
        Field("followers", "int", "Its followers."),
        Field("following", "int", "The accounts it follows."),
        Field("posts", "int", "Its posts."),
    )),
    Event("target_account", doc="A target account about to be worked.", fields=(
        Field("username", "string", "Its handle."),
        Field("followers", "int", "Its followers."),
        Field("following", "int", "The accounts it follows."),
        Field("posts", "int", "Its posts."),
    )),
    Event("source_progress", doc="A target, hashtag or post URL of a run with several: started or done.", fields=(
        Field("workflow", _SOURCE_WORKFLOWS, "The kind of source."),
        Field("source", "string", "The source."),
        Field("index", "int", "Its rank, from 1."),
        Field("total", "int", "Sources of the run."),
        Field("quota", "int", "Its share of the budget."),
        Field("processed", "int", "Profiles worked so far (`running`: in the run; `done`: in it)."),
        Field("status", OneOf(("running", "done")), "Where it is."),
        Field("failure_code", "string", "Why it could not be worked (`done`).", optional=True),
    )),
    Event("session_stop", doc="The run is over, and why.", fields=(
        Field("status", "string", "COMPLETED, INTERRUPTED, ERROR..."),
        Field("reason", "string", "Why, as an English sentence."),
        Field("duration_seconds", "int", "How long it ran."),
        Field("reason_code", "string", "Why, as a code the app translates.", optional=True),
        Field("reason_params", MapOf("json"), "The code's parameters.", optional=True),
        Field("screenshot", "string", "The last screen, a file.", optional=True),
        Field("hierarchy", "string", "The last screen's tree, a file.", optional=True),
    )),
    Event("stats", doc="The run's final counters (`run_instagram_automation`), or the unfollows so far.", fields=(
        Field("likes", "int", "Likes."),
        Field("follows", "int", "Follows."),
        Field("comments", "int", "Comments."),
        Field("profiles", "int", "Profiles acted on."),
        Field("unfollows", "int", "Unfollows."),
    )),
    Event("instagram_stats", doc="The live counters.", fields=(
        Field("stats", RUN_STATS, "The counters."),
    )),
    Event("instagram_profile_visit", doc="A profile opened.", fields=(
        Field("username", "string", "Its handle."),
        Field("followers", "int", "Its followers, if read.", nullable=True),
        Field("is_private", "bool", "A private account."),
    )),
    Event("profile_captured", doc="A profile read: its counters, bio, picture.", fields=(
        Field("username", "string", "Its handle."),
        Field("full_name", "string", "Its name.", optional=True, nullable=True),
        Field("follower_count", "int", "Its followers.", optional=True),
        Field("following_count", "int", "The accounts it follows.", optional=True),
        Field("media_count", "int", "Its posts.", optional=True),
        Field("is_private", "bool", "A private account.", optional=True),
        Field("is_verified", "bool", "A verified account.", optional=True),
        Field("is_business", "bool", "A business account (media capture).", optional=True),
        Field("biography", "string", "Its bio.", optional=True, nullable=True),
        Field("profile_pic_url", "string", "Its picture: a data URL, or a link (media capture).",
              optional=True, nullable=True),
        Field("profile_pic_url_hd", "string", "Its large picture (media capture).", optional=True, nullable=True),
        Field("external_url", "string", "Its link (media capture).", optional=True, nullable=True),
        Field("category", "string", "Its category (media capture).", optional=True, nullable=True),
        Field("captured_at", "string", "When, ISO 8601 (media capture).", optional=True),
    )),
    Event("media_captured", doc="A post the app loaded (media capture).", fields=(
        Field("media_id", "string", "Its id."),
        Field("media_type", "string", "photo, video, carousel."),
        Field("image_url", "string", "Its picture."),
        Field("like_count", "int", "Its likes."),
        Field("comment_count", "int", "Its comments."),
        Field("caption", "string", "Its caption, cut."),
        Field("username", "string", "Its author.", nullable=True),
        Field("width", "int", "Width.", optional=True),
        Field("height", "int", "Height.", optional=True),
        Field("taken_at", "int", "When it was posted.", optional=True, nullable=True),
        Field("captured_at", "string", "When it was captured, ISO 8601.", optional=True),
    )),
    Event("profile_skipped", doc="A profile left out: known already, filtered, unreachable.", fields=(
        Field("username", "string", "Its handle."),
        Field("reason", "string", "Why, as a code the app translates or a filter's words."),
        Field("detail", "string", "A hint appended to the reason.", nullable=True),
    )),
    Event("instagram_action", doc="Something the run did or saw on a profile (`IPCEmitter.emit_action`).", fields=(
        Field("action", "string", "What: `like`, `follow`, `comment`, `greeting`..."),
        Field("username", "string", "On whom."),
        Field("details", "json", "What goes with it.", optional=True),
    )),
    Event("follow_event", doc="A follow.", fields=(
        Field("username", "string", "Who."),
        Field("success", "bool", "It took."),
        Field("profile_data", ACTION_PROFILE, "The profile's counters, when it was read.", optional=True),
    )),
    Event("like_event", doc="Likes on a profile.", fields=(
        Field("username", "string", "Whose posts."),
        Field("likes_count", "int", "How many."),
        Field("profile_data", ACTION_PROFILE, "The profile's counters, when it was read.", optional=True),
    )),
    Event("story_event", doc="Stories watched, and liked.", fields=(
        Field("username", "string", "Whose."),
        Field("stories_watched", "int", "Watched."),
        Field("stories_liked", "int", "Liked."),
        Field("profile_data", ACTION_PROFILE, "The profile's counters, when it was read.", optional=True),
    )),
    Event("current_post", doc="The hashtag post being worked.", fields=(
        Field("author", "string", "Its author."),
        Field("likes_count", "int", "Its likes.", nullable=True),
        Field("comments_count", "int", "Its comments.", nullable=True),
        Field("caption", "string", "Its caption, cut.", nullable=True),
        Field("hashtag", "string", "The hashtag.", nullable=True),
    )),
    Event("post_skipped", doc="A hashtag post left out.", fields=(
        Field("author", "string", "Its author."),
        Field("reason", "string", "Why."),
        Field("hashtag", "string", "The hashtag.", nullable=True),
    )),
    Event("agent_decision", doc="A feed post judged: liked, commented or left (feed card).", fields=(
        Field("action", "string", "`like`, `like_comment`, `skip`."),
        Field("target_username", "string", "The post's author.", nullable=True),
        Field("reason", "string", "Why.", nullable=True),
        Field("visit_profile", "bool", "The author will be visited."),
        Field("workflow_type", "string", "The family of the card."),
        Field("comment", "string", "The comment written.", optional=True),
        Field("screenshot", "string", "The post.", optional=True),
        Field("cost_usd", "number", "What the call cost.", optional=True),
        Field("model", "string", "The model.", optional=True),
    )),
    Event("agent_profile_decision_request", doc="Decision mode: the facts of one profile, for the desktop's plan.",
          fields=(
              Field("requestId", "string", "Pairs it with the answer on stdin."),
              Field("username", "string", "The profile."),
              Field("engagement", DECISION_ENGAGEMENT, "The AI verdict."),
              Field("profile", DECISION_PROFILE, "The profile."),
              Field("budget", DECISION_BUDGET, "Budgets."),
              Field("limits", DECISION_LIMITS, "Per-profile limits."),
          )),
    Event("unfollow_event", doc="An unfollow.", fields=(
        Field("username", "string", "Who."),
        Field("success", "bool", "It took."),
    )),
    Event("unfollow_plan", doc="The unfollow run's candidates, decided on data before the first tap.", fields=(
        Field("mode", "string", "The mode."),
        Field("candidates", "int", "Accounts it will unfollow at most."),
        Field("refusals", MapOf("int"), "Rule -> accounts kept for it."),
    )),
    Event("sync_step", doc="A list of the two-list sync, started or done.", fields=(
        Field("step", _SYNC_LIST, "The list."),
        Field("status", OneOf(("started", "completed")), "Where it is."),
        Field("new_count", "int", "Accounts new to the base (`completed`).", optional=True),
        Field("updated_count", "int", "Accounts updated (`completed`).", optional=True),
        Field("total_seen", "int", "Accounts read (`completed`, followers).", optional=True),
    )),
    Event("sync_progress", doc="A list being read.", fields=(
        Field("list_type", _SYNC_LIST, "The list."),
        Field("new_count", "int", "New so far."),
        Field("updated_count", "int", "Updated so far."),
        Field("total_seen", "int", "Read so far."),
    )),
    Event("sync_user_discovered", doc="An account read in a list.", fields=(
        Field("list_type", _SYNC_LIST, "The list."),
        Field("username", "string", "Its handle."),
        Field("display_name", "string", "Its name."),
        Field("is_new", "bool", "New to the base."),
    )),
    Event("sync_complete", doc="The sync is over.", fields=(
        Field("non_followers_count", "int", "Followed accounts that do not follow back."),
        Field("mutuals_count", "int", "Mutual follows."),
        Field("success", "bool", "Every list was read."),
        Field("new_count", "int", "New followed accounts (`sync_following`).", optional=True),
        Field("updated_count", "int", "Updated followed accounts (`sync_following`).", optional=True),
        Field("following", Shape(name="InstagramSyncListCounts", fields=(
            Field("new_count", "int", "New."),
            Field("updated_count", "int", "Updated."),
            Field("total_seen", "int", "Read.", optional=True),
        )), "The followed list (`sync_followers_following`).", optional=True),
        Field("followers", Shape(name="InstagramSyncListCounts", fields=(
            Field("new_count", "int", "New."),
            Field("updated_count", "int", "Updated."),
            Field("total_seen", "int", "Read.", optional=True),
        )), "The followers list (`sync_followers_following`).", optional=True),
    )),
    Event("step_metric", doc="One atomic gesture or decision (`emit_step`), for the step telemetry.", fields=(
        Field("category", "string", "`tap`, `scroll`, `keystroke`, `follower_decision`..."),
        Field("action", "string", "A finer label.", nullable=True),
        Field("target", "string", "What it acted on.", nullable=True),
        Field("detail", "json", "Its structured payload."),
        Field("ts", "number", "When, epoch seconds."),
    )),
    *AI_EVENTS,
)

INSTAGRAM_AUTOMATION = WorkflowContract(
    workflow_id=f"instagram.automation.{WORKFLOW_TYPES[0]}",
    also=tuple(f"instagram.automation.{workflow_type}" for workflow_type in WORKFLOW_TYPES[1:]),
    selector="workflowType",
    name="InstagramAutomation",
    bridge="desktop_bridge",
    doc="An Instagram automation run: targets, hashtags, post URLs, feed, unfollow, list sync.",
    launcher=_LAUNCHER,
    reader=_BUILDER,
    settings=(
        Field("workflowType", OneOf(WORKFLOW_TYPES), "The workflow of the run.", required=True, via=_BUILDER),
        Field("target", "string", "Accounts, hashtags or post URLs, comma-joined; the workflow's name when it "
              "acts on the account itself.", required=True, attr=f"{_ACTION}.target_username"),
        Field("distribution", OneOf(("balanced", "sequential", "interleaved")),
              "How the budget is split across several targets.", default="balanced", attr=f"{_ACTION}.distribution"),
        Field("limits", LIMITS, "The run's budget."),
        Field("probabilities", PROBABILITIES, "Chances of each action."),
        Field("filters", FILTERS, "Profile filters."),
        Field("session", SESSION, "Duration and source exhaustion."),
        Field("comments", COMMENTS, "Written comments."),
        Field("feedStories", FEED_STORIES, "Stories of the feed.", when=_FEED),
        Field("feed", FEED, "The feed walk.", when=_FEED),
        Field("unfollow", UNFOLLOW, "The unfollow run.", when=_UNFOLLOW),
        Field("sync", SYNC, "The two-list sync.", when={"workflowType": "sync_followers_following"}),
        Field("postCriteria", POST_CRITERIA, "Hashtag: which posts to open."),
        Field("interactionMode", "string", "Hashtag: the older one-choice plan (`likers`, `posts`...).",
              attr=f"{_ACTION}.interaction_mode"),
        Field("engagePosts", "bool", "Hashtag: engage each post itself.", attr=f"{_ACTION}.engage_posts"),
        Field("walkLikers", "bool", "Hashtag: walk each post's likers.", attr=f"{_ACTION}.walk_likers"),
        Field("walkCommenters", "bool", "Hashtag: walk each post's commenters.", attr=f"{_ACTION}.walk_commenters"),
        Field("maxPosts", "int", "Hashtag: posts to open.", attr=f"{_ACTION}.max_posts"),
        Field("maxLikersPerPost", "int", "Hashtag: likers walked per post.", attr=f"{_ACTION}.max_likers_per_post"),
        Field("maxCommentersPerPost", "int", "Hashtag: commenters walked per post.",
              attr=f"{_ACTION}.max_commenters_per_post"),
        Field("source_mode", OneOf(("likers", "commenters")), "Post URL: the population walked.",
              attr=f"{_ACTION}.source_mode"),
        Field("like_comments", "bool", "Post URL: like comments of the thread.", attr=f"{_ACTION}.like_comments"),
        Field("reply_to_comments", "bool", "Post URL: reply to comments of the thread.",
              attr=f"{_ACTION}.reply_to_comments"),
        Field("max_comment_likes", "int", "Post URL: comments liked.", attr=f"{_ACTION}.max_comment_likes"),
        Field("max_comment_replies", "int", "Post URL: comments answered.", attr=f"{_ACTION}.max_comment_replies"),
        Field("walk_profiles", "bool", "Post URL: false stays in the thread and visits nobody.",
              attr=f"{_ACTION}.walk_profiles"),
        Field("behaviorPolicy", BEHAVIOR_POLICY, "The pacing profile.", via=_PACING),
        Field("warmupPolicy", WARMUP_POLICY, "The warmup caps; injected by the host.", by=HOST),
        Field("language", "string", "The language the AI writes its content in.", default="en", via=_AI_HOOKS),
        Field("packageName", "string", "The Instagram app to run (a clone). Absent: the installed Instagram.",
              via=_LAUNCHER),
        Field("ai", AI, "The AI of the run."),
    ),
    bridge_fields=(
        device_field("deviceId"),
        network_reset_field(),
        Field("mediaCaptureEnabled", "bool", "Capture the profiles and media the app loads.", default=False),
    ),
    events=EVENTS,
)

CONTRACTS = (INSTAGRAM_AUTOMATION,)

__all__ = ["CONTRACTS", "INSTAGRAM_AUTOMATION", "WORKFLOW_TYPES"]
