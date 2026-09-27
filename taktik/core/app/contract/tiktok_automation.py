"""TikTok workflows of the `tiktok_bridge` dispatcher, first half: the video workflows.

For You (`tiktok.automation.for_you`) and the search (`search`, and `hashtag` and `target`, the same
launcher): one payload, the settings every video workflow shares (`_internal/video_payload.py`),
the workflow's own, the AI block and the app language. The profile-visiting workflows (followers,
target profiles, post URL), the follow-graph sync and the inbox are not declared yet.
"""

from __future__ import annotations

from .schema import HOST, Event, Field, ListOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import ERROR_EVENT, STATUS_EVENT, network_reset_field
from .tiktok_lines import AI_PROFILE_DONE_EVENT, BOT_PROFILE_EVENT

_WORKFLOWS = "taktik.core.social_media.tiktok.actions.business.workflows"
_AI_HOOKS = "taktik.core.social_media.tiktok.workflows.core.ai_hooks"
_VIDEO_READER = f"{_WORKFLOWS}._internal.video_payload:video_settings_from_payload"
_QUERIES_READER = f"{_WORKFLOWS}.search.payload:search_queries_from_payload"


def _percent(key: str, snake: str, doc: str, default: float) -> Field:
    return Field(key, "number", f"{doc}, in percent (a snake_case name takes a fraction, or a percent above 1).",
                 default=default, aliases=(snake,), attr=snake, unit="percent")


#: What every video workflow reads (`video_settings_from_payload`), with the same defaults.
VIDEO_SETTINGS = (
    Field("maxVideos", "int", "Videos to watch in the run.", default=50, aliases=("max_videos",), attr="max_videos"),
    Field("minWatchTime", "number", "Shortest watch of a video, in seconds.", default=2.0,
          aliases=("min_watch_time",), attr="min_watch_time"),
    Field("maxWatchTime", "number", "Longest watch of a video, in seconds.", default=8.0,
          aliases=("max_watch_time",), attr="max_watch_time"),
    _percent("likeProbability", "like_probability", "Chance to like a video", 30),
    _percent("followProbability", "follow_probability", "Chance to follow its author", 10),
    _percent("favoriteProbability", "favorite_probability", "Chance to add it to favorites", 5),
    _percent("commentProbability", "comment_probability", "Chance to comment on it", 0),
    Field("maxCommentsPerSession", "int", "Comments in the run.", default=10,
          aliases=("max_comments_per_session",), attr="max_comments_per_session"),
    _percent("repostProbability", "repost_probability", "Chance to repost it", 0),
    Field("maxRepostsPerSession", "int", "Reposts in the run.", default=5,
          aliases=("max_reposts_per_session",), attr="max_reposts_per_session"),
    Field("commentTexts", ListOf("string"), "Comments to pick from, kept as written.", default=(),
          aliases=("comments", "comment_texts"), attr="comment_texts"),
    Field("requiredHashtags", ListOf("string"), "Act only on a video carrying one of these (without #).", default=(),
          aliases=("required_hashtags",), attr="required_hashtags"),
    Field("excludedHashtags", ListOf("string"), "Skip a video carrying one of these (without #).", default=(),
          aliases=("excluded_hashtags",), attr="excluded_hashtags"),
    Field("minLikes", "int", "Skip a video with fewer likes; null: no floor.", nullable=True,
          aliases=("min_likes",), attr="min_likes"),
    Field("maxLikes", "int", "Skip a video with more likes; null: no ceiling.", nullable=True,
          aliases=("max_likes",), attr="max_likes"),
    Field("maxLikesPerSession", "int", "Likes in the run.", default=50,
          aliases=("max_likes_per_session",), attr="max_likes_per_session"),
    Field("maxFollowsPerSession", "int", "Follows in the run.", default=20,
          aliases=("max_follows_per_session",), attr="max_follows_per_session"),
    Field("skipAlreadyLiked", "bool", "Skip a video already liked.", default=True,
          aliases=("skip_already_liked",), attr="skip_already_liked"),
    Field("skipAlreadyFollowed", "bool", "Do not follow an author already followed.", default=True,
          aliases=("skip_already_followed",), attr="skip_already_followed"),
    Field("skipAds", "bool", "Skip sponsored videos.", default=True, aliases=("skip_ads",), attr="skip_ads"),
    Field("pauseAfterActions", "int", "Take a break after this many actions.", default=10,
          aliases=("pause_after_actions",), attr="pause_after_actions"),
    Field("pauseDurationMin", "number", "Shortest break, in seconds.", default=30.0,
          aliases=("pause_duration_min",), attr="pause_duration_min"),
    Field("pauseDurationMax", "number", "Longest break, in seconds.", default=60.0,
          aliases=("pause_duration_max",), attr="pause_duration_max"),
)

