"""TikTok video surface selectors."""

from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.comments import CommentSelectors, COMMENT_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.creator import (
    VideoCreatorSelectors,
    VIDEO_CREATOR_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.detail import VideoSelectors, VIDEO_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.engagement import (
    VideoEngagementSelectors,
    VIDEO_ENGAGEMENT_SELECTORS,
)
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.media import VideoMediaSelectors, VIDEO_MEDIA_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.share import VIDEO_SHARE_SELECTORS, VideoShareSelectors
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.sound import VIDEO_SOUND_SELECTORS, VideoSoundSelectors
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.state import VideoStateSelectors, VIDEO_STATE_SELECTORS

VideoDetailSelectors = VideoSelectors
VIDEO_DETAIL_SELECTORS = VIDEO_SELECTORS
VideoCommentsSelectors = CommentSelectors
VIDEO_COMMENTS_SELECTORS = COMMENT_SELECTORS

__all__ = [
    "COMMENT_SELECTORS",
    "VIDEO_COMMENTS_SELECTORS",
    "VIDEO_CREATOR_SELECTORS",
    "VIDEO_DETAIL_SELECTORS",
    "VIDEO_ENGAGEMENT_SELECTORS",
    "VIDEO_MEDIA_SELECTORS",
    "VIDEO_SELECTORS",
    "VIDEO_SHARE_SELECTORS",
    "VIDEO_SOUND_SELECTORS",
    "VideoSoundSelectors",
    "VIDEO_STATE_SELECTORS",
    "CommentSelectors",
    "VideoCommentsSelectors",
    "VideoCreatorSelectors",
    "VideoDetailSelectors",
    "VideoEngagementSelectors",
    "VideoMediaSelectors",
    "VideoSelectors",
    "VideoStateSelectors",
]
