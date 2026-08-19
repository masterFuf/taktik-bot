"""The profile ceiling and the profile counter must measure the same thing.

`total_profiles_limit` comes from the page's "max profiles" field, and `profiles_processed` is
incremented once per person actually interacted with. As long as both count PEOPLE they agree.

The feed is the exception, and it is the reason this file exists. Its page fills `maxProfiles`
with the number of POSTS to browse, so the ceiling arrives in the wrong unit. That was harmless
while nothing ever incremented the counter -- the guard was simply dead. The moment walking a
post's likers started feeding it, a 30-post feed run visiting 5 likers each would have stopped
after six posts, on a limit the operator never set in those units.

So the feed publishes no profile ceiling, and these tests pin that down: getting it wrong again
is silent, and only shows up as runs that end far too early.
"""

from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
)


def _limits(workflow_type: str, max_profiles: int = 30) -> dict:
    config = build_instagram_automation_config({
        "workflowType": workflow_type,
        "target": "someone",
        "limits": {"maxProfiles": max_profiles},
    })
    return config["session_settings"]


def test_the_feed_publishes_no_profile_ceiling():
    # Its budget is the action's max_interactions, counted in posts.
    assert _limits("feed")["total_profiles_limit"] == 0


def test_the_feed_still_carries_its_post_budget():
    config = build_instagram_automation_config({
        "workflowType": "feed",
        "target": "auto",
        "limits": {"maxProfiles": 30},
    })
    action = config["actions"][0]

    assert action["max_interactions"] == 30
    assert action["max_posts_to_check"] == 30


def test_profile_walking_workflows_keep_their_ceiling():
    # These count people, so the operator's number applies as-is.
    for workflow_type in ("target_followers", "target_following", "target_profiles",
                          "hashtags", "post_url"):
        assert _limits(workflow_type)["total_profiles_limit"] == 30, workflow_type


def test_the_ceiling_follows_the_operator_number():
    assert _limits("target_followers", max_profiles=7)["total_profiles_limit"] == 7
