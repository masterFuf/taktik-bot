from taktik.core.social_media.tiktok.actions.business.workflows.search.payload import (
    search_queries_from_payload,
)


def test_normalize_search_queries_uses_hashtags_array_for_hashtag_workflow():
    queries = search_queries_from_payload(
        {
            "workflowType": "hashtag",
            "hashtags": ["#viral", "fyp", "viral", "  #trend  "],
        },
        hashtag=True,
    )

    assert queries == ["viral", "fyp", "trend"]


def test_normalize_search_queries_falls_back_to_search_query():
    queries = search_queries_from_payload(
        {
            "workflowType": "hashtag",
            "searchQuery": "#motivation",
        },
        hashtag=True,
    )

    assert queries == ["motivation"]


def test_normalize_search_queries_keeps_raw_search_for_generic_search_workflow():
    queries = search_queries_from_payload(
        {
            "workflowType": "search",
            "searchQueries": ["@creator", "marketing tips"],
        },
        hashtag=False,
    )

    assert queries == ["@creator", "marketing tips"]


def test_the_older_single_query_names_are_still_read():
    assert search_queries_from_payload({"target": "@creator"}, hashtag=False) == ["@creator"]
    assert search_queries_from_payload({"username": "chef"}, hashtag=False) == ["chef"]
    assert search_queries_from_payload({"hashtag": "#food"}, hashtag=True) == ["food"]
    assert search_queries_from_payload({}, hashtag=False) == []
