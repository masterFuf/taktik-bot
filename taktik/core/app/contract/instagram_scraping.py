"""Instagram scraping (`scraping_bridge`): the five `instagram.scraping.*` workflows of the manifest.

One payload, one reader, one launcher: `type` names the source, and so the workflow id
(`instagram.scraping.<type>`); the settings of a source are read only for that source (`when`).
`tests/unit/app/contract` holds the reader, the launcher and the bridge to this declaration.
"""

from __future__ import annotations

from .schema import HOST, Event, Field, ListOf, MapOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import AI_ERROR_EVENT, AI_PROFILE_DONE_EVENT, AI_PROFILE_START_EVENT, device_field
from .stop_reasons import INSTAGRAM_SCRAPING_COMPLETION_REASON

_SCRAPING = "taktik.core.social_media.instagram.workflows.scraping"

SCRAPING_TYPES = ("target", "hashtag", "post_url", "usernames", "profile_posts")

_TARGET = {"type": "target"}
_ACCOUNTS = {"type": ("target", "profile_posts")}
_HASHTAG = {"type": "hashtag"}
_POST_URL = {"type": "post_url"}
_USERNAMES = {"type": "usernames"}
_PROFILE_POSTS = {"type": "profile_posts"}
_AI = {"ai.enabled": True}

AI = Shape(
    name="InstagramScrapingAi",
    doc="AI qualification of each profile; read only when `enabled`.",
    fields=(
        Field("enabled", "bool", "Qualify each profile with the AI.", default=False, attr="ai_mode"),
        Field("profileAnalysis", "bool", "Classify the profile's niche.", default=True,
              attr="ai_profile_analysis", when=_AI),
        Field("niche", "string", "The niche to qualify against; empty: the prompt alone.", default="",
              attr="ai_niche", when=_AI),
        Field("qualificationPrompt", "string", "What a qualified profile is, for the text qualification.",
              default="", attr="ai_qualification_prompt", when=_AI),
        Field("openrouterApiKey", "string", "The key the AI writes with; injected by the host.", default="",
              attr="openrouter_api_key", when=_AI, by=HOST),
        Field("visionModel", "string", "The model that reads the profile's screenshot; injected by the host.",
              default="", attr="vision_model", when=_AI, by=HOST),
        Field("nicheTaxonomy", MapOf(ListOf("string")), "Premium taxonomy, niche slug -> sub-niches; injected "
              "by the host.", default={}, attr="niche_taxonomy", when=_AI, by=HOST),
    ),
)

