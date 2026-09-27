"""TikTok workflows of the `tiktok_bridge` dispatcher that visit profiles: followers, target
profiles, post URL.

The three read their interaction settings, their session budgets and their filter criteria through
`followers/payload.py`, then what is their own: the accounts whose followers to walk, the list of
profiles, the video whose commenters to visit.

The filter criteria are not read key by key: `resolve_tiktok_filter_criteria` merges every flat key
of the payload, and the `filters` block over them, into the criteria the shared evaluator
(`shared/filtering`) reads. Declared here are the criteria the evaluator reads, under the app's
names; when two names of one criterion are both sent, the last one of the payload wins.
"""

from __future__ import annotations

from .schema import HOST, Computed, Event, Field, ListOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import ERROR_EVENT, STATUS_EVENT, network_reset_field
from .tiktok_automation import AI_SETTINGS

_WORKFLOWS = "taktik.core.social_media.tiktok.actions.business.workflows"
_FOLLOWERS = f"{_WORKFLOWS}.followers.payload"
_SETTINGS_READER = f"{_FOLLOWERS}:followers_settings_from_payload"


def _percent(key: str, snake: str, doc: str, default: float) -> Field:
    return Field(key, "number", f"{doc}, in percent (a snake_case name takes a fraction, or a percent above 1).",
                 default=default, aliases=(snake,), attr=snake, unit="percent")


def _criterion(key: str, spec, doc: str, criterion: str, *aliases: str, negate: bool = False) -> Field:
    return Field(key, spec, f"Filter criterion: {doc}", aliases=aliases, attr=f"filters.{criterion}", negate=negate)


