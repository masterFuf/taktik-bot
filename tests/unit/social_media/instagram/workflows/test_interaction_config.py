"""What a workflow does when the operator sets nothing.

These fifteen keys were read and defaulted inline in each interaction workflow. Recopied,
the block drifts in silence: a default changed in one workflow keeps its old value in the
others, and nothing fails — the runs simply behave differently, for a reason no reader can
see from the code.

The defaults asserted below are the historical ones. They are pinned because they ARE the
product behaviour of an unconfigured run, not an implementation detail.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.common.interaction_config import (
    build_interaction_config,
)


HISTORICAL_DEFAULTS = {
    'like_probability': 0.8,
    'follow_probability': 0.2,
    'comment_probability': 0.1,
    'story_probability': 0.2,
    'story_like_probability': 0.0,
    'min_likes_per_profile': 1,
    'max_likes_per_profile': 3,
    'max_comments_per_profile': 1,
    'max_stories_per_profile': 3,
    'max_story_likes_per_profile': 1,
    'ai_decision_mode': None,
    'ai_decision_dry_run': True,
    'ai_decision_capabilities': None,
}


@pytest.mark.parametrize("key,expected", sorted(HISTORICAL_DEFAULTS.items()))
def test_an_unconfigured_run_keeps_its_historical_default(key, expected):
    assert build_interaction_config({})[key] == expected


def test_the_operator_always_wins_over_the_default():
    built = build_interaction_config({'like_probability': 0.0, 'follow_probability': 1.0})
    assert built['like_probability'] == 0.0   # not the 0.8 default, and not falsy-coerced
    assert built['follow_probability'] == 1.0
    assert built['comment_probability'] == 0.1  # untouched keys keep theirs


def test_ai_dry_run_can_be_turned_off():
    """`True` by default, so a config that says False must not be read as 'unset'."""
    assert build_interaction_config({'ai_decision_dry_run': False})['ai_decision_dry_run'] is False


@pytest.mark.parametrize("empty", [None, {}])
def test_no_config_is_not_a_crash(empty):
    built = build_interaction_config(empty)
    assert set(built) == set(HISTORICAL_DEFAULTS) | {'filter_criteria'}


def test_filter_criteria_is_always_resolved():
    """The key must exist even with no config: the workflows index into it directly."""
    assert build_interaction_config({})['filter_criteria'] is not None