_SETTINGS = (
    Field("type", OneOf(SCRAPING_TYPES), "Where the profiles come from; names the workflow "
          "`instagram.scraping.<type>`.", required=True, attr="type"),
    # Every source.
    Field("sessionDurationMinutes", "number", "Stop after this many minutes.", default=60,
          aliases=("session_duration_minutes",), attr="session_duration_minutes"),
    Field("maxProfiles", "int", "Stop after this many profiles.", default=500, aliases=("max_profiles",),
          attr="max_profiles"),
    Field("exportCsv", "bool", "Write the profiles to a CSV file at the end.", default=True,
          aliases=("export_csv",), attr="export_csv"),
    Field("saveToDb", "bool", "File a scraping session and its profiles.", default=True,
          aliases=("save_to_db",), attr="save_to_db"),
    Field("enrichProfiles", "bool", "Open each profile for its counters and bio.", default=False,
          aliases=("enrich_profiles",), attr="enrich_profiles"),
    Field("fetchLocation", "bool", "Enriched runs: also open \"About this account\" (country, date joined).",
          default=False, aliases=("fetch_location",), attr="fetchLocation"),
    Field("minFollowers", "int", "Skip profiles with fewer followers; null: no rule.", attr="minFollowers",
          nullable=True),
    Field("minFollowing", "int", "Skip profiles following fewer accounts; null: no rule.", attr="minFollowing",
          nullable=True),
    Field("minPosts", "int", "Skip profiles with fewer posts; null: no rule.", attr="minPosts", nullable=True),
    Field("maxFollowers", "int", "Skip profiles with more followers; null or 0: no limit.", attr="maxFollowers",
          nullable=True),
    Field("maxFollowing", "int", "Skip profiles following more accounts; null or 0: no limit.",
          attr="maxFollowing", nullable=True),
    Field("requireProfilePicture", "bool", "Skip profiles without a picture.", default=False,
          attr="requireProfilePicture"),
    Field("skipPrivateProfiles", "bool", "Skip private profiles.", default=True, attr="skipPrivateProfiles"),
    Field("rescrapeAfterDays", "int", "Scrape a known profile again after this many days; 0: always; "
          "null: never.", aliases=("rescrape_after_days",), attr="rescrape_after_days", nullable=True),
    Field("deepQualify", "bool", "Read each profile's following list to qualify it.", default=False,
          aliases=("deep_qualify",), attr="deep_qualify"),
    Field("deepQualifyMaxFollowing", "int", "Accounts a deep qualification reads.", default=30,
          aliases=("deep_qualify_max_following",), attr="deep_qualify_max_following",
          when={"deepQualify": True}),
    Field("appLanguage", "string", "The language the AI answers in.", default="en",
          aliases=("response_language",), attr="response_language"),
    Field("ai", AI, "AI qualification."),
    Field("aiRescrapeMode", OneOf(("full", "stats_only")), "A known profile scraped again: everything, or "
          "its counters only (AI runs).", default="full", aliases=("ai_rescrape_mode",), attr="ai_rescrape_mode",
          when=_AI),
    # `target` and `profile_posts`.
    Field("targetUsernames", ListOf("string"), "Accounts to read (`target`, `profile_posts`); a text is one "
          "account.", default=(), aliases=("target_usernames", "targets", "targetAccounts"),
          attr="target_usernames", when=_ACCOUNTS),
    # `target`.
    Field("scrapeType", OneOf(("followers", "following", "posts")), "Which list of the accounts (`target`); "
          "`posts`: the likers and commenters of their first post.", default="followers",
          aliases=("scrape_type",), attr="scrape_type", when=_TARGET),
    Field("scrapePostLikers", "bool", "`posts`: collect the likers.", default=True,
          aliases=("scrape_post_likers",), attr="scrape_post_likers", when=_TARGET),
    Field("scrapePostCommenters", "bool", "`posts`: collect the commenters.", default=False,
          aliases=("scrape_post_commenters",), attr="scrape_post_commenters", when=_TARGET),
    # `hashtag`.
    Field("hashtags", ListOf("string"), "Hashtags to walk, without # (`hashtag`).", default=(),
          aliases=("hashtag",), attr="hashtags", when=_HASHTAG),
    Field("scrapeHashtagLikers", "bool", "Collect the likers of the hashtag's posts.", default=True,
          aliases=("scrape_likers",), attr="scrape_likers", when=_HASHTAG),
    Field("scrapeHashtagCommenters", "bool", "Collect the commenters of the hashtag's posts.", default=False,
          aliases=("scrape_commenters",), attr="scrape_commenters", when=_HASHTAG),
    Field("maxPosts", "int", "Posts of the hashtag to open.", default=50, aliases=("max_posts",),
          attr="max_posts", when=_HASHTAG),
    # `post_url`.
    Field("postUrls", ListOf("string"), "Post links whose people to collect (`post_url`).", default=(),
          aliases=("post_urls", "postUrl"), attr="post_urls", when=_POST_URL),
    Field("scrapePostUrlLikers", "bool", "Collect the post's likers.", default=True,
          aliases=("scrape_likers",), attr="scrape_likers", when=_POST_URL),
    Field("scrapePostUrlCommenters", "bool", "Collect the post's commenters.", default=False,
          aliases=("scrape_commenters",), attr="scrape_commenters", when=_POST_URL),
    # `usernames`.
    Field("usernames", ListOf("string"), "Profiles to qualify, by name (`usernames`).", default=(),
          attr="usernames", when=_USERNAMES),
    Field("sourceName", "string", "Where the list came from, kept on the scraping session.",
          default="manual selection", attr="source_name", when=_USERNAMES),
    # `profile_posts`.
    Field("maxPostsPerTarget", "int", "Posts to collect per account (`profile_posts`); 0 or less: the "
          "default.", default=20, attr="max_posts_per_target", when=_PROFILE_POSTS),
)

_BRIDGE_FIELDS = (
    device_field("deviceId"),
    Field("packageName", "string", "An Instagram clone's package, for its installed version; a CLI run's "
          "restart opens it too.", by=HOST),
)

_REFUSALS = (
    # Without it the reader reads no source and the default `target` run has no account.
    Refusal("type", doc="No source named."),
    Refusal("targetUsernames", when=_TARGET, doc="Account scraping without an account."),
    Refusal("targetUsernames", when=_PROFILE_POSTS, doc="Post collection without an account."),
    Refusal("hashtags", when=_HASHTAG, doc="Hashtag scraping without a hashtag."),
    Refusal("postUrls", when=_POST_URL, doc="Post scraping without a link."),
    Refusal("usernames", when=_USERNAMES, doc="Qualification without a profile."),
)

# ------------------------------------------------------------------------------------- lines

