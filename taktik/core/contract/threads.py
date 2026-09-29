"""Threads workflows of the `threads_bridge` dispatcher: the search (follow) and the feed.

Both read the same settings (`threads_*_config_from_payload`), two of them as nested objects: the
chance of each action and the profile filters. A nested object is a group: the keys under it are
declared one by one, each with the attribute of the config it sets.
"""

from __future__ import annotations

from .schema import HOST, Event, Field, ListOf, OneOf, Refusal, Shape, WorkflowContract
from .shared import ERROR_EVENT, LOG_EVENT, STATUS_EVENT

_HANDLER = "taktik.core.social_media.threads.workflows.agent_handler"

ACTION_PROBABILITIES = Shape(
    name="ThreadsActionProbabilities",
    doc="The chance of each action on a visited profile, in percent (0: never, 100: always).",
    fields=(
        Field("follow", "int", "Follow the profile.", default=80, attr="actions.follow"),
        Field("like", "int", "Like its recent posts, up to `maxLikesPerProfile`.", default=50, attr="actions.like"),
        Field("repost", "int", "Repost its latest post.", default=0, attr="actions.repost"),
        Field("comment", "int", "Comment: read, not wired yet (the run only logs it).", default=0,
              attr="actions.comment"),
    ),
)

PROFILE_FILTERS = Shape(
    name="ThreadsProfileFilters",
    doc="A visited profile outside these is skipped.",
    fields=(
        Field("minFollowers", "int", "Fewest followers.", default=0, attr="filters.min_followers"),
        Field("maxFollowers", "int", "Most followers.", default=10_000_000, attr="filters.max_followers"),
        Field("bioKeywordsInclude", ListOf("string"), "The bio holds one of these.", default=(),
              attr="filters.bio_keywords_include"),
        Field("bioKeywordsExclude", ListOf("string"), "The bio holds none of these.", default=(),
              attr="filters.bio_keywords_exclude"),
    ),
)

#: What both workflows read, with the reader's defaults.
COMMON_SETTINGS = (
    Field("deviceId", "string", "The adb serial of the phone; read by the dispatcher too.", default="agent",
          aliases=("device_id",), attr="device_id", by=HOST),
    Field("maxProfiles", "int", "Profiles to visit.", default=10, aliases=("maxFollows",), attr="max_profiles"),
    Field("minDelaySeconds", "number", "Shortest pause between two profiles, in seconds.", default=2.0,
          attr="min_delay_seconds"),
    Field("maxDelaySeconds", "number", "Longest pause between two profiles, in seconds.", default=5.0,
          attr="max_delay_seconds"),
    Field("maxLikesPerProfile", "int", "Most posts liked on one profile.", default=2, attr="max_likes_per_profile"),
    Field("actionProbabilities", ACTION_PROBABILITIES, "The chance of each action.", aliases=("actions",)),
    Field("filters", PROFILE_FILTERS, "Which visited profiles to act on."),
)

RUN_STATS = Shape(
    name="ThreadsRunStats",
    doc="`InteractStats.as_dict()`: the run's counters.",
    fields=tuple(Field(name, "int", doc) for name, doc in (
        ("profiles_visited", "Profiles opened."),
        ("profiles_interacted", "Follows, likes, reposts and replies together."),
        ("profiles_filtered", "Profiles the filters refused."),
        ("private_profiles", "Private profiles met."),
        ("likes", "Posts liked."),
        ("follows", "Profiles followed."),
        ("reposts", "Posts reposted."),
        ("replies", "Replies written."),
        ("errors", "Errors."),
    )),
)

EVENTS = (
    STATUS_EVENT,
    ERROR_EVENT,
    LOG_EVENT,
    Event("threads_stats", doc="The run's counters, after each profile and at the end.", fields=(
        Field("stats", RUN_STATS, "The counters."),
    )),
    Event("threads_profile_visit", doc="A profile was opened.", fields=(
        Field("username", "string", "Its handle."),
        Field("followers", "int", "Its followers, when read.", nullable=True),
        Field("is_private", "bool", "A private profile."),
    )),
    Event("threads_action", doc="An action on the profile being visited.", fields=(
        Field("action", OneOf(("follow", "like", "repost")), "What was done."),
        Field("username", "string", "The profile's handle."),
        Field("details", "json", "What was read of the profile (and the post's rank for a like).",
              optional=True),
    )),
)


def _workflow_type(values, doc: str, **kwargs) -> Field:
    return Field("workflowType", OneOf(values), doc, **kwargs)


THREADS_SEARCH = WorkflowContract(
    workflow_id="threads.automation.follow",
    name="ThreadsSearch",
    bridge="threads_bridge",
    doc="Search Threads for a query, then act on the profiles it finds.",
    launcher=f"{_HANDLER}:run_threads_search",
    reader=f"{_HANDLER}:threads_search_config_from_payload",
    settings=(
        Field("searchQuery", "string", "What to search for, without @. When it is absent, `targets` or "
              "`targetAccounts` (a list: its first entry) are read.", required=True,
              aliases=("search_query", "target", "username", "targets", "targetAccounts"), attr="search_query"),
        *COMMON_SETTINGS,
    ),
    bridge_fields=(_workflow_type(("follow",), "Which workflow of the dispatcher runs.",
                                  default="follow"),),
    refusals=(Refusal("searchQuery", doc="Nothing to search for."),),
    events=EVENTS,
)

THREADS_FEED = WorkflowContract(
    workflow_id="threads.automation.feed",
    name="ThreadsFeed",
    bridge="threads_bridge",
    doc="Walk the home feed and act on the authors of its posts.",
    launcher=f"{_HANDLER}:run_threads_feed",
    reader=f"{_HANDLER}:threads_feed_config_from_payload",
    settings=COMMON_SETTINGS,
    bridge_fields=(_workflow_type(("feed",), "Which workflow of the dispatcher runs; without it, the search.",
                                  required=True),),
    events=EVENTS,
)

CONTRACTS = (THREADS_SEARCH, THREADS_FEED)

__all__ = ["CONTRACTS", "THREADS_FEED", "THREADS_SEARCH"]
