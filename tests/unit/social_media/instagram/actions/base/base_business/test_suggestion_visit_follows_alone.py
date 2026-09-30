"""The suggestions visit follows with no other gesture; no other pass does.

Rule 2 of `resolve_against_availability` drops a follow that would be the only gesture on a
profile. Since that rule came in (2026-09-05), the suggestions visit of a notifications scan --
follow 100 %, nothing else -- followed no one. That visit is the one pass whose job is to follow
in bulk: its interaction config grants it the right to follow alone, and every other config keeps
the rule. The engine is the real one; only the phone is stubbed (`test_interaction_engine_min_likes`).
"""

from taktik.core.social_media.instagram.workflows.common.interaction_config import (
    build_interaction_config,
)
from taktik.core.social_media.instagram.workflows.notifications import (
    DEFAULT_SUGGESTION_INTERACTION_CONFIG,
)

from test_interaction_engine_min_likes import _ClickActions, _Engine, _LikeBusiness

# A public profile with posts and no story: nothing is missing, the follow is simply alone.
_PROFILE = {'posts_count': 30, 'follow_button_state': 'follow'}


def _visit(config):
    clicks = _ClickActions(follow_ok=True)
    likes = _LikeBusiness()
    engine = _Engine(likes, clicks)
    result = engine._perform_interactions_on_profile('suggested_one', dict(config),
                                                     profile_data=dict(_PROFILE))
    return result, clicks, likes


def test_the_suggestions_visit_follows_the_account_it_opens():
    result, clicks, likes = _visit(DEFAULT_SUGGESTION_INTERACTION_CONFIG)

    assert clicks.follow_calls == 1
    assert result['follows'] == 1
    # Still nothing else: the visit is about acquisition.
    assert likes.calls == 0
    assert result['stories'] == 0


def test_an_automation_follow_still_never_lands_alone():
    config = build_interaction_config({
        'like_probability': 0.0, 'follow_probability': 1.0,
        'comment_probability': 0.0, 'story_probability': 0.0,
    })

    result, clicks, _likes = _visit(config)

    assert clicks.follow_calls == 0
    assert result['follows'] == 0
