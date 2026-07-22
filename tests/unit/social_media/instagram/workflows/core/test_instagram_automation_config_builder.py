import pytest

from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
    build_instagram_session_config_event,
)


def test_builds_target_followers_config_with_limits_and_targets():
    config = build_instagram_automation_config(
        {
            "workflowType": "target_followers",
            "target": "alpha, beta",
            "limits": {
                "maxProfiles": 10,
                "minLikesPerProfile": 1,
                "maxLikesPerProfile": 3,
            },
            "probabilities": {
                "like": 50,
                "follow": 30,
                "comment": 10,
                "watchStories": 20,
                "likeStories": 5,
            },
            "filters": {
                "minFollowers": 100,
                "maxFollowers": 5000,
                "minPosts": 4,
                "maxFollowing": 800,
            },
            "session": {
                "durationMinutes": 45,
                "minDelay": 2,
                "maxDelay": 6,
                "maxConsecutiveKnownUsernames": 0,
            },
            "comments": {
                "customComments": ["nice"],
            },
        }
    )

    assert config["session_settings"]["workflow_type"] == "target_followers"
    assert config["session_settings"]["total_follows_limit"] == 3
    assert config["session_settings"]["total_likes_limit"] == 15
    assert config["session_settings"]["max_consecutive_known_usernames"] == 1
    assert config["filters"]["min_followers"] == 100

    action = config["actions"][0]
    assert action["type"] == "interact_with_followers"
    assert action["target_username"] == "alpha"
    assert action["target_usernames"] == ["alpha", "beta"]
    assert action["probabilities"]["like_percentage"] == 50
    assert action["comment_settings"]["custom_comments"] == ["nice"]


def test_builds_feed_config_with_story_settings():
    config = build_instagram_automation_config(
        {
            "workflowType": "feed",
            "target": "feed",
            "limits": {
                "maxProfiles": 7,
                "maxFeedStoryProfiles": 4,
            },
            "probabilities": {
                "like": 80,
                "feedStoryReaction": 25,
                "watchStories": 0,
                "likeStories": 15,
            },
            "filters": {
                "minPostLikes": 10,
                "maxPostLikes": 200,
            },
            "feedStories": {
                "enabled": True,
                "reaction": "fire",
            },
        }
    )

    assert config["session_settings"]["workflow_type"] == "feed"
    action = config["actions"][0]
    assert action["type"] == "feed"
    assert action["max_interactions"] == 7
    assert action["view_feed_stories"] is True
    assert action["max_feed_story_profiles"] == 4
    assert action["feed_story_reaction_percentage"] == 25
    assert action["feed_story_reaction"] == "fire"
    assert action["min_post_likes"] == 10
    assert action["max_post_likes"] == 200


def test_builds_sync_followers_following_config_with_mode():
    config = build_instagram_automation_config(
        {
            "workflowType": "sync_followers_following",
            "target": "self",
            "sync": {
                "mode": "full",
            },
        }
    )

    assert config["session_settings"]["workflow_type"] == "sync_following"
    assert config["actions"] == [
        {
            "type": "sync_followers_following",
            "mode": "full",
        }
    ]


def test_builds_session_config_event_with_optional_ai_payload():
    payload = build_instagram_session_config_event(
        {
            "deviceId": "device-1",
            "workflowType": "target_followers",
            "target": "alpha",
            "limits": {
                "maxProfiles": 9,
                "maxLikesPerProfile": 3,
            },
            "probabilities": {
                "like": 70,
                "follow": 40,
                "comment": 20,
                "watchStories": 10,
                "likeStories": 5,
            },
            "filters": {
                "minFollowers": 20,
                "maxFollowers": 2000,
                "minPosts": 2,
                "maxFollowing": 700,
            },
            "session": {
                "durationMinutes": 30,
                "minDelay": 4,
                "maxDelay": 8,
                "maxNoNewUsernamesScrolls": 6,
            },
            "ai": {
                "smartComments": True,
                "profileAnalysis": False,
                "postAnalysis": True,
            },
        },
        ai_enabled=True,
    )

    assert payload == {
        "deviceId": "device-1",
        "workflowType": "target_followers",
        "target": "alpha",
        "limits": {
            "maxProfiles": 9,
            "maxLikesPerProfile": 3,
        },
        "probabilities": {
            "like": 70,
            "follow": 40,
            "comment": 20,
            "watchStories": 10,
            "likeStories": 5,
        },
        "filters": {
            "minFollowers": 20,
            "maxFollowers": 2000,
            "minPosts": 2,
            "maxFollowing": 700,
        },
        "session": {
            "durationMinutes": 30,
            "minDelay": 4,
            "maxDelay": 8,
            "maxNoNewUsernamesScrolls": 6,
        },
        "ai": {
            "enabled": True,
            "smartComments": True,
            "profileAnalysis": False,
            "postAnalysis": True,
        },
    }


