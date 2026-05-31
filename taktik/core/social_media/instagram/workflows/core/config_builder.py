"""Bridge-compatible config builder for Instagram automation workflows."""

import math
from typing import Any, Dict, Optional


def _build_action_config(
    *,
    raw_config: Dict[str, Any],
    action_type: str,
    interaction_type: str,
    primary_target: str,
    target_list: list[str],
    max_profiles: int,
    min_likes_per_profile: int,
    max_likes_per_profile: int,
    like_percentage: int,
    follow_percentage: int,
    comment_percentage: int,
    story_percentage: int,
    story_like_percentage: int,
    max_consecutive_known_usernames: Optional[int] = None,
    max_no_new_usernames_scrolls: Optional[int] = None,
) -> Dict[str, Any]:
    """Build the action payload consumed by ``InstagramAutomation``."""

    target = raw_config.get("target")
    limits = raw_config.get("limits", {})
    probabilities = raw_config.get("probabilities", {})
    filters = raw_config.get("filters", {})
    comments_config = raw_config.get("comments", {})
    feed_stories_config = raw_config.get("feedStories", {})
    unfollow_config = raw_config.get("unfollow", {})

    if action_type == "sync_following":
        return {
            "type": "sync_following",
        }

    if action_type == "sync_followers_following":
        sync_cfg = raw_config.get("sync", {})
        return {
            "type": "sync_followers_following",
            "mode": sync_cfg.get("mode", "fast"),
        }

    if action_type == "unfollow":
        return {
            "type": "unfollow",
            "max_unfollows": unfollow_config.get("maxUnfollows", max_profiles),
            "unfollow_mode": unfollow_config.get("unfollowMode", "non-followers"),
            "min_delay": 2,
            "max_delay": 5,
            "skip_verified": unfollow_config.get("skipVerified", True),
            "skip_business": unfollow_config.get("skipBusiness", False),
            "min_days_since_follow": unfollow_config.get("minDaysSinceFollow", 3),
            "bot_follows_only": unfollow_config.get("botFollowsOnly", False),
            "whitelist": unfollow_config.get("whitelist", []),
            "blacklist": unfollow_config.get("blacklist", []),
        }

    if action_type == "feed":
        feed_story_enabled = bool(feed_stories_config.get("enabled", story_percentage > 0))
        return {
            "type": "feed",
            "max_interactions": max_profiles,
            "max_posts_to_check": max_profiles,
            "like_percentage": like_percentage,
            "follow_percentage": follow_percentage,
            "comment_percentage": comment_percentage,
            "story_watch_percentage": story_percentage,
            "story_like_percentage": story_like_percentage,
            "view_feed_stories": feed_story_enabled,
            "max_feed_story_profiles": feed_stories_config.get(
                "maxProfiles", limits.get("maxFeedStoryProfiles", 5)
            ),
            "feed_story_reaction_percentage": probabilities.get("feedStoryReaction", 0),
            "feed_story_reaction": feed_stories_config.get("reaction", "laugh"),
            "min_post_likes": filters.get("minPostLikes", 0),
            "max_post_likes": filters.get("maxPostLikes", 0),
            "custom_comments": comments_config.get("customComments", []),
        }

    if action_type == "notifications":
        return {
            "type": "notifications",
            "max_interactions": max_profiles,
            "like_percentage": like_percentage,
            "follow_percentage": follow_percentage,
            "comment_percentage": comment_percentage,
        }

    action_config: Dict[str, Any] = {
        "type": action_type,
        "target_username": primary_target if action_type == "interact_with_followers" else None,
        "target_usernames": target_list if action_type == "interact_with_followers" else [],
        "hashtag": target if action_type == "hashtag" else None,
        "post_url": target if action_type == "post_url" else None,
        "interaction_type": interaction_type,
        "max_interactions": max_profiles,
        "like_posts": True,
        "min_likes_per_profile": min_likes_per_profile,
        "max_likes_per_profile": max_likes_per_profile,
        "probabilities": {
            "like_percentage": like_percentage,
            "follow_percentage": follow_percentage,
            "comment_percentage": comment_percentage,
            "story_percentage": story_percentage,
            "story_like_percentage": story_like_percentage,
        },
        "like_settings": {
            "enabled": like_percentage > 0,
            "like_carousels": True,
            "like_reels": True,
            "randomize_order": True,
            "methods": ["button_click", "double_tap"],
            "verify_like_success": True,
            "max_attempts_per_post": 2,
            "delay_between_attempts": 2,
        },
        "follow_settings": {
            "enabled": follow_percentage > 0,
            "unfollow_after_days": 3,
            "verify_follow_success": True,
        },
        "story_settings": {
            "enabled": story_percentage > 0,
            "watch_duration_range": [3, 8],
        },
        "story_like_settings": {
            "enabled": story_like_percentage > 0,
            "max_stories_per_user": 3,
            "like_probability": story_like_percentage / 100.0,
            "verify_like_success": True,
        },
        "comment_settings": {
            "enabled": comment_percentage > 0,
            "custom_comments": comments_config.get("customComments", []),
        },
        "scrolling": {
            "enabled": True,
            "max_scroll_attempts": 3,
            "scroll_delay": 1.5,
        },
    }

    if max_consecutive_known_usernames is not None:
        action_config["max_consecutive_known_usernames"] = max_consecutive_known_usernames
    if max_no_new_usernames_scrolls is not None:
        action_config["max_no_new_usernames_scrolls"] = max_no_new_usernames_scrolls

    return action_config


