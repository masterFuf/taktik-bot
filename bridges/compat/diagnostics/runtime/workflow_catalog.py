"""Workflow catalog constants for compat workflow diagnostics."""

DEFAULT_CONFIGS = {
    "target_followers": {
        "limits": {"maxProfiles": 3, "maxLikesPerProfile": 1},
        "probabilities": {"like": 80, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0},
    },
    "hashtag": {
        "limits": {"maxProfiles": 3, "maxLikesPerProfile": 1},
        "probabilities": {"like": 80, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0},
    },
    "feed": {
        "limits": {"maxProfiles": 3, "maxLikesPerProfile": 1},
        "probabilities": {"like": 80, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0},
    },
}

NEEDS_TARGET = (
    "target_followers",
    "target_following",
    "hashtag",
    "post_likers",
    "post_url",
    "scrape_account",
    "scrape_hashtag",
    "scrape_post_url",
    "scrape_e_story",
    "smart_comment",
)

INSTAGRAM_AUTOMATION_WF = (
    "target_followers",
    "target_following",
    "hashtag",
    "post_likers",
    "post_url",
    "feed",
    "notifications",
    "unfollow",
)
INSTAGRAM_SCRAPING_WF = ("scrape_account", "scrape_hashtag", "scrape_post_url", "scrape_e_story")
INSTAGRAM_DM_WF = ("dm_response", "dm_outreach")
INSTAGRAM_PUBLISH_WF = ("upload_post", "upload_carousel", "upload_reel", "upload_story")

TIKTOK_AUTOMATION_WF = ("for_you", "hashtag", "target", "followers")
TIKTOK_DM_WF = ("dm_read", "dm_outreach")
TIKTOK_SCRAPING_WF = ("scrape_account", "scrape_hashtag", "scrape_post")


__all__ = [
    "DEFAULT_CONFIGS",
    "INSTAGRAM_AUTOMATION_WF",
    "INSTAGRAM_DM_WF",
    "INSTAGRAM_PUBLISH_WF",
    "INSTAGRAM_SCRAPING_WF",
    "NEEDS_TARGET",
    "TIKTOK_AUTOMATION_WF",
    "TIKTOK_DM_WF",
    "TIKTOK_SCRAPING_WF",
]