def test_session_config_event_is_rhythm_driven_when_no_explicit_delays():
    """A rhythm-driven run advertises no delay window and surfaces the pacing profile,
    so the analyzer shows "Rythme" instead of a misleading fixed window."""
    payload = build_instagram_session_config_event(
        {
            "deviceId": "device-1",
            "workflowType": "target_followers",
            "target": "alpha",
            "limits": {"maxProfiles": 9, "maxLikesPerProfile": 3},
            "probabilities": {"like": 100, "follow": 15, "comment": 5, "watchStories": 100, "likeStories": 30},
            "filters": {"minFollowers": 20, "maxFollowers": 2000, "minPosts": 2, "maxFollowing": 700},
            "session": {"durationMinutes": 30},
            "behaviorPolicy": {"profileId": "fast"},
        }
    )

    assert "minDelay" not in payload["session"]
    assert "maxDelay" not in payload["session"]
    assert payload["session"]["durationMinutes"] == 30
    assert payload["behaviorPolicy"] == {"profileId": "fast"}


def test_warmup_policy_is_passed_through_to_session_settings():
    """The desktop app injects warmupPolicy (camelCase numbers); the builder normalises it into
    session_settings.warmup_policy (snake_case) for the SessionManager to enforce."""
    config = build_instagram_automation_config(
        {
            "workflowType": "target_followers",
            "target": "alpha",
            "limits": {"maxProfiles": 10, "maxLikesPerProfile": 3},
            "probabilities": {"like": 50, "follow": 30, "comment": 10, "watchStories": 20, "likeStories": 5},
            "filters": {"minFollowers": 100, "maxFollowers": 5000, "minPosts": 4, "maxFollowing": 800},
            "session": {"durationMinutes": 45},
            "warmupPolicy": {
                "maxActionsPerDay": 50,
                "maxFollowsPerDay": 10,
                "maxCommentsPerDay": 5,
                "minActionGapSeconds": 45,
                "maxActionsPerSession": 25,
            },
        }
    )

    assert config["session_settings"]["warmup_policy"] == {
        "max_actions_per_day": 50,
        "max_follows_per_day": 10,
        "max_comments_per_day": 5,
        "min_action_gap_seconds": 45.0,
        "max_actions_per_session": 25,
    }


def test_no_warmup_policy_leaves_session_settings_clean():
    """Standalone (no desktop injection) -> no warmup_policy key, no enforcement."""
    config = build_instagram_automation_config(
        {
            "workflowType": "target_followers",
            "target": "alpha",
            "limits": {"maxProfiles": 10, "maxLikesPerProfile": 3},
            "probabilities": {"like": 50, "follow": 30, "comment": 10, "watchStories": 20, "likeStories": 5},
            "filters": {"minFollowers": 100, "maxFollowers": 5000, "minPosts": 4, "maxFollowing": 800},
            "session": {"durationMinutes": 45},
        }
    )

    assert "warmup_policy" not in config["session_settings"]


def test_action_carries_profile_filters_and_relationship_flags():
    """Anti-regression (2026-07-18, confirmed on a live run): the action dict MUST carry the
    profile filters. The target/hashtag/post_url runners rebuild their config via
    FilterCriteria.from_action(action) and the notifications/feed paths read action['filters'];
    neither ever sees the top-level built["filters"]. Without these keys the UI filters were
    silently replaced by dataclass defaults and the relationship-skip flags were dropped —
    a profile whose button read 'following' was processed anyway."""
    config = build_instagram_automation_config(
        {
            "workflowType": "target_followers",
            "target": "someone",
            "filters": {
                "minFollowers": 123,
                "maxFollowers": 4567,
                "minPosts": 2,
                "maxFollowing": 890,
                "skipFollowsUs": True,
                "skipAlreadyFollowing": True,
            },
        }
    )
    action = config["actions"][0]
    # Flat keys -> FilterCriteria.from_action
    assert action["min_followers"] == 123
    assert action["max_followers"] == 4567
    assert action["min_posts"] == 2
    assert action["max_following"] == 890
    assert action["skip_follows_us"] is True
    assert action["skip_already_following"] is True
    # Nested dict -> action.get('filters') readers (notifications/feed)
    assert action["filters"]["min_followers"] == 123
    assert action["filters"]["skip_follows_us"] is True