#: The interaction settings every profile-visiting workflow reads (`followers_settings_from_payload`).
PROFILE_SETTINGS = (
    Field("minPostsPerProfile", "int", "Fewest videos watched on a visited profile.", default=1,
          aliases=("min_posts_per_profile",), attr="min_posts_per_profile"),
    Field("maxPostsPerProfile", "int", "Most videos watched on a visited profile.", default=3,
          aliases=("max_posts_per_profile", "postsPerProfile", "posts_per_profile"), attr="max_posts_per_profile"),
    Field("minWatchTime", "number", "Shortest watch of a video, in seconds.", default=5.0,
          aliases=("min_watch_time",), attr="min_watch_time"),
    Field("maxWatchTime", "number", "Longest watch of a video, in seconds.", default=15.0,
          aliases=("max_watch_time",), attr="max_watch_time"),
    _percent("likeProbability", "like_probability", "Chance to like a video", 70),
    _percent("favoriteProbability", "favorite_probability", "Chance to add a video to favorites", 30),
    _percent("commentProbability", "comment_probability", "Chance to comment on a video", 10),
    Field("commentTexts", ListOf("string"), "Comments to pick from, kept as written.", default=(),
          aliases=("comments", "comment_texts"), attr="comment_texts"),
    Field("maxCommentsPerSession", "int", "Comments in the run.", default=10,
          aliases=("max_comments_per_session",), attr="max_comments_per_session"),
    _percent("shareProbability", "share_probability", "Chance to share a video", 5),
    _percent("followProbability", "follow_probability", "Chance to follow the profile", 50),
    _percent("storyLikeProbability", "story_like_probability", "Chance to like the profile's story", 50),
    Field("minDelay", "number", "Shortest pause between two actions, in seconds.", default=1.0,
          aliases=("min_delay",), attr="min_delay"),
    Field("maxDelay", "number", "Longest pause between two actions, in seconds.", default=3.0,
          aliases=("max_delay",), attr="max_delay"),
    Field("pauseAfterActions", "int", "Take a break after this many actions.", default=10,
          aliases=("pause_after_actions",), attr="pause_after_actions"),
    Field("pauseDurationMin", "number", "Shortest break, in seconds.", default=30.0,
          aliases=("pause_duration_min",), attr="pause_duration_min"),
    Field("pauseDurationMax", "number", "Longest break, in seconds.", default=60.0,
          aliases=("pause_duration_max",), attr="pause_duration_max"),
    Field("includeFriends", "bool", "Visit mutual friends too.", default=False,
          aliases=("include_friends",), attr="include_friends"),
    Field("maxConsecutiveKnownUsernames", "int", "Stop a list after this many known accounts in a row.",
          default=150, aliases=("max_consecutive_known_usernames",), attr="max_consecutive_known_usernames"),
    Field("maxLikesPerSession", "int", "Likes in the run.", default=50, aliases=("max_likes_per_session",),
          attr="0", reader=f"{_FOLLOWERS}:session_limits_from_payload"),
    Field("maxFollowsPerSession", "int", "Follows in the run.", default=20, aliases=("max_follows_per_session",),
          attr="1", reader=f"{_FOLLOWERS}:session_limits_from_payload"),
    # The criteria the shared evaluator reads.
    _criterion("minFollowers", "int", "skip a profile with fewer followers.", "min_followers", "min_followers"),
    _criterion("minPosts", "int", "skip a profile with fewer videos.", "min_posts", "minVideos", "min_posts"),
    _criterion("allowPrivate", "bool", "false: skip private profiles.", "allow_private", "allow_private"),
    _criterion("skipPrivateAccounts", "bool", "true: skip private profiles (false says nothing).",
               "allow_private", "skip_private_accounts", negate=True),
    _criterion("maxFollowingRatio", "number", "skip a profile following more than this many times its "
               "followers.", "max_following_ratio", "max_following_ratio"),
    _criterion("verifiedPenalty", "number", "points taken from a verified profile.", "verified_penalty",
               "verified_penalty"),
    _criterion("businessPenalty", "number", "points taken from a business profile.", "business_penalty",
               "business_penalty"),
    _criterion("forbiddenBioKeywords", ListOf("string"), "skip a bio holding one of these.",
               "forbidden_bio_keywords", "forbidden_bio_keywords"),
    _criterion("requiredBioKeywords", ListOf("string"), "skip a bio holding none of these.",
               "required_bio_keywords", "required_bio_keywords"),
    _criterion("requireBio", "bool", "skip a profile without a bio.", "require_bio", "require_bio"),
    _criterion("requireFullName", "bool", "skip a profile without a display name.", "require_full_name",
               "requireDisplayName", "require_full_name"),
    _criterion("minScore", "number", "skip a profile scoring less.", "min_score", "min_score"),
    Field("filters", "json", "Criteria as a block, over the flat ones; `maxFollowers` in it is the follower "
          "ceiling (flat, it is the visit budget).", aliases=("filter_criteria",), attr="filters", unit="merged"),
    Field("botUsername", "string", "The acting account; the bridge reads it on the phone at start.",
          aliases=("bot_username",), reader=f"{_FOLLOWERS}:bot_username_from_payload", app=False),
    *AI_SETTINGS,
)

PROFILE_RUN_STATS = Shape(
    name="TikTokProfileRunStats",
    doc="The run's counters: the session totals, and the current target's live counters over them.",
    fields=(
        *(Field(name, "int", doc) for name, doc in (
            ("followers_seen", "Accounts read in the lists."),
            ("profiles_visited", "Profiles visited."),
            ("posts_watched", "Videos watched."),
            ("likes", "Videos liked."),
            ("favorites", "Videos added to favorites."),
            ("follows", "Profiles followed."),
            ("already_friends", "Mutual friends met."),
            ("skipped", "Profiles skipped."),
            ("known_usernames_seen", "Accounts already known."),
            ("new_usernames_seen", "Accounts met for the first time."),
            ("consecutive_known_usernames", "Known accounts in a row, now."),
            ("errors", "Errors."),
        )),
        Field("profiles_filtered", "int", "Profiles the criteria refused.", optional=True),
        Field("comments", "int", "Comments written.", optional=True),
        Field("shares", "int", "Videos shared.", optional=True),
        Field("completion_reason", "string", "Why the run ended (final stats).", optional=True),
        Field("elapsed_seconds", "number", "Time spent.", optional=True),
        Field("elapsed_formatted", "string", "The same, for a person.", optional=True),
        Field("current_target", "string", "The account whose followers are walked (followers).", optional=True),
        Field("target_index", "int", "Its rank, from 0 (followers).", optional=True),
        Field("total_targets", "int", "Targets of the run, when the run knows it.", optional=True),
    ),
)

