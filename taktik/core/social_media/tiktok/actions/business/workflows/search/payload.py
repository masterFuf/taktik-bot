"""One reading of a TikTok Search or Hashtag payload, for the bridge and the Agent handler alike.

The bridge read a list of queries (`hashtags`, `searchQueries`) and shared the video budget
between them; the Agent handler, which the CLI runs, read one query and an older subset of the
settings. The settings are those of every video workflow (`_internal/video_payload.py`); this
module reads the queries and builds the config of one query of the session.
"""

from __future__ import annotations

from typing import Any, Mapping

from .models import SearchConfig


def search_queries_from_payload(payload: Mapping[str, Any], *, hashtag: bool) -> list[str]:
    """The run's queries, in order, without duplicates; hashtags lose their "#".

    A list (`hashtags`, `searchQueries`) wins; otherwise the single query, under the page's name
    (`searchQuery`) or the older ones an Agent plan or a CLI call may carry.
    """
    raw_queries = payload.get("hashtags") or payload.get("searchQueries") or []
    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]

    queries: list[str] = []
    for raw_query in raw_queries:
        query = str(raw_query or "").strip()
        if hashtag:
            query = query.lstrip("#")
        if query and query not in queries:
            queries.append(query)
    if queries:
        return queries

    single = (
        payload.get("searchQuery")
        or payload.get("search_query")
        or payload.get("target")
        or payload.get("username")
        or payload.get("hashtag")
    )
    if isinstance(single, (list, tuple)):
        single = single[0] if single else ""
    single_query = str(single or "").strip()
    if hashtag:
        single_query = single_query.lstrip("#")
    return [single_query] if single_query else []


def query_label(query: str, workflow_type: str) -> str:
    """How a query is shown in logs and statuses; the query itself is not changed."""
    return f"#{query}" if workflow_type == "hashtag" else query


def search_config_for_query(
    settings: Mapping[str, Any],
    *,
    search_query: str,
    max_videos: int,
    max_likes_per_session: int,
    max_follows_per_session: int,
) -> SearchConfig:
    """The config of one query: the run's settings, this query's share of the budget."""
    return SearchConfig(**{
        **settings,
        "search_query": search_query,
        "max_videos": max_videos,
        "max_likes_per_session": max_likes_per_session,
        "max_follows_per_session": max_follows_per_session,
    })


__all__ = ["query_label", "search_config_for_query", "search_queries_from_payload"]