def test_action_max_bounds_zero_means_no_limit():
    """A literal 'Max followers: 0' must not reject every profile (same guard as the scraping
    mapper): 0 on a MAX bound falls back to the permissive default."""
    config = build_instagram_automation_config(
        {
            "workflowType": "target_followers",
            "target": "someone",
            "filters": {"minFollowers": 0, "maxFollowers": 0, "minPosts": 0, "maxFollowing": 0},
        }
    )
    action = config["actions"][0]
    assert action["min_followers"] == 0        # 0 min = no minimum, kept literally
    assert action["max_followers"] == 100000   # 0 max = no limit
    assert action["max_following"] == 10000


def test_filters_survive_into_the_runner_interaction_config():
    """End-to-end lock on the exact broken path: front raw config -> action ->
    WorkflowConfigBuilder.build_interaction_config -> filter_criteria consumed by
    _process_profile_on_screen. The UI values and the skip flags must all survive."""
    from taktik.core.social_media.instagram.workflows.management.config.config import (
        WorkflowConfigBuilder,
    )

    raw = {
        "workflowType": "target_followers",
        "target": "someone",
        "filters": {
            "minFollowers": 100,
            "maxFollowers": 50000,
            "minPosts": 3,
            "maxFollowing": 7500,
            "skipFollowsUs": True,
            "skipAlreadyFollowing": True,
        },
    }
    action = build_instagram_automation_config(raw)["actions"][0]
    runner_config = WorkflowConfigBuilder.build_interaction_config(action)
    criteria = runner_config["filter_criteria"]
    assert criteria["min_followers"] == 100
    assert criteria["max_followers"] == 50000
    assert criteria["min_posts"] == 3
    assert criteria["max_following"] == 7500
    assert criteria["skip_follows_us"] is True
    assert criteria["skip_already_following"] is True


def test_unknown_workflow_type_raises_instead_of_running_followers():
    # The old silent fallback turned any unmapped type into a follower-interaction
    # run on a real account (it bit once with 'cold_dm'). Must fail loudly.
    with pytest.raises(ValueError, match="cold_dm"):
        build_instagram_automation_config(
            {"workflowType": "cold_dm", "target": "someone"}
        )


def test_absent_workflow_type_keeps_the_documented_standalone_default():
    # Standalone/CLI configs predating workflowType rely on the follower default.
    config = build_instagram_automation_config({"target": "someone"})
    assert config["actions"][0]["type"] == "interact_with_followers"


def test_session_config_event_passes_through_agent_decision_contract():
    decision = {
        "mode": "decide",
        "dryRun": True,
        "capabilities": {
            "like": True,
            "follow": False,
            "comment": False,
            "watchStories": True,
            "likeStories": False,
        },
    }
    payload = build_instagram_session_config_event(
        {"ai": {"enabled": True, "profileAnalysis": True, "decision": decision}},
        ai_enabled=True,
    )

    assert payload["ai"]["decision"] == decision


def test_decision_mode_capabilities_replace_legacy_probability_ceilings():
    config = build_instagram_automation_config({
        "workflowType": "target_followers",
        "target": "someone",
        "limits": {"maxProfiles": 12, "maxLikesPerProfile": 3},
        # These stale UI intentions must have no authority in decide mode.
        "probabilities": {
            "like": 0,
            "follow": 7,
            "comment": 0,
            "watchStories": 0,
            "likeStories": 100,
        },
        "ai": {
            "enabled": True,
            "decision": {
                "mode": "decide",
                "dryRun": False,
                "capabilities": {
                    "like": True,
                    "follow": True,
                    "comment": False,
                    "watchStories": True,
                    "likeStories": False,
                },
            },
        },
    })

    action = config["actions"][0]
    assert action["probabilities"] == {
        "like_percentage": 100,
        "follow_percentage": 100,
        "comment_percentage": 0,
        "story_percentage": 100,
        "story_like_percentage": 0,
    }
    assert config["session_settings"]["total_likes_limit"] == 36
    assert config["session_settings"]["total_follows_limit"] == 12
    assert action["ai_decision_mode"] == "decide"
    assert action["ai_decision_dry_run"] is False
    assert action["ai_decision_capabilities"]["comment"] is False

    from taktik.core.social_media.instagram.workflows.management.config.config import (
        WorkflowConfigBuilder,
    )

    runner_config = WorkflowConfigBuilder.build_interaction_config(action)
    assert runner_config["max_likes_per_profile"] == 3
    assert runner_config["ai_decision_mode"] == "decide"
    assert runner_config["ai_decision_capabilities"] == action["ai_decision_capabilities"]