PROFILE_EVENTS = (
    STATUS_EVENT,
    ERROR_EVENT,
    Event("followers_stats", doc="The run's counters.", fields=(Field("stats", PROFILE_RUN_STATS, "The counters."),)),
    Event("action", doc="An action on the profile being visited.", fields=(
        Field("action", "string", "What was done (like, follow, favorite, comment, story_like...)."),
        Field("target", "string", "The profile's handle."),
    )),
    Event("pause", doc="A break starts.", fields=(Field("duration", "int", "Its length, in seconds."),)),
    Event("profile_captured", doc="What was read off a visited profile.", fields=(
        Field("platform", OneOf(("tiktok",)), "The platform."),
        Field("username", "string", "Its handle."),
        Field("display_name", "string", "Its display name.", nullable=True),
        Field("followers_count", "int", "Its followers.", nullable=True),
        Field("following_count", "int", "The accounts it follows.", nullable=True),
        Field("likes_count", "int", "Its likes.", nullable=True),
        Field("videos_count", "int", "Its videos.", nullable=True),
        Field("biography", "string", "Its bio.", nullable=True),
        Field("is_private", "bool", "A private profile."),
        Field("is_verified", "bool", "A verified profile."),
        Field("profile_pic_base64", "string", "Its picture, a data URI.", nullable=True),
    )),
    Event("workflow_start", doc="A target, or the single pass, starts.", fields=(
        Field("target", "string", "The account, or the video link; empty for a list of profiles."),
        Field("targets", ListOf("string"), "Every target of the run (the profiles of a list)."),
        Field("current_target_index", "int", "Its rank, from 0."),
    )),
)

_REST = (network_reset_field(),)


def _workflow_type(*values: str) -> Field:
    return Field("workflowType", OneOf(values), "Which workflow of the dispatcher runs.", required=True)


def _device() -> Field:
    return Field("deviceId", "string", "The adb serial of the phone.", required=True, by=HOST)


# ------------------------------------------------------------------------------------ followers

TIKTOK_FOLLOWERS = WorkflowContract(
    workflow_id="tiktok.automation.followers",
    name="TikTokFollowers",
    bridge="tiktok_bridge",
    doc="Visit the followers of one or more accounts; the profile budget is shared between them.",
    launcher=f"{_WORKFLOWS}.followers.agent_handler:run_tiktok_followers",
    reader=_SETTINGS_READER,
    settings=(
        *PROFILE_SETTINGS,
        Field("targetAccounts", ListOf("string"), "The accounts whose followers to walk, in order, without @; "
              "wins over every other target key.", default=(), reader=f"{_FOLLOWERS}:followers_targets_from_payload"),
        Field("targets", ListOf("string"), "The same list, when `targetAccounts` is not sent.", default=(),
              reader=f"{_FOLLOWERS}:followers_targets_from_payload"),
        Field("searchQuery", "string", "One account, when no list is sent.",
              aliases=("search_query", "target", "username"), reader=f"{_FOLLOWERS}:followers_targets_from_payload",
              unit="in_list"),
        Field("maxFollowers", "int", "Profiles the run visits, shared between the accounts.", default=20,
              aliases=("max_followers", "maxVideos", "max_videos"), reader=f"{_FOLLOWERS}:profile_budget_from_payload"),
    ),
    bridge_fields=(_device(), _workflow_type("followers"), *_REST),
    refusals=(Refusal("searchQuery", doc="No account: neither a list nor a single one."),),
    events=(
        *PROFILE_EVENTS,
        Event("target_switch", doc="The run moves to an account.", fields=(
            Field("current_target", "string", "The account."),
            Field("target_index", "int", "Its rank, from 0."),
            Field("total_targets", "int", "Accounts of the run."),
            Field("next_target", "string", "The account after it.", nullable=True),
        )),
    ),
)

