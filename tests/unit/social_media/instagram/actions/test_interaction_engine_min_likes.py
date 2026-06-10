"""D1 regression — the `min_likes_per_profile` threshold must only gate the LIKE,
never short-circuit the follow / story blocks.

Before the fix, a failed/empty like (0 posts liked < min_likes) made
`_perform_interactions_on_profile` return early, so on EVERY workflow using the shared
interaction engine (target, hashtag, post_url, feed, notifications) the bot also stopped
following AND stopped watching stories. Users reported "interactions enabled but it never
interacts" — this locks the behaviour.
"""

import pytest

from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
    InteractionEngineMixin,
)
from taktik.core.social_media.instagram.actions.core.base_business.config_parsing import (
    ConfigParsingMixin,
)


class _Logger:
    def debug(self, *a, **k):
        pass

    def info(self, *a, **k):
        pass

    def error(self, *a, **k):
        pass


class _LikeBusiness:
    def __init__(self, posts_liked=0, posts_commented=0):
        self._result = {'posts_liked': posts_liked, 'posts_commented': posts_commented}
        self.calls = 0

    def like_profile_posts(self, *a, **k):
        self.calls += 1
        return self._result


class _ClickActions:
    def __init__(self, follow_ok=True):
        self.follow_ok = follow_ok
        self.follow_calls = 0

    def follow_user(self, username):
        self.follow_calls += 1
        return self.follow_ok


class _Engine(InteractionEngineMixin, ConfigParsingMixin):
    """Minimal harness: real decision (ConfigParsingMixin) + real engine, stubbed device IO."""

    def __init__(self, like_business, click_actions, story_result=None):
        self.logger = _Logger()
        self.like_business = like_business
        self.click_actions = click_actions
        self._story_result = story_result
        self.follow_events = []
        self.like_events = []
        self.recorded = []
        self.popups = 0

    def _emit_like_event(self, *a, **k):
        self.like_events.append(a)

    def _emit_follow_event(self, *a, **k):
        self.follow_events.append(a)

    def _record_action(self, *a, **k):
        self.recorded.append(a)

    def _handle_follow_suggestions_popup(self):
        self.popups += 1

    def _view_stories_on_current_profile(self, username, like_slot=-1, max_stories=3):
        return self._story_result


# Probabilities at 1.0 → percentage 100 → the random decision always plans the action.
def _cfg(**overrides):
    base = {
        'like_probability': 1.0,
        'follow_probability': 0.0,
        'comment_probability': 0.0,
        'story_probability': 0.0,
        'story_like_probability': 0.0,
        'min_likes_per_profile': 1,
    }
    base.update(overrides)
    return base


def test_follow_runs_even_when_like_yields_zero():
    like_biz = _LikeBusiness(posts_liked=0)
    clicks = _ClickActions(follow_ok=True)
    eng = _Engine(like_biz, clicks)

    res = eng._perform_interactions_on_profile(
        'alice', _cfg(follow_probability=1.0), profile_data=None
    )

    assert like_biz.calls == 1  # like was attempted
    assert clicks.follow_calls == 1  # follow STILL executed despite 0 likes
    assert res['follows'] == 1
    assert res['actually_interacted'] is True


def test_story_watched_even_when_like_yields_zero():
    like_biz = _LikeBusiness(posts_liked=0)
    clicks = _ClickActions(follow_ok=False)
    eng = _Engine(like_biz, clicks, story_result={'stories_viewed': 2, 'stories_liked': 0})

    res = eng._perform_interactions_on_profile(
        'bob', _cfg(story_probability=1.0), profile_data=None
    )

    assert res['stories'] == 2  # stories STILL watched despite 0 likes
    assert res['actually_interacted'] is True


def test_like_only_below_threshold_is_not_an_interaction():
    # Original intent preserved: a like-only plan with too few posts is not "interacted".
    like_biz = _LikeBusiness(posts_liked=0)
    clicks = _ClickActions(follow_ok=False)
    eng = _Engine(like_biz, clicks)

    res = eng._perform_interactions_on_profile('carol', _cfg(), profile_data=None)

    assert clicks.follow_calls == 0
    assert res['follows'] == 0
    assert res['actually_interacted'] is False


def test_successful_like_counts_and_emits():
    like_biz = _LikeBusiness(posts_liked=2)
    clicks = _ClickActions(follow_ok=False)
    eng = _Engine(like_biz, clicks)

    res = eng._perform_interactions_on_profile('dave', _cfg(), profile_data=None)

    assert res['likes'] == 2
    assert res['actually_interacted'] is True
    assert len(eng.like_events) == 1  # IPC like event emitted