#: `print_scraping_result` (`bridges/instagram/scraping/runtime/runner.py`), the bridge's last line.
SCRAPING_RESULT_EVENT = Event("scraping_result", doc="The run's verdict: its last line.", fields=(
    Field("success", "bool", "The run did what it was asked."),
    Field("totalScraped", "int", "Profiles collected (posts, for `profile_posts`).", optional=True),
    Field("completionReason", INSTAGRAM_SCRAPING_COMPLETION_REASON,
          "How the run ended: its surface reached or not, profiles or none.", optional=True, nullable=True),
    Field("error", "string", "What went wrong, for a person.", optional=True, nullable=True),
))

_EVENTS = (
    SCRAPING_RESULT_EVENT,
    Event("scraping_session", doc="The run's `scraping_sessions` row, as soon as it is written.", fields=(
        Field("scraping_id", "int", "The row's id: the desktop closes it if the bridge is killed."),
        Field("platform", OneOf(("instagram",)), "The platform of the row."),
    )),
    Event("target_info", doc="An account's list about to be read (`followers`, `following`).", fields=(
        Field("username", "string", "The account."),
        Field("available_count", "int", "What its profile announces."),
        Field("effective_max", "int", "What this run will read of it."),
        Field("scrape_type", OneOf(("followers", "following")), "The list."),
    )),
    Event("scraping_profile_visit", doc="A profile opened, before any filter.", fields=(
        Field("username", "string", "Its handle."),
        Field("is_business", "bool", "A business account."),
        Field("is_private", "bool", "A private account."),
        Field("is_verified", "bool", "A verified account."),
        Field("biography", "string", "Its bio.", optional=True),
        Field("followers_count", "int", "Its followers.", optional=True),
        Field("following_count", "int", "The accounts it follows.", optional=True),
        Field("posts_count", "int", "Its posts.", optional=True),
        Field("full_name", "string", "Its name.", optional=True),
        Field("business_category", "string", "Its business category.", optional=True),
    )),
    Event("profile_captured", doc="A profile collected.", fields=(
        Field("username", "string", "Its handle."),
        Field("full_name", "string", "Its name.", optional=True, nullable=True),
        Field("follower_count", "int", "Its followers.", optional=True, nullable=True),
        Field("following_count", "int", "The accounts it follows.", optional=True, nullable=True),
        Field("media_count", "int", "Its posts.", optional=True, nullable=True),
        Field("is_private", "bool", "A private account.", optional=True),
        Field("is_verified", "bool", "A verified account.", optional=True),
        Field("biography", "string", "Its bio.", optional=True, nullable=True),
        Field("profile_pic_url", "string", "Its picture, as a data URL.", optional=True),
    )),
    Event("profile_skipped", doc="A profile left out: known already, filtered, unreachable.", fields=(
        Field("username", "string", "Its handle."),
        Field("reason", "string", "Why, as a code the app translates or a filter's words."),
        Field("detail", "string", "A hint appended to the reason.", nullable=True),
    )),
    Event("scraping_dq_progress", doc="A deep qualification reading a following list.", fields=(
        Field("username", "string", "The profile qualified."),
        Field("count", "int", "Accounts read so far."),
        Field("max_count", "int", "Accounts it will read."),
    )),
    Event("post_url_found", doc="A hashtag post opened.", fields=(
        Field("url", "string", "Its link."),
        Field("hashtag", "string", "The hashtag walked."),
    )),
    Event("post_captured", doc="A post collected (`profile_posts`).", fields=(
        Field("username", "string", "Its author."),
        Field("post_url", "string", "Its link."),
        Field("likes_count", "int", "Its likes; null when unreadable.", nullable=True),
        Field("comments_count", "int", "Its comments; null when unreadable.", nullable=True),
    )),
    AI_PROFILE_START_EVENT,
    AI_PROFILE_DONE_EVENT,
    AI_ERROR_EVENT,
)

INSTAGRAM_SCRAPING = WorkflowContract(
    workflow_id="instagram.scraping.target",
    also=tuple(f"instagram.scraping.{kind}" for kind in SCRAPING_TYPES if kind != "target"),
    selector="type",
    name="InstagramScraping",
    bridge="scraping_bridge",
    doc="Collect profiles from accounts' lists, hashtags, posts or a list of names, or the posts of accounts.",
    launcher=f"{_SCRAPING}.agent_handler:run_instagram_scraping",
    reader=f"{_SCRAPING}.payload:scraping_config_from_payload",
    settings=_SETTINGS,
    bridge_fields=_BRIDGE_FIELDS,
    refusals=_REFUSALS,
    events=_EVENTS,
)

CONTRACTS = (INSTAGRAM_SCRAPING,)

__all__ = ["CONTRACTS", "INSTAGRAM_SCRAPING", "SCRAPING_TYPES"]
