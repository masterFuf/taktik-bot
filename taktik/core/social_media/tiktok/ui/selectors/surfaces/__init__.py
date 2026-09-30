"""TikTok surface selectors."""

from taktik.core.social_media.tiktok.ui.selectors.surfaces.activity import ActivitySelectors, ACTIVITY_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.conversation import (
    ConversationSelectors,
    CONVERSATION_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FollowersSelectors, FOLLOWERS_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.inbox import InboxSelectors, INBOX_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import ProfileSelectors, PROFILE_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.search import SearchSelectors, SEARCH_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import (
    CommentSelectors,
    COMMENT_SELECTORS,
    VideoCreatorSelectors,
    VIDEO_CREATOR_SELECTORS,
    VideoCommentsSelectors,
    VIDEO_COMMENTS_SELECTORS,
    VideoDetailSelectors,
    VIDEO_DETAIL_SELECTORS,
    VideoEngagementSelectors,
    VIDEO_ENGAGEMENT_SELECTORS,
    VideoMediaSelectors,
    VIDEO_MEDIA_SELECTORS,
    VideoSelectors,
    VIDEO_SELECTORS,
    VideoStateSelectors,
    VIDEO_STATE_SELECTORS,
)

__all__ = [
    "ACTIVITY_SELECTORS",
    "COMMENT_SELECTORS",
    "CONVERSATION_SELECTORS",
    "FOLLOWERS_SELECTORS",
    "INBOX_SELECTORS",
    "PROFILE_SELECTORS",
    "SEARCH_SELECTORS",
    "VIDEO_COMMENTS_SELECTORS",
    "VIDEO_CREATOR_SELECTORS",
    "VIDEO_DETAIL_SELECTORS",
    "VIDEO_ENGAGEMENT_SELECTORS",
    "VIDEO_MEDIA_SELECTORS",
    "VIDEO_SELECTORS",
    "VIDEO_STATE_SELECTORS",
    "ActivitySelectors",
    "CommentSelectors",
    "ConversationSelectors",
    "FollowersSelectors",
    "InboxSelectors",
    "ProfileSelectors",
    "SearchSelectors",
    "VideoCommentsSelectors",
    "VideoCreatorSelectors",
    "VideoDetailSelectors",
    "VideoEngagementSelectors",
    "VideoMediaSelectors",
    "VideoSelectors",
    "VideoStateSelectors",
]
