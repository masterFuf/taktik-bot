"""Where a config keeps its filters must have exactly one answer.

This defect family has cost two runs already, and it is silent by construction: two
halves of a system read two shapes of the same setting, and as long as the operator
configures nothing both shapes hold the same values. The day a threshold is set, one
half honours it and the other keeps the defaults.
"""

import pytest

from taktik.core.shared.config import resolve_filter_criteria


FLAT = {"min_followers": 500, "max_followers": 9000}
NESTED = {"filters": {"min_followers": 500, "max_followers": 9000}}
REBUILT = {"filter_criteria": {"min_followers": 500, "max_followers": 9000}}


@pytest.mark.parametrize("config", [FLAT, NESTED, REBUILT], ids=["flat", "nested", "rebuilt"])
def test_every_shape_a_producer_uses_resolves_to_the_same_criteria(config):
    """The app, the scheduler, the CLI and the runners do not agree on the shape."""
    resolved = resolve_filter_criteria(config)
    assert resolved["min_followers"] == 500
    assert resolved["max_followers"] == 9000


def test_the_rebuilt_block_wins_over_the_plain_one():
    """Precedence, unchanged: a config rebuilt by a runner carries the effective values."""
    resolved = resolve_filter_criteria({
        "filters": {"min_followers": 10},
        "filter_criteria": {"min_followers": 500},
    })
    assert resolved["min_followers"] == 500


def test_a_nested_block_wins_over_a_flat_key():
    resolved = resolve_filter_criteria({"min_followers": 10, "filters": {"min_followers": 500}})
    assert resolved["min_followers"] == 500


def test_a_criterion_nobody_listed_here_still_reaches_its_reader():
    """A merge, not a reconstruction.

    The whitelist this replaces silently dropped every key it did not name, which is how
    the relationship flags got swallowed on the way to the workflow.
    """
    resolved = resolve_filter_criteria({"filters": {"some_future_criterion": 42}})
    assert resolved["some_future_criterion"] == 42


@pytest.mark.parametrize("config", [None, {}, {"filters": None}, {"filter_criteria": None}],
                         ids=["none", "empty", "null-filters", "null-criteria"])
def test_an_absent_or_empty_block_reads_as_no_criteria_never_as_none(config):
    """Callers used to guard this with `or {}` — some of them, which is the bug."""
    assert resolve_filter_criteria(config) == {}


def test_the_block_names_are_not_carried_into_the_result():
    resolved = resolve_filter_criteria({"filters": {"min_followers": 500}})
    assert "filters" not in resolved
    assert "filter_criteria" not in resolved


def test_the_builder_emits_a_shape_the_criteria_reader_understands():
    """End to end, on the real producer and the real reader.

    The app's filters used to be replaced by the dataclass defaults between the two.
    """
    from taktik.core.social_media.instagram.workflows.core.config_builder import (
        build_instagram_automation_config,
    )
    from taktik.core.social_media.instagram.workflows.management.config.config import (
        FilterCriteria,
    )

    built = build_instagram_automation_config({
        "workflowType": "target_followers",
        "target": "someone",
        "filters": {
            "minFollowers": 500,
            "maxFollowers": 9000,
            "minPosts": 12,
            "skipAlreadyFollowing": True,
        },
    })

    criteria = FilterCriteria.from_action(built["actions"][0])
    assert criteria.min_followers == 500
    assert criteria.max_followers == 9000
    assert criteria.min_posts == 12
    assert criteria.skip_already_following is True


def test_the_criteria_reader_accepts_a_nested_only_action():
    """A producer emitting one shape must not silently fall back to the defaults."""
    from taktik.core.social_media.instagram.workflows.management.config.config import (
        FilterCriteria,
    )

    criteria = FilterCriteria.from_action({"filters": {"min_followers": 500, "min_posts": 12}})
    assert criteria.min_followers == 500
    assert criteria.min_posts == 12