#: The AI block and the language its operator-facing texts are written in (`ai_hooks.py`).
#: `ai.newFollowers`: the welcome pass of the new-followers flow (`services/welcome/decision.py`).
WELCOME_POLICY = Shape(
    name="TikTokWelcomePolicy",
    doc="The welcome pass of new followers; anything missing means off. Only the follow-back asks the AI.",
    fields=(
        Field("enabled", "bool",
              "Run the welcome pass; without `followBack`, it needs no `ai.enabled`, no key, no AI call.",
              default=False),
        Field("followBack", "bool",
              "Follow back a follower the verdict approves: each follower is then qualified by the AI "
              "(`ai.enabled` required).", default=True, aliases=("follow_back",)),
        Field("welcomeDm", "bool", "Write a welcome message to a new follower (see `dmRequiresFollowBack`).",
              default=False, aliases=("welcome_dm",)),
        Field("minScore", "number", "The verdict's score, 0 to 1 (or 0 to 100), from which a follower is approved.",
              default=0.6, aliases=("min_score",)),
        Field("dmRequiresFollowBack", "bool",
              "Write only to a follower the verdict has us follow back; false: to every new follower, whatever the verdict.",
              default=True, aliases=("dm_requires_follow_back",)),
        Field("maxDms", "int", "Welcome messages in the run.", default=10, aliases=("max_dms",)),
        Field("delayMin", "int", "Shortest pause between two messages, in seconds.", default=30, aliases=("delay_min",)),
        Field("delayMax", "int", "Longest pause between two messages, in seconds.", default=70, aliases=("delay_max",)),
        Field("messages", ListOf("string"), "The welcome messages to pick from."),
    ),
)

#: The run's `ai` block, as the TikTok readers read it: the AI factory (`app/ai/factory.py`), the
#: hooks (`workflows/core/ai_hooks.py`) and the welcome policy.
AI_BLOCK = Shape(
    name="TikTokAiBlock",
    doc="The run's AI settings; the key and the models are injected by the app's main process.",
    fields=(
        Field("enabled", "bool", "AI on for this run.", default=False),
        Field("openrouterApiKey", "string", "The OpenRouter key (injected by the host, never typed).", by=HOST),
        Field("visionModel", "string", "The vision model, instead of the default."),
        Field("textModel", "string", "The text model, instead of the default."),
        Field("nicheTaxonomy", "json", "The niches the classifier chooses from.", aliases=("niche_taxonomy",)),
        Field("profileAnalysis", "bool", "Judge each visited profile before engaging it.", default=False),
        Field("smartComments", "bool", "Write the comments with the AI.", default=False),
        Field("commentDecisionMode", "bool", "Let the AI decide whether to comment at all.", default=False),
        Field("accountNiche", "string", "The acting account's niche, the verdicts are relative to it.",
              aliases=("account_niche",)),
        Field("accountSubNiche", "string", "Its sub-niche.", aliases=("account_sub_niche",)),
        Field("accountProfile", "json", "The acting account's persona, for the comments."),
        Field("newFollowers", WELCOME_POLICY, "The welcome pass of new followers.", aliases=("new_followers",)),
    ),
)

AI_SETTINGS = (
    # Handed whole to the AI factory, the hooks and the welcome policy: their reads are held by
    # `test_workflow_contract_lines.py`.
    Field("ai", AI_BLOCK, "The AI block.", default={}, reader=f"{_AI_HOOKS}:ai_config_from_payload",
          via=f"{_AI_HOOKS}:install_profile_ai_hooks_for_run"),
    Field("language", "string", "The app language the operator-facing AI texts are written in.", default="en",
          aliases=("appLanguage",), reader=f"{_AI_HOOKS}:app_language_from_payload"),
)

VIDEO_STATS = Shape(
    name="TikTokVideoRunStats",
    doc="The run's counters (`send_stats`), totals of the session for a search.",
    fields=(
        Field("videos_watched", "int", "Videos watched."),
        Field("videos_liked", "int", "Videos liked."),
        Field("users_followed", "int", "Authors followed."),
        Field("videos_favorited", "int", "Videos added to favorites."),
        Field("videos_skipped", "int", "Videos skipped."),
        Field("errors", "int", "Errors."),
    ),
)

VIDEO_INFO = Shape(
    name="TikTokVideoOnScreen",
    doc="The video on screen (`IPC.video_info`).",
    fields=(
        Field("author", "string", "Its author's handle."),
        Field("description", "string", "Its caption.", nullable=True),
        Field("like_count", "string", "Its likes, as the screen writes them.", nullable=True),
        Field("is_liked", "bool", "Already liked."),
        Field("is_followed", "bool", "Author already followed."),
        Field("is_ad", "bool", "A sponsored video."),
        Field("hashtags", ListOf("string"), "Its hashtags.", optional=True),
        Field("sound", "string", "Its sound.", optional=True),
        Field("author_pic", "string", "The author's picture, a data URI, sent once per author.", optional=True),
        Field("watch_time", "number", "Seconds the run spends on it.", optional=True),
    ),
)

