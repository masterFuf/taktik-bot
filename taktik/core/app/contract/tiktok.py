"""TikTok workflows with a bridge of their own (`tiktok.standalone.*`): unfollow, cold DM, scraping.

Each declaration names the reader it describes; `tests/unit/app/contract` holds the reader to it.
The upload (`tiktok.standalone.upload_post`) has no payload reader yet and is not declared.
"""

from __future__ import annotations

from .schema import HOST, Computed, Event, Field, ListOf, MapOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import AI_SPEND_EVENT, ERROR_EVENT, STATUS_EVENT, device_field, network_reset_field

_WORKFLOWS = "taktik.core.social_media.tiktok.actions.business.workflows"

# ------------------------------------------------------------------------------------ unfollow

UNFOLLOW_RUN_STATS = Shape(
    name="TikTokUnfollowRunStats",
    doc="`UnfollowStats.to_dict()`, plus the run's target.",
    fields=(
        Field("unfollowed", "int", "Confirmed unfollows."),
        Field("skipped", "int", "Rows kept, every motive together."),
        Field("skipped_friends", "int", "Mutual friends kept."),
        Field("skipped_handle_unknown", "int", "Rows whose handle the list hides."),
        Field("skipped_recent_follows", "int", "Followed less than the minimum age ago."),
        Field("skipped_follow_date_unknown", "int", "No follow date: kept in doubt."),
        Field("unconfirmed", "int", "Taps the row did not confirm: not unfollows."),
        Field("recorded", "int", "Confirmed unfollows written to the base."),
        Field("errors", "int", "Rows that failed."),
        Field("stop_reason", "string", "Why the run stopped early; empty otherwise."),
        Field("refusals", MapOf("int"), "Motive -> rows kept for it."),
        Field("target", "int", "The run's maximum."),
    ),
)

TIKTOK_UNFOLLOW = WorkflowContract(
    workflow_id="tiktok.standalone.tiktok_unfollow",
    name="TikTokUnfollow",
    bridge="tiktok_unfollow_bridge",
    doc="Unfollow from the acting account's following list.",
    launcher=f"{_WORKFLOWS}.unfollow.agent_handler:run_tiktok_unfollow",
    reader=f"{_WORKFLOWS}.unfollow.payload:unfollow_config_from_payload",
    nest="config",
    settings=(
        Field("max_unfollows", "int", "Stop after this many confirmed unfollows.", default=20,
              aliases=("maxUnfollows",), attr="max_unfollows"),
        Field("delay_min", "number", "Shortest pause after an unfollow, in seconds.", default=1.0,
              aliases=("min_delay", "minDelay"), attr="min_delay"),
        Field("delay_max", "number", "Longest pause after an unfollow, in seconds.", default=3.0,
              aliases=("max_delay", "maxDelay"), attr="max_delay"),
        Field("skip_friends", "bool", "Keep mutual friends.", default=True,
              aliases=("skipFriends",), attr="include_friends", negate=True),
        Field("min_follow_age", "int", "Keep accounts followed less than this many days ago; 0: no rule.",
              default=0, aliases=("minFollowAge", "min_follow_age_days"), attr="min_follow_age_days"),
        Field("max_scroll_attempts", "int", "Scrolls without a new row before the list is done.", default=10,
              aliases=("maxScrollAttempts",), attr="max_scroll_attempts"),
        Field("include_friends", "bool", "Older opposite of `skip_friends`, read when it is absent.",
              default=False, aliases=("includeFriends",), attr="include_friends", app=False),
        Field("botUsername", "string", "The acting account; the bridge reads it on the phone at start.",
              aliases=("bot_username",), attr="bot_username", app=False),
    ),
    bridge_fields=(device_field("device_id"), network_reset_field()),
    beside_settings=("networkReset",),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        Event("unfollow_stats", doc="The run's counters, after each row and at the end.", fields=(
            Field("stats", UNFOLLOW_RUN_STATS, "The counters."),
        )),
        Event("unfollow_event", doc="One row of the list: unfollowed, kept, or not confirmed.", fields=(
            Field("event", OneOf(("unfollowed", "skipped", "not_confirmed")), "What happened to the row."),
            Field("username", "string", "The row's handle; null for a row without one.", nullable=True),
            Field("count", "int", "Confirmed unfollows so far (`unfollowed`).", optional=True),
            Field("reason", "string", "Why the row was kept (`skipped`, `not_confirmed`).", optional=True),
            Field("state", "string", "What the row showed after the tap (`not_confirmed`).", optional=True),
        )),
    ),
)

