"""TikTok's catalogues by domain, the names `compat/data/overrides/tiktok.yaml` addresses.

A host registers this declaration with compat at its start (`register_platform`); the version
overrides, the clone patch and the Lab's tables reach the catalogues through it.
"""

from taktik.core.compat.selectors.platforms import PlatformSelectors
from taktik.core.social_media.tiktok.ui.selectors import (
    AUTH_SELECTORS,
    SIGNUP_SELECTORS,
    LOGOUT_SELECTORS,
    COUNTRY_PICKER_SELECTORS,
    NAVIGATION_SELECTORS,
    PROFILE_SELECTORS,
    # The four catalogues BEHIND `VIDEO_SELECTORS`, not the facade over them. Registering the
    # facade looked right and reached nothing: it is a `__getattr__` object, so a patch aimed at
    # it lands on a phantom attribute while production imports these four.
    VIDEO_CREATOR_SELECTORS,
    VIDEO_ENGAGEMENT_SELECTORS,
    VIDEO_MEDIA_SELECTORS,
    VIDEO_STATE_SELECTORS,
    PUBLISH_COMPOSER_SELECTORS,
    PUBLISH_CREATION_ENTRY_SELECTORS,
    PUBLISH_EDITOR_SELECTORS,
    PUBLISH_MEDIA_PICKER_SELECTORS,
    PUBLISH_PROGRESS_SELECTORS,
    COMMENT_SELECTORS,
    SEARCH_SELECTORS,
    INBOX_SELECTORS,
    ACTIVITY_SELECTORS,
    CONVERSATION_SELECTORS,
    POPUP_SELECTORS,
    SCROLL_SELECTORS,
    DETECTION_SELECTORS,
    FOLLOWERS_SELECTORS,
    SETTINGS_SELECTORS,
)

CATALOGUES = PlatformSelectors(
    domains={
        "auth": AUTH_SELECTORS,
        "signup": SIGNUP_SELECTORS,
        "logout": LOGOUT_SELECTORS,
        "country_picker": COUNTRY_PICKER_SELECTORS,
        "navigation": NAVIGATION_SELECTORS,
        "profile": PROFILE_SELECTORS,
        # `video` used to point at the VideoSelectors FACADE. Measured: the override machinery
        # reached 15 of the catalogue's 25 distinct objects, and the one non-dataclass among them
        # absorbed its patches silently. The four real video catalogues and the five publish ones
        # are registered by name instead — nothing addresses a facade any more.
        "video_creator": VIDEO_CREATOR_SELECTORS,
        "video_engagement": VIDEO_ENGAGEMENT_SELECTORS,
        "video_media": VIDEO_MEDIA_SELECTORS,
        "video_state": VIDEO_STATE_SELECTORS,
        "publish_composer": PUBLISH_COMPOSER_SELECTORS,
        "publish_creation_entry": PUBLISH_CREATION_ENTRY_SELECTORS,
        "publish_editor": PUBLISH_EDITOR_SELECTORS,
        "publish_media_picker": PUBLISH_MEDIA_PICKER_SELECTORS,
        "publish_progress": PUBLISH_PROGRESS_SELECTORS,
        "comment": COMMENT_SELECTORS,
        "search": SEARCH_SELECTORS,
        "inbox": INBOX_SELECTORS,
        "activity": ACTIVITY_SELECTORS,
        "conversation": CONVERSATION_SELECTORS,
        "popup": POPUP_SELECTORS,
        "scroll": SCROLL_SELECTORS,
        "detection": DETECTION_SELECTORS,
        "followers": FOLLOWERS_SELECTORS,
        "settings": SETTINGS_SELECTORS,
    },
)
