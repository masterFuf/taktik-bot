"""La recherche par hashtag applique les hashtags requis et exclus, avec la règle du Pour toi.

La page Hashtag TikTok et le nœud du planificateur envoient `requiredHashtags` /
`excludedHashtags`. Un run hashtag part vers `run_search_workflow`, qui ne les lisait pas : seul le
Pour toi les appliquait. Relevé par le test de contrat des configurations le 2026-09-24.

Le filtre n'est pas réécrit : celui du Pour toi est remonté dans `BaseVideoWorkflow`, et les deux
fils le partagent. Le dernier test tient cette promesse — même légende, même verdict.
"""

import pytest

from bridges.tiktok.workflows.automation.runtime.search_config import build_search_config
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.models import ForYouConfig
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow import ForYouWorkflow
from taktik.core.social_media.tiktok.actions.business.workflows.search.models import SearchConfig
from taktik.core.social_media.tiktok.actions.business.workflows.search.workflow import SearchWorkflow


def _search(**config) -> SearchWorkflow:
    workflow = SearchWorkflow.__new__(SearchWorkflow)
    workflow.config = SearchConfig(search_query="cuisine", **config)
    return workflow


def _for_you(**config) -> ForYouWorkflow:
    workflow = ForYouWorkflow.__new__(ForYouWorkflow)
    workflow.config = ForYouConfig(**config)
    return workflow


def _video(description: str) -> dict:
    return {"description": description, "like_count": "120", "is_liked": False}


def test_the_hashtag_page_payload_reaches_the_search_config():
    # Ce que TikTokHashtag.tsx et le runner du planificateur envoient (tags sans `#`).
    config = build_search_config(
        SearchConfig,
        {
            "workflowType": "hashtag",
            "hashtags": ["cuisine"],
            "requiredHashtags": ["recette", "food"],
            "excludedHashtags": ["pub"],
        },
        "cuisine",
        max_videos=10,
        remaining_likes=5,
        remaining_follows=2,
    )

    assert config.required_hashtags == ["recette", "food"]
    assert config.excluded_hashtags == ["pub"]


def test_a_search_payload_without_the_lists_filters_nothing():
    config = build_search_config(SearchConfig, {"workflowType": "search"}, "chef", 10, 5, 2)

    assert config.required_hashtags == []
    assert config.excluded_hashtags == []
    assert _search()._should_skip_video(_video("anything at all")) is False


def test_the_search_skips_a_video_without_a_required_hashtag():
    workflow = _search(required_hashtags=["recette"])

    assert workflow._should_skip_video(_video("Mon plat du jour #cuisine")) is True
    assert workflow._should_skip_video(_video("Mon plat du jour #Recette #cuisine")) is False


def test_the_search_skips_a_video_carrying_an_excluded_hashtag():
    workflow = _search(excluded_hashtags=["pub"])

    assert workflow._should_skip_video(_video("Nouveau robot #cuisine #PUB")) is True
    assert workflow._should_skip_video(_video("Nouveau robot #cuisine")) is False


@pytest.mark.parametrize(
    "description",
    [
        "",
        "sans hashtag",
        "#recette maison",
        "#pub #recette",
        "#food et #pub",
        "#FOOD",
        "recette sans dièse",
    ],
)
def test_for_you_and_search_give_the_same_verdict(description):
    lists = {"required_hashtags": ["recette", "food"], "excluded_hashtags": ["pub"]}

    assert _search(**lists)._rejected_by_hashtags(_video(description)) == \
        _for_you(**lists)._rejected_by_hashtags(_video(description))
    assert _search(**lists)._should_skip_video(_video(description)) == \
        _for_you(**lists)._should_skip_video(_video(description))
