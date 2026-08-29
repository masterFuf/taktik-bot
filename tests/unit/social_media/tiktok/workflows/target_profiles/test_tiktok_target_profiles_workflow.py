"""The target-profiles workflow engages the people it was given — and nobody else.

A hand-picked list is the one place where "close enough" is a real failure: the operator named
twelve accounts, and engaging a thirteenth is engaging a stranger under their name. So the tests
here are about identity and attribution rather than about interaction, which is the followers
workflow's own tested body, reused unchanged.
"""

from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import (
    FollowersStats,
)
from taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow import (
    FollowersWorkflow,
)
from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles import (
    TargetProfilesConfig,
    TargetProfilesWorkflow,
)


def _workflow(**config_kwargs) -> TargetProfilesWorkflow:
    """A workflow instance without a device — only the list/attribution logic is exercised."""
    workflow = TargetProfilesWorkflow.__new__(TargetProfilesWorkflow)
    workflow.config = TargetProfilesConfig(**config_kwargs)
    return workflow


# --- the list ------------------------------------------------------------------------------


def test_the_list_is_normalised_and_kept_in_order():
    workflow = _workflow(usernames=["@Marie", "paul", "  jules  "])
    assert workflow._resolve_targets() == ["Marie", "paul", "jules"]


def test_the_same_person_is_not_visited_twice():
    """Case and at-sign are spelling, not identity — a list that names one person three times
    must cost one visit, not three."""
    workflow = _workflow(usernames=["@marie", "Marie", "MARIE"])
    assert workflow._resolve_targets() == ["marie"]


def test_empty_entries_are_dropped_rather_than_searched():
    workflow = _workflow(usernames=["", "   ", "@", None, "marie"])
    assert workflow._resolve_targets() == ["marie"]


# --- attribution ---------------------------------------------------------------------------


def test_a_rejected_profile_is_not_filed_under_somebody_s_followers():
    """`filtered_profiles` records WHERE a profile came from. Filing a hand-picked account as a
    follower of the last searched target is what makes the reject stats unreadable."""
    workflow = _workflow(usernames=["marie"])
    assert workflow.FILTER_SOURCE_TYPE == "selection"
    assert workflow._filter_source_name == "target_profiles"

    assert FollowersWorkflow.FILTER_SOURCE_TYPE == "followers"


def test_the_run_is_filed_under_its_own_workflow_type():
    """Sharing `followers` would merge two different questions in every grouping the app does
    on that column — the same footgun the session_name spelling already caused once."""
    calls = {}

    class _Repo:
        def create_session(self, **kwargs):
            calls.update(kwargs)

            class _Ref:
                account_id = 7
                session_id = 42

            return _Ref()

    workflow = _workflow(usernames=["marie"])
    workflow._followers_repository = _Repo()
    workflow.logger = _SilentLogger()

    workflow._open_session("bot", ["marie", "paul"])

    assert calls["workflow_type"] == "target_profiles"
    assert calls["session_name"] == "Target Profiles"
    assert workflow._account_id == 7
    assert workflow._session_id == 42


def test_no_bot_username_means_no_session_and_no_crash():
    workflow = _workflow(usernames=["marie"])
    workflow._followers_repository = None  # would raise if touched
    workflow._open_session(None, ["marie"])


# --- skipping ------------------------------------------------------------------------------


class _SilentLogger:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _SkipRepo:
    def __init__(self, *, recent=False, filtered=False):
        self._recent = recent
        self._filtered = filtered

    def has_recent_interaction(self, **_kwargs):
        return self._recent

    def is_profile_filtered(self, **_kwargs):
        return self._filtered


def _skippable(workflow, repo):
    workflow._followers_repository = repo
    workflow._account_id = 1
    workflow._processed_usernames = set()
    workflow.logger = _SilentLogger()
    workflow.stats = FollowersStats()
    workflow._send_stats_update = lambda: None
    workflow._on_action_callback = None
    return workflow


def test_a_profile_already_interacted_with_this_week_is_skipped_before_any_navigation():
    """The check costs a DB read; letting it through costs a search, a profile screen and an AI
    call, to reach the same verdict."""
    workflow = _skippable(_workflow(usernames=["marie"]), _SkipRepo(recent=True))
    assert workflow._should_skip("marie") is True
    assert workflow.stats.skipped == 1


def test_a_profile_already_rejected_is_skipped_only_when_filters_are_on():
    """With no filters configured there is no such thing as "already rejected" — re-checking
    would import a verdict from a run that had different criteria."""
    workflow = _skippable(_workflow(usernames=["marie"]), _SkipRepo(filtered=True))
    assert workflow._should_skip("marie") is False

    workflow = _skippable(
        _workflow(usernames=["marie"], filters={"min_followers": 100}), _SkipRepo(filtered=True)
    )
    assert workflow._should_skip("marie") is True
    assert workflow.stats.profiles_filtered == 1


def test_the_same_handle_twice_in_one_run_is_handled_once():
    workflow = _skippable(_workflow(usernames=["marie"]), _SkipRepo())
    assert workflow._should_skip("marie") is False
    assert workflow._should_skip("@Marie") is True


def test_an_unreadable_history_does_not_skip_the_profile():
    """A DB error is not a verdict. Treating it as one would silently empty a run."""

    class _BrokenRepo:
        def has_recent_interaction(self, **_kwargs):
            raise RuntimeError("db locked")

        def is_profile_filtered(self, **_kwargs):
            raise RuntimeError("db locked")

    workflow = _skippable(
        _workflow(usernames=["marie"], filters={"min_followers": 100}), _BrokenRepo()
    )
    assert workflow._should_skip("marie") is False


# --- the shared body -----------------------------------------------------------------------


def test_the_per_profile_body_is_the_followers_one():
    """Not "an equivalent one". Two copies drift, and the copy that drifts is the one that stops
    recording interactions."""
    assert (
        TargetProfilesWorkflow._process_current_profile
        is FollowersWorkflow._process_current_profile
    )


def test_a_budget_is_still_a_budget():
    """`max_followers` keeps its meaning so every inherited limit and progress log reads right."""
    workflow = _workflow(usernames=["a", "b", "c"], max_followers=2)
    assert workflow.config.max_followers == 2
