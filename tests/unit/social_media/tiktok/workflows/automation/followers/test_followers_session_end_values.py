"""A Followers session over several targets ends on the motive of its last target, with the
values of its sentence counted over the whole session, and a crashed target ends the session."""

from taktik.core.social_media.tiktok.workflows.automation.followers import FollowersStats
from taktik.core.social_media.tiktok.workflows.automation.followers.agent_handler import run_tiktok_followers


def _factory(endings):
    """Each target's workflow ends on the next `(reason, params, likes)` of `endings`."""
    created = []

    class _Workflow:
        def __init__(self, device, config):
            self.config = config
            created.append(self)

        def run(self, bot_username=None):
            reason, params, likes = endings[len(created) - 1]
            return FollowersStats(profiles_visited=1, likes=likes, completion_reason=reason,
                                  completion_reason_params=params)

    return _Workflow, created


def _payload(**extra):
    return {"targets": ["target_1", "target_2"], "maxFollowers": 10, "maxLikesPerSession": 4, **extra}


def test_a_crashed_target_ends_the_session_on_its_crash():
    factory, created = _factory([("crashed", {"error": "screen gone"}, 0), ("completed", {}, 0)])

    result = run_tiktok_followers(_payload(), device=object(), workflow_factory=factory,
                                  on_finished=lambda totals, targets: None)

    assert len(created) == 1, "the session went on after a crash"
    assert result["stats"]["completion_reason"] == "crashed"
    assert result["stats"]["completion_reason_params"] == {"error": "screen gone"}


def test_a_session_cap_counts_the_whole_session():
    factory, _created = _factory([("completed", {"interactions": 3}, 3),
                                  ("max_likes_reached", {"count": 1, "limit": 1}, 1)])

    result = run_tiktok_followers(_payload(), device=object(), workflow_factory=factory,
                                  on_finished=lambda totals, targets: None)

    assert result["stats"]["completion_reason"] == "max_likes_reached"
    assert result["stats"]["completion_reason_params"] == {"count": 4, "limit": 4}
