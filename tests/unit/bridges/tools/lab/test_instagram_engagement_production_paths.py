"""The Lab's engagement actions run the functions the workflows run, not a parallel engine.

Three of them tested code no workflow calls: `engagement.view_profile_stories` drove
`StoryBusiness.view_profile_stories` while every profile visit watches stories through
`InteractionEngineMixin._view_stories_on_current_profile`; `engagement.engage_likers` and
`engagement.has_likes` drove `UIHelpers`, which the automation builds and never calls, while the
feed, hashtag and post URL workflows walk likers through `LikersWorkflowBase._interact_with_likers_list`
and gate on `_find_like_count_element`. A green Lab run then said nothing about production.
"""

from types import SimpleNamespace

import pytest

from bridges.tools.lab.actions.instagram import engagement


def _refuse(name):
    def refused(*_a, **_k):
        raise AssertionError(f"{name} is not the production path")
    return refused


def test_profile_stories_are_watched_by_the_engine_of_every_profile_visit():
    calls = []

    def watch(username, **kwargs):
        calls.append((username, kwargs))
        return {"stories_viewed": 3, "stories_liked": 1}

    bundle = SimpleNamespace(
        popup=SimpleNamespace(_view_stories_on_current_profile=watch),
        story=SimpleNamespace(view_profile_stories=_refuse("StoryBusiness.view_profile_stories")),
    )

    result = engagement.view_profile_stories(
        bundle, {"username": "@someone", "max_stories": "4", "story_like": "1", "max_story_likes": "2"})

    assert calls == [("someone", {"do_story_like": True, "max_story_likes": 2, "max_stories": 4})]
    assert result["success"] is True
    assert result["details"] == {"stories_viewed": 3, "stories_liked": 1}


def test_a_profile_without_a_watched_story_is_not_a_success():
    bundle = SimpleNamespace(popup=SimpleNamespace(_view_stories_on_current_profile=lambda *_a, **_k: None))

    result = engagement.view_profile_stories(bundle, {})

    assert result["success"] is False
    assert "no story watched" in result["message"]


def test_likers_are_walked_by_the_loop_of_the_workflows():
    calls = []

    def walk(**kwargs):
        calls.append(kwargs)
        kwargs["stats"]["users_interacted"] = 2
        kwargs["stats"]["follows_made"] = 2

    feed = SimpleNamespace(default_config={"like_percentage": 35, "comment_percentage": 10},
                           _interact_with_likers_list=walk)
    bundle = SimpleNamespace(feed=feed)

    result = engagement.engage_likers(bundle, {"max_interactions": "3", "follow_percentage": "100"})

    assert len(calls) == 1
    call = calls[0]
    assert call["max_interactions"] == 3
    assert call["source_type"] == "FEED"
    # The page's percentages, 0-100 as the workflows read them; what is not given stays the feed's.
    assert call["effective_config"]["follow_percentage"] == 100
    assert call["effective_config"]["like_percentage"] == 35
    assert result["success"] is True
    assert result["details"]["users_interacted"] == 2


def test_no_liker_engaged_is_a_failure():
    feed = SimpleNamespace(default_config={}, _interact_with_likers_list=lambda **_k: None)

    assert engagement.engage_likers(SimpleNamespace(feed=feed), {})["success"] is False


@pytest.mark.parametrize("element, answer", [(object(), True), (None, False)], ids=["counter", "none"])
def test_has_likes_is_the_gate_of_the_likers_popup(element, answer):
    bundle = SimpleNamespace(popup=SimpleNamespace(_find_like_count_element=lambda: element))

    assert engagement.has_likes(bundle, {}) is answer


def test_the_lab_no_longer_reaches_ui_helpers():
    assert not hasattr(engagement, "_ui_helpers")


def test_the_two_unreachable_engines_are_gone():
    """`UIHelpers` (built by the automation, never called) and `StoryBusiness.view_profile_stories`
    (no workflow, no Lab action) were removed: no second likers/stories engine is left to drift."""
    import importlib.util

    from taktik.core.social_media.instagram.services.story import StoryBusiness
    from taktik.core.social_media.instagram import workflows

    assert importlib.util.find_spec("taktik.core.social_media.instagram.workflows.common.ui_helpers") is None
    assert not hasattr(workflows, "UIHelpers")
    assert not hasattr(StoryBusiness, "view_profile_stories")
