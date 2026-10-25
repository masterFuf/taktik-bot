"""Instagram's catalogues by domain, the names `compat/data/overrides/instagram.yaml` addresses.

A host registers this declaration with compat at its start (`register_platform`); the version
overrides, the clone patch and the Lab's tables reach the catalogues through it.
"""

from taktik.core.compat.selectors.platforms import PlatformSelectors
from taktik.core.social_media.instagram.ui.selectors import (
    AUTH_SELECTORS,
    NAVIGATION_SELECTORS,
    BUTTON_SELECTORS,
    PROFILE_SELECTORS,
    POST_SELECTORS,
    STORY_SELECTORS,
    DM_SELECTORS,
    POPUP_SELECTORS,
    SCROLL_SELECTORS,
    DETECTION_SELECTORS,
    TEXT_INPUT_SELECTORS,
    PROBLEMATIC_PAGE_SELECTORS,
    CONTENT_CREATION_SELECTORS,
    FEED_SELECTORS,
    UNFOLLOW_SELECTORS,
    NOTIFICATION_SELECTORS,
    HASHTAG_SELECTORS,
    FOLLOWERS_LIST_SELECTORS,
    POST_COMMENTS_SELECTORS,
    POST_GRID_SELECTORS,
    POST_LIKERS_SELECTORS,
    POST_REELS_SELECTORS,
    POST_SHARE_SHEET_SELECTORS,
    FEED_SUGGESTIONS_SELECTORS,
    DISCOVER_PEOPLE_SELECTORS,
    SETTINGS_SELECTORS,
    DEBUG_SELECTORS,
)

CATALOGUES = PlatformSelectors(
    domains={
        "auth": AUTH_SELECTORS,
        "navigation": NAVIGATION_SELECTORS,
        "buttons": BUTTON_SELECTORS,
        "profile": PROFILE_SELECTORS,
        "post": POST_SELECTORS,
        "story": STORY_SELECTORS,
        "dm": DM_SELECTORS,
        "popup": POPUP_SELECTORS,
        "scroll": SCROLL_SELECTORS,
        "detection": DETECTION_SELECTORS,
        "text_input": TEXT_INPUT_SELECTORS,
        "problematic_page": PROBLEMATIC_PAGE_SELECTORS,
        "content": CONTENT_CREATION_SELECTORS,
        "feed": FEED_SELECTORS,
        "unfollow": UNFOLLOW_SELECTORS,
        "notification": NOTIFICATION_SELECTORS,
        "hashtag": HASHTAG_SELECTORS,
        "followers_list": FOLLOWERS_LIST_SELECTORS,
        # The post sub-catalogues copy POST_SELECTORS values at import: a `post.*` override does not
        # reach their readers, so each is addressed under its own name.
        "post_comments": POST_COMMENTS_SELECTORS,
        "post_grid": POST_GRID_SELECTORS,
        "post_likers": POST_LIKERS_SELECTORS,
        "post_reels": POST_REELS_SELECTORS,
        "post_share_sheet": POST_SHARE_SHEET_SELECTORS,
        "feed_suggestions": FEED_SUGGESTIONS_SELECTORS,
        "discover_people": DISCOVER_PEOPLE_SELECTORS,
        "settings": SETTINGS_SELECTORS,
        "debug": DEBUG_SELECTORS,
    },
    copies={
        "post_comments": "post",
        "post_grid": "post",
        "post_likers": "post",
        "post_reels": "post",
        "post_share_sheet": "post",
    },
)
