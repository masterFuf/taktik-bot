from bridges.tiktok.workflows.automation.search import _normalize_search_queries


def test_normalize_search_queries_uses_hashtags_array_for_hashtag_workflow():
    queries = _normalize_search_queries(
        {
            "workflowType": "hashtag",
            "hashtags": ["#viral", "fyp", "viral", "  #trend  "],
        }
    )

    assert queries == ["viral", "fyp", "trend"]


def test_normalize_search_queries_falls_back_to_search_query():
    queries = _normalize_search_queries(
        {
            "workflowType": "hashtag",
            "searchQuery": "#motivation",
        }
    )

    assert queries == ["motivation"]


def test_normalize_search_queries_keeps_raw_search_for_generic_search_workflow():
    queries = _normalize_search_queries(
        {
            "workflowType": "search",
            "searchQueries": ["@creator", "marketing tips"],
        }
    )

    assert queries == ["@creator", "marketing tips"]