def build_instagram_automation_config(raw_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build the legacy CLI-compatible config consumed by Instagram automation."""
    target = raw_config.get("target", "")
    workflow_type = raw_config.get("workflowType")
    limits = raw_config.get("limits", {})
    probabilities = raw_config.get("probabilities", {})
    filters = raw_config.get("filters", {})
    session_config = raw_config.get("session", {})

    max_profiles = limits.get("maxProfiles", 20)
    min_likes_per_profile = limits.get("minLikesPerProfile", 1)
    max_likes_per_profile = limits.get("maxLikesPerProfile", 2)
    like_percentage = probabilities.get("like", 80)
    follow_percentage = probabilities.get("follow", 20)
    comment_percentage = probabilities.get("comment", 5)
    story_percentage = probabilities.get("watchStories", 15)
    story_like_percentage = probabilities.get("likeStories", 10)
    min_followers = filters.get("minFollowers", 50)
    max_followers = filters.get("maxFollowers", 50000)
    min_posts = filters.get("minPosts", 5)
    max_followings = filters.get("maxFollowing", 7500)
    session_duration = session_config.get("durationMinutes", 60)
    min_delay = session_config.get("minDelay", 5)
    max_delay = session_config.get("maxDelay", 15)
    max_consecutive_known_usernames = session_config.get("maxConsecutiveKnownUsernames")
    if max_consecutive_known_usernames is not None:
        max_consecutive_known_usernames = max(1, int(max_consecutive_known_usernames or 1))

    max_no_new_usernames_scrolls = session_config.get("maxNoNewUsernamesScrolls")
    if max_no_new_usernames_scrolls is not None:
        max_no_new_usernames_scrolls = max(1, int(max_no_new_usernames_scrolls or 1))

    target_list = [t.strip() for t in target.split(",") if t.strip()]
    primary_target = target_list[0] if target_list else target

    if workflow_type == "target_followers":
        interaction_type = "followers"
        action_type = "interact_with_followers"
        session_workflow_type = "target_followers"
    elif workflow_type == "target_following":
        interaction_type = "following"
        action_type = "interact_with_followers"
        session_workflow_type = "target_followers"
    elif workflow_type == "hashtags":
        interaction_type = "hashtag"
        action_type = "hashtag"
        session_workflow_type = "hashtag"
    elif workflow_type == "post_url":
        interaction_type = "post-likers"
        action_type = "post_url"
        session_workflow_type = "target_followers"
    elif workflow_type == "unfollow":
        interaction_type = "unfollow"
        action_type = "unfollow"
        session_workflow_type = "unfollow"
    elif workflow_type == "sync_following":
        interaction_type = "sync_following"
        action_type = "sync_following"
        session_workflow_type = "sync_following"
    elif workflow_type == "sync_followers_following":
        interaction_type = "sync_followers_following"
        action_type = "sync_followers_following"
        session_workflow_type = "sync_following"
    elif workflow_type == "feed":
        interaction_type = "feed"
        action_type = "feed"
        session_workflow_type = "feed"
    elif workflow_type == "notifications":
        interaction_type = "notifications"
        action_type = "notifications"
        session_workflow_type = "notifications"
    else:
        interaction_type = "followers"
        action_type = "interact_with_followers"
        session_workflow_type = "target_followers"

    session_settings: Dict[str, Any] = {
        "workflow_type": session_workflow_type,
        "total_profiles_limit": max_profiles,
        "total_follows_limit": math.ceil(max_profiles * (follow_percentage / 100))
        if follow_percentage > 0
        else 0,
        "total_likes_limit": math.ceil(max_profiles * max_likes_per_profile * (like_percentage / 100))
        if like_percentage > 0
        else 0,
        "session_duration_minutes": session_duration,
        "skip_initial_restart": True,
        "delay_between_actions": {
            "min": min_delay,
            "max": max_delay,
        },
        "randomize_actions": True,
        "enable_screenshots": True,
        "screenshot_path": "screenshots",
    }

    if max_consecutive_known_usernames is not None:
        session_settings["max_consecutive_known_usernames"] = max_consecutive_known_usernames
    if max_no_new_usernames_scrolls is not None:
        session_settings["max_no_new_usernames_scrolls"] = max_no_new_usernames_scrolls

    return {
        "filters": {
            "min_followers": min_followers,
            "max_followers": max_followers,
            "min_followings": 0,
            "max_followings": max_followings,
            "min_posts": min_posts,
            "privacy_relation": "public_and_private",
            "blacklist_words": [],
        },
        "session_settings": session_settings,
        "actions": [
            _build_action_config(
                raw_config=raw_config,
                action_type=action_type,
                interaction_type=interaction_type,
                primary_target=primary_target,
                target_list=target_list,
                max_profiles=max_profiles,
                min_likes_per_profile=min_likes_per_profile,
                max_likes_per_profile=max_likes_per_profile,
                like_percentage=like_percentage,
                follow_percentage=follow_percentage,
                comment_percentage=comment_percentage,
                story_percentage=story_percentage,
                story_like_percentage=story_like_percentage,
                max_consecutive_known_usernames=max_consecutive_known_usernames,
                max_no_new_usernames_scrolls=max_no_new_usernames_scrolls,
            )
        ],
    }


def build_instagram_session_config_event(
    raw_config: Dict[str, Any],
    *,
    ai_enabled: bool = False,
) -> Dict[str, Any]:
    """Build the structured session_config event payload emitted by the bridge."""
    limits = raw_config.get("limits", {})
    probabilities = raw_config.get("probabilities", {})
    filters = raw_config.get("filters", {})
    session_config = raw_config.get("session", {})
    ai_config = raw_config.get("ai", {})

    session_payload: Dict[str, Any] = {
        "durationMinutes": session_config.get("durationMinutes", 60),
        "minDelay": session_config.get("minDelay", 5),
        "maxDelay": session_config.get("maxDelay", 15),
    }
    if session_config.get("maxConsecutiveKnownUsernames") is not None:
        session_payload["maxConsecutiveKnownUsernames"] = session_config.get(
            "maxConsecutiveKnownUsernames"
        )
    if session_config.get("maxNoNewUsernamesScrolls") is not None:
        session_payload["maxNoNewUsernamesScrolls"] = session_config.get(
            "maxNoNewUsernamesScrolls"
        )

    payload: Dict[str, Any] = {
        "deviceId": raw_config.get("deviceId"),
        "workflowType": raw_config.get("workflowType"),
        "target": raw_config.get("target"),
        "limits": {
            "maxProfiles": limits.get("maxProfiles", 20),
            "maxLikesPerProfile": limits.get("maxLikesPerProfile", 2),
        },
        "probabilities": {
            "like": probabilities.get("like", 80),
            "follow": probabilities.get("follow", 20),
            "comment": probabilities.get("comment", 5),
            "watchStories": probabilities.get("watchStories", 15),
            "likeStories": probabilities.get("likeStories", 10),
        },
        "filters": {
            "minFollowers": filters.get("minFollowers", 50),
            "maxFollowers": filters.get("maxFollowers", 50000),
            "minPosts": filters.get("minPosts", 5),
            "maxFollowing": filters.get("maxFollowing", 7500),
        },
        "session": session_payload,
    }

    if ai_enabled:
        payload["ai"] = {
            "enabled": True,
            "smartComments": ai_config.get("smartComments", False),
            "profileAnalysis": ai_config.get("profileAnalysis", False),
            "postAnalysis": ai_config.get("postAnalysis", False),
        }

    return payload
