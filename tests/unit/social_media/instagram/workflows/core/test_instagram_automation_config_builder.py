from taktik.core.social_media.instagram.workflows.core.config_builder import (
    build_instagram_automation_config,
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
