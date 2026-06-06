"""D2 regression — `story_like` (front "likeStories") must survive the config build.

Before the fix, `ActionProbabilities` had no `story_like` field, so
`from_percentages`/`to_dict` silently dropped `story_like_percentage`. The story-like
probability therefore never reached the interaction engine for target/hashtag/post_url.
"""

import pytest

from taktik.core.social_media.instagram.workflows.management.config import (
    ActionProbabilities,
    WorkflowConfigBuilder,
)


def test_from_percentages_wires_story_like():
    p = ActionProbabilities.from_percentages({'story_like_percentage': 30})
    assert p.story_like == pytest.approx(0.30)


def test_to_dict_exposes_story_like_probability():
    p = ActionProbabilities.from_percentages({'story_like_percentage': 25})
    assert p.to_dict()['story_like_probability'] == pytest.approx(0.25)


def test_build_interaction_config_carries_story_like():
    action = {
        'probabilities': {
            'like_percentage': 80,
            'follow_percentage': 20,
            'story_like_percentage': 40,
        }
    }
    cfg = WorkflowConfigBuilder.build_interaction_config(action)
    assert cfg['story_like_probability'] == pytest.approx(0.40)


def test_story_like_defaults_when_absent():
    # Absent key falls back to the historical 10% default, never to a dropped key.
    cfg = WorkflowConfigBuilder.build_interaction_config({'probabilities': {}})
    assert cfg['story_like_probability'] == pytest.approx(0.10)