VIDEO_EVENTS = (
    STATUS_EVENT,
    ERROR_EVENT,
    BOT_PROFILE_EVENT,
    AI_PROFILE_DONE_EVENT,
    Event("stats", doc="The run's counters.", fields=(Field("stats", VIDEO_STATS, "The counters."),)),
    Event("video_info", doc="The video on screen.", fields=(Field("video", VIDEO_INFO, "The video."),)),
    Event("action", doc="An action on the video on screen.", fields=(
        Field("action", OneOf(("like", "follow")), "What was done."),
        Field("target", "string", "The author's handle."),
    )),
    Event("pause", doc="A break starts.", fields=(Field("duration", "int", "Its length, in seconds."),)),
)


def _bridge_fields(*workflow_types: str) -> tuple:
    return (
        Field("deviceId", "string", "The adb serial of the phone.", required=True, by=HOST),
        Field("workflowType", OneOf(workflow_types), "Which workflow of the dispatcher runs.", required=True),
        network_reset_field(),
    )


# ------------------------------------------------------------------------------------ For You

TIKTOK_FOR_YOU = WorkflowContract(
    workflow_id="tiktok.automation.for_you",
    name="TikTokForYou",
    bridge="tiktok_bridge",
    doc="Watch and act on the For You feed.",
    launcher=f"{_WORKFLOWS}.for_you.agent_handler:run_tiktok_for_you",
    reader=f"{_WORKFLOWS}.for_you.payload:for_you_config_from_payload",
    settings=(
        *VIDEO_SETTINGS,
        Field("trainingKeywords", ListOf("string"), "Niche words: a video off them is marked not interested.",
              default=(), aliases=("training_keywords",), attr="training_keywords"),
        Field("trainingRejectOffNiche", "bool", "Mark off-niche videos not interested.", default=True,
              aliases=("training_reject_off_niche",), attr="training_reject_off_niche"),
        Field("maxRejectionsPerSession", "int", "Videos marked not interested in the run.", default=20,
              aliases=("max_rejections_per_session",), attr="max_rejections_per_session"),
        Field("followBackSuggestions", "bool", "Follow back the suggestions the feed shows.", default=False,
              aliases=("follow_back_suggestions",), attr="follow_back_suggestions"),
        *AI_SETTINGS,
    ),
    bridge_fields=_bridge_fields("for_you"),
    events=VIDEO_EVENTS,
)

# ------------------------------------------------------------------------------------- search

TIKTOK_SEARCH = WorkflowContract(
    workflow_id="tiktok.automation.search",
    also=("tiktok.automation.hashtag",),
    name="TikTokSearch",
    bridge="tiktok_bridge",
    doc="Search one or more queries (accounts or hashtags) and act on the videos found; the budgets "
        "are shared between the queries.",
    launcher=f"{_WORKFLOWS}.search.agent_handler:run_tiktok_search",
    reader=_VIDEO_READER,
    settings=(
        *VIDEO_SETTINGS,
        Field("hashtags", ListOf("string"), "The hashtags, in order, without #; wins over every other query key.",
              default=(), reader=_QUERIES_READER, reader_kwargs={"hashtag": True}),
        Field("searchQueries", ListOf("string"), "The queries, in order, when no hashtag list is sent.",
              default=(), reader=_QUERIES_READER, reader_kwargs={"hashtag": True}),
        Field("searchQuery", "string", "One query, when no list is sent.",
              aliases=("search_query", "target", "username", "hashtag"), reader=_QUERIES_READER,
              reader_kwargs={"hashtag": True}, unit="in_list"),
        *AI_SETTINGS,
    ),
    bridge_fields=_bridge_fields("search", "hashtag"),
    refusals=(Refusal("searchQuery", doc="No query: neither a list nor a single one."),),
    events=(
        *VIDEO_EVENTS,
        Event("search_workflow_start", doc="The first query starts.", fields=(
            Field("current_target", "string", "The query."),
            Field("targets", ListOf("string"), "Every query of the run."),
            Field("current_target_index", "int", "Its rank, from 0."),
            Field("workflow_type", OneOf(("search", "hashtag")), "Search or hashtag."),
        )),
        Event("search_target_switch", doc="The run moves to the next query.", fields=(
            Field("current_target", "string", "The query."),
            Field("target_index", "int", "Its rank, from 0."),
            Field("total_targets", "int", "Queries of the run."),
            Field("workflow_type", OneOf(("search", "hashtag")), "Search or hashtag."),
        )),
    ),
)

CONTRACTS = (TIKTOK_FOR_YOU, TIKTOK_SEARCH)

__all__ = ["CONTRACTS", "TIKTOK_FOR_YOU", "TIKTOK_SEARCH", "VIDEO_SETTINGS"]
