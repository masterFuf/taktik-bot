"""`tt.engagement.target_profiles` plays the launcher of a TikTok « Ces comptes » run.

The action hands its params to `run_tiktok_target_profiles`, which reads them with the run's own
readers and builds `TargetProfilesWorkflow`: the config the workflow receives is the one a run
gets for the same page settings. Nothing is touched without an account or a list.
"""

from types import SimpleNamespace

import pytest

from bridges.tools.lab.actions.tiktok import engagement
from taktik.core.social_media.tiktok.workflows.automation.target_profiles import agent_handler


class _Stats:
    def __init__(self, **values):
        self._values = values

    def to_dict(self):
        return dict(self._values)


@pytest.fixture
def built(monkeypatch):
    """The workflows the production launcher builds, run without a phone."""
    workflows = []

    class _Workflow:
        def __init__(self, device, config):
            self.device, self.config = device, config
            workflows.append(self)

        def run(self, bot_username=None):
            self.bot_username = bot_username
            return _Stats(profiles_visited=2, likes=0, follows=0, errors=1, completion_reason="list_exhausted")

    monkeypatch.setattr(agent_handler, "_default_workflow_factory", lambda: _Workflow)
    monkeypatch.setattr(engagement, "open_bot_base", lambda: None)
    return workflows


def _bundle():
    return SimpleNamespace(device=SimpleNamespace(_device="raw-device"))


def test_visits_only_by_default(built):
    result = engagement.target_profiles(_bundle(), {"usernames": "@one, two,three", "account": "@operator"})

    (workflow,) = built
    assert workflow.device == "raw-device"
    assert workflow.bot_username == "operator"
    assert workflow.config.usernames == ["one", "two", "three"]
    assert workflow.config.max_followers == 3
    assert (workflow.config.like_probability, workflow.config.follow_probability,
            workflow.config.favorite_probability, workflow.config.story_like_probability) == (0, 0, 0, 0)
    assert workflow.config.max_posts_per_profile == 0
    assert result["success"] is True
    assert "2 visited" in result["message"] and "1 not reached" in result["message"]


def test_a_like_opens_the_asked_number_of_videos(built):
    engagement.target_profiles(_bundle(), {"usernames": "one", "account": "operator",
                                           "like_percentage": "100", "posts": "1"})

    (workflow,) = built
    assert workflow.config.like_probability == 1.0
    assert (workflow.config.min_posts_per_profile, workflow.config.max_posts_per_profile) == (1, 1)


@pytest.mark.parametrize("params", [{"usernames": "one"}, {"account": "operator"}])
def test_nothing_is_touched_without_an_account_or_a_list(built, params):
    result = engagement.target_profiles(_bundle(), params)

    assert built == []
    assert result["success"] is False


def test_the_open_profile_action_says_why_a_profile_was_not_opened():
    """`tt.search.open_user_profile`, the search each profile of the list goes through: its failure
    carries the reason the run tells the app, `not_found` only when the search established it."""
    from bridges.tools.lab.actions.tiktok.search import open_user_profile

    search = SimpleNamespace(navigate_to_user_profile=lambda _username: False,
                             last_profile_navigation_failure="not_found")

    result = open_user_profile(SimpleNamespace(search=search), {"username": "user_3"})

    assert result["success"] is False
    assert result["details"] == {"reason": "not_found", "accountNotFound": True}