# ------------------------------------------------------------------------------------- cold DM

DM_OUTREACH_STATS = Shape(
    name="TikTokDmOutreachStats",
    doc="The run's counters.",
    fields=(
        Field("sent", "int", "Messages sent."),
        Field("success", "int", "Messages the conversation shows."),
        Field("failed", "int", "Recipients that failed."),
        Field("privacy_blocked", "int", "Recipients whose settings refuse messages."),
        Field("not_found", "int", "Recipients the search did not find."),
        Field("no_message_entry", "int", "Recipients whose profile offers no message entry: skipped."),
    ),
)

TIKTOK_DM_OUTREACH = WorkflowContract(
    workflow_id="tiktok.standalone.tiktok_dm_outreach",
    name="TikTokDmOutreach",
    bridge="dm_outreach_bridge",
    doc="Write to a list of accounts the acting account never wrote to.",
    launcher=f"{_WORKFLOWS}.dm.agent_handler:run_tiktok_dm_outreach",
    reader=f"{_WORKFLOWS}.dm.payload:dm_outreach_request_from_payload",
    reader_kwargs={"default_session_id": "<device>"},
    settings=(
        Field("recipients", ListOf("string"), "Handles to write to; a text is split on commas.", required=True,
              aliases=("targetUsernames", "target_usernames"), attr="recipients"),
        Field("messages", ListOf("string"), "Messages to pick from, kept as written; in AI mode, the fallback.",
              default=(), aliases=("messageTemplates",), attr="messages"),
        Field("delayMin", "number", "Shortest pause between two recipients, in seconds.", default=30,
              aliases=("delay_min",), attr="delay_min"),
        Field("delayMax", "number", "Longest pause between two recipients, in seconds.", default=60,
              aliases=("delay_max",), attr="delay_max"),
        Field("maxDms", "int", "Stop after this many messages.", default=50, aliases=("max_dms",), attr="max_dms"),
        Field("accountId", "int", "The acting account's row, for the sent-DM markers.", default=1,
              aliases=("account_id",), attr="account_id"),
        Field("messageMode", OneOf(("manual", "ai")), "The static list, or one message written per recipient.",
              default="manual", aliases=("message_mode",), attr="message_mode"),
        Field("aiPrompt", "string", "What the AI message says (AI mode).", default="",
              aliases=("ai_prompt",), attr="ai_prompt"),
        Field("sessionId", "string", "Tags the sent-DM markers of this run.", default=Computed("the device id"),
              aliases=("session_id",), attr="session_id", by=HOST),
        Field("openrouterApiKey", "string", "The key the AI mode writes with; injected by the host.", default="",
              aliases=("openrouter_api_key",), attr="openrouter_api_key", by=HOST),
    ),
    bridge_fields=(device_field("device_id", "deviceId"), network_reset_field()),
    refusals=(
        Refusal("recipients", doc="Nobody to write to."),
        Refusal("messages", when={"messageMode": "manual"}, doc="Manual mode without a message."),
    ),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        AI_SPEND_EVENT,
        Event("progress", doc="The recipient being processed.", fields=(
            Field("current", "int", "Its rank, from 1."),
            Field("total", "int", "Recipients this run will process."),
            Field("username", "string", "Its handle."),
        )),
        Event("dm_result", doc="What happened with one recipient.", fields=(
            Field("username", "string", "Its handle."),
            Field("success", "bool", "The message was sent."),
            Field("error", "string", "Why not.", nullable=True),
            Field("skipped", "bool", "Left out on purpose: neither sent nor failed.", optional=True),
            Field("reason", "string", "Why it was left out (`no_message_entry`).", optional=True),
        )),
        Event("stats", doc="The run's counters, after each recipient.", fields=(
            Field("stats", DM_OUTREACH_STATS, "The counters."),
        )),
    ),
)

# ------------------------------------------------------------------------------------ scraping

