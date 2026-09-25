"""The one reading of a For You payload: units by vocabulary, defaults, free text kept as written."""
from dataclasses import asdict

import pytest

from taktik.core.social_media.tiktok.actions.business.workflows.for_you.models import ForYouConfig
from taktik.core.social_media.tiktok.actions.business.workflows.for_you.payload import (
    for_you_config_from_payload,
)


def test_an_empty_payload_gives_the_workflow_defaults():
    assert asdict(for_you_config_from_payload({})) == asdict(ForYouConfig())


@pytest.mark.parametrize("payload, expected", [
    ({"likeProbability": 1}, 0.01),
    ({"likeProbability": 30}, 0.3),
    ({"likeProbability": 0}, 0.0),
    ({"like_probability": 0.3}, 0.3),
    ({"like_probability": 30}, 0.3),
    ({"likeProbability": None}, 0.3),
    ({"likeProbability": 5, "like_probability": 0.9}, 0.05),
])
def test_a_probability_is_read_in_the_unit_of_its_vocabulary(payload, expected):
    assert for_you_config_from_payload(payload).like_probability == pytest.approx(expected)


def test_the_page_keys_that_the_cli_used_to_drop_are_read():
    config = for_you_config_from_payload({
        "commentProbability": 20,
        "maxCommentsPerSession": 4,
        "commentTexts": ["Nice one", "#love it, really"],
        "repostProbability": 10,
        "maxRepostsPerSession": 2,
        "trainingKeywords": ["running"],
        "trainingRejectOffNiche": False,
        "maxRejectionsPerSession": 7,
    })

    assert config.comment_probability == pytest.approx(0.2)
    assert config.max_comments_per_session == 4
    assert config.comment_texts == ["Nice one", "#love it, really"]
    assert config.repost_probability == pytest.approx(0.1)
    assert config.max_reposts_per_session == 2
    assert config.training_keywords == ["running"]
    assert config.training_reject_off_niche is False
    assert config.max_rejections_per_session == 7


def test_comment_texts_fall_back_to_the_older_comments_key():
    assert for_you_config_from_payload({"commentTexts": [], "comments": ["Hi"]}).comment_texts == ["Hi"]


def test_hashtags_lose_their_hash_because_the_filter_adds_it():
    config = for_you_config_from_payload({"requiredHashtags": ["#run", " trail "], "excludedHashtags": "ads, #promo"})

    assert config.required_hashtags == ["run", "trail"]
    assert config.excluded_hashtags == ["ads", "promo"]


def test_a_cli_string_of_keywords_is_split_on_commas():
    assert for_you_config_from_payload({"trainingKeywords": "running, trail"}).training_keywords == ["running", "trail"]