# ------------------------------------------------------------------------------- target profiles

TIKTOK_TARGET_PROFILES = WorkflowContract(
    workflow_id="tiktok.automation.target_profiles",
    name="TikTokTargetProfiles",
    bridge="tiktok_bridge",
    doc="Visit a list of profiles in one pass.",
    launcher=f"{_WORKFLOWS}.target_profiles.agent_handler:run_tiktok_target_profiles",
    reader=_SETTINGS_READER,
    settings=(
        *PROFILE_SETTINGS,
        Field("profiles", ListOf("string"), "The profiles to visit, without @.", required=True,
              aliases=("targetProfiles", "usernames"),
              reader=f"{_WORKFLOWS}.target_profiles.payload:target_profiles_from_payload"),
        Field("maxProfiles", "int", "Profiles the run visits.", default=Computed("one per listed profile"),
              aliases=("maxFollowers",), reader=f"{_WORKFLOWS}.target_profiles.payload:profile_visit_budget",
              reader_kwargs={"profiles": ["one", "two"]}),
    ),
    bridge_fields=(_device(), _workflow_type("target_profiles"), *_REST),
    refusals=(Refusal("profiles", doc="No profile to visit."),),
    events=PROFILE_EVENTS,
)

# ------------------------------------------------------------------------------------ post URL

TIKTOK_POST_URL = WorkflowContract(
    workflow_id="tiktok.automation.post_url",
    name="TikTokPostUrl",
    bridge="tiktok_bridge",
    doc="Visit the people who commented on one video.",
    launcher=f"{_WORKFLOWS}.post_url.agent_handler:run_tiktok_post_url",
    reader=f"{_WORKFLOWS}.post_url.payload:post_url_config_from_payload",
    settings=(
        *(item for item in PROFILE_SETTINGS if item.key not in ("maxLikesPerSession", "maxFollowsPerSession")),
        Field("maxLikesPerSession", "int", "Likes in the run.", default=50, aliases=("max_likes_per_session",),
              attr="max_likes_per_session"),
        Field("maxFollowsPerSession", "int", "Follows in the run.", default=20, aliases=("max_follows_per_session",),
              attr="max_follows_per_session"),
        Field("postUrl", "string", "The video's link.", required=True,
              aliases=("post_url", "videoUrl", "video_url", "url", "postLink"), attr="post_url"),
        Field("maxCommenters", "int", "Commenters to identify; each costs a profile open.", default=20,
              aliases=("max_commenters",), attr="max_commenters"),
        Field("maxProfiles", "int", "Commenters to visit.", default=Computed("the commenter budget"),
              aliases=("max_profiles", "maxFollowers", "max_followers", "maxVideos", "max_videos"),
              attr="max_followers"),
        Field("maxCommentScrolls", "int", "Scrolls of the comments.", default=8,
              aliases=("max_comment_scrolls",), attr="max_comment_scrolls"),
        Field("deviceId", "string", "The adb serial the link is opened on.", required=True, aliases=("device_id",),
              reader=f"{_WORKFLOWS}.post_url.payload:device_id_from_payload", by=HOST),
    ),
    bridge_fields=(_workflow_type("post_url"), *_REST),
    refusals=(Refusal("postUrl", doc="No link."),),
    events=PROFILE_EVENTS,
)

CONTRACTS = (TIKTOK_FOLLOWERS, TIKTOK_TARGET_PROFILES, TIKTOK_POST_URL)

__all__ = ["CONTRACTS", "PROFILE_SETTINGS", "TIKTOK_FOLLOWERS", "TIKTOK_POST_URL", "TIKTOK_TARGET_PROFILES"]