TIKTOK_SCRAPING = WorkflowContract(
    workflow_id="tiktok.standalone.tiktok_scraping",
    name="TikTokScraping",
    bridge="tiktok_scraping_bridge",
    doc="Collect profiles from accounts, a hashtag, posts' commenters, sounds or an account's posts.",
    launcher=f"{_WORKFLOWS}.scraping.agent_handler:run_tiktok_scraping",
    reader=f"{_WORKFLOWS}.scraping.payload:scraping_config_from_payload",
    settings=(
        Field("type", OneOf(("target", "hashtag", "post_url", "sound", "account_posts")), "Where the profiles come from.",
              default="target", aliases=("scrape_type",), attr="scrape_type"),
        Field("targetUsernames", ListOf("string"), "Accounts to read (`target`, `account_posts`); a text is split on commas.",
              default=(), aliases=("target_usernames",), attr="target_usernames"),
        Field("scrapeType", OneOf(("followers", "following")), "Which list of the accounts (`target`).",
              default="followers", aliases=("target_scrape_type",), attr="target_scrape_type"),
        Field("hashtag", "string", "The hashtag, without # (`hashtag`).", default="", attr="hashtag"),
        Field("postUrls", ListOf("string"), "Post links whose commenters to collect (`post_url`).", default=(),
              aliases=("post_urls",), attr="post_urls"),
        Field("maxCommentersPerPost", "int", "Commenters to identify per post.", default=20,
              aliases=("max_commenters_per_post",), attr="max_commenters_per_post"),
        Field("soundQuery", "string", "A sound to name instead of discovering one on the feed (`sound`).", default="",
              aliases=("sound_query",), attr="sound_query"),
        Field("minSoundPosts", "int", "Skip sounds with fewer posts.", default=500,
              aliases=("min_sound_posts",), attr="min_sound_posts"),
        Field("maxUsersPerSound", "int", "Profiles to collect per sound.", default=10,
              aliases=("max_users_per_sound",), attr="max_users_per_sound"),
        Field("maxSoundsPerSession", "int", "Sounds to open in one run.", default=5,
              aliases=("max_sounds_per_session",), attr="max_sounds_per_session"),
        Field("maxPostsPerAccount", "int", "Post links to collect per account (`account_posts`).", default=20,
              aliases=("max_posts_per_account",), attr="max_posts_per_account"),
        Field("maxProfiles", "int", "Stop after this many profiles.", default=500,
              aliases=("max_profiles",), attr="max_profiles"),
        Field("maxPosts", "int", "Videos to walk through (`hashtag`).", default=50,
              aliases=("maxVideos", "max_videos"), attr="max_videos"),
        Field("enrichProfiles", "bool", "Open each profile for its counters and bio.", default=True,
              aliases=("enrich_profiles",), attr="enrich_profiles"),
        Field("maxProfilesToEnrich", "int", "Profiles to open.", default=50,
              aliases=("max_profiles_to_enrich",), attr="max_profiles_to_enrich"),
        Field("sessionDurationMinutes", "number", "Stop after this many minutes; 0: no limit.", default=0.0,
              aliases=("session_duration_minutes",), attr="session_duration_minutes"),
        Field("saveToDb", "bool", "File a scraping session and its profiles.", default=True,
              aliases=("save_to_db",), reader=f"{_WORKFLOWS}.scraping.payload:save_to_db_from_payload"),
    ),
    bridge_fields=(device_field("deviceId"),),
    refusals=(
        Refusal("targetUsernames", when={"type": "target"}, doc="Account scraping without an account."),
        Refusal("hashtag", when={"type": "hashtag"}, doc="Hashtag scraping without a hashtag."),
    ),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        Event("scraping_session", doc="The run's `scraping_sessions` row, as soon as it is written.", fields=(
            Field("scraping_id", "int", "The row's id: the desktop closes it if the bridge is killed."),
            Field("platform", OneOf(("tiktok",)), "The platform of the row."),
        )),
        Event("scraping_progress", doc="Profiles collected so far.", fields=(
            Field("scraped", "int", "Profiles collected."),
            Field("total", "int", "The run's budget."),
            Field("current", "string", "The last one collected."),
        )),
        Event("scraping_profile", doc="One profile collected.", fields=(
            Field("username", "string", "Its handle."),
            Field("followersCount", "int", "Its followers."),
            Field("followingCount", "int", "The accounts it follows."),
            Field("scrapedAt", "string", "When, ISO 8601."),
        )),
        Event("scraping_completed", doc="The run is over.", fields=(
            Field("totalScraped", "int", "Profiles collected."),
        )),
    ),
)

CONTRACTS = (TIKTOK_UNFOLLOW, TIKTOK_DM_OUTREACH, TIKTOK_SCRAPING)

__all__ = ["CONTRACTS", "TIKTOK_DM_OUTREACH", "TIKTOK_SCRAPING", "TIKTOK_UNFOLLOW"]
