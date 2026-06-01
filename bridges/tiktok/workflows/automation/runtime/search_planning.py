"""Planning helpers for TikTok search/hashtag bridge workflow."""

from __future__ import annotations

from typing import Any, Dict, List


def normalize_search_queries(config: Dict[str, Any]) -> List[str]:
    """Return a deduplicated list of search or hashtag queries."""
    workflow_type = str(config.get("workflowType") or "").strip().lower()
    raw_queries = config.get("hashtags") or config.get("searchQueries") or []

    if isinstance(raw_queries, str):
        raw_queries = [raw_queries]

    queries: List[str] = []
    for raw_query in raw_queries:
        query = str(raw_query or "").strip()
        if workflow_type == "hashtag":
            query = query.lstrip("#")
        if query and query not in queries:
            queries.append(query)

    if queries:
        return queries

    single_query = str(config.get("searchQuery") or "").strip()
    if workflow_type == "hashtag":
        single_query = single_query.lstrip("#")

    return [single_query] if single_query else []


def format_query_label(query: str, workflow_type: str) -> str:
    """Format a query for logs/status without changing the workflow payload."""
    return f"#{query}" if workflow_type == "hashtag" else query


__all__ = ["normalize_search_queries", "format_query_label"]
