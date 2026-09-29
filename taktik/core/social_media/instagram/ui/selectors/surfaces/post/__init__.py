"""Instagram post-surface selectors."""

from taktik.core.social_media.instagram.ui.selectors.surfaces.post.comments import PostCommentsSelectors, POST_COMMENTS_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post.detail import PostSelectors, POST_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post.grid import PostGridSelectors, POST_GRID_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post.likers import PostLikersSelectors, POST_LIKERS_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post.reels import PostReelsSelectors, POST_REELS_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post.share_sheet import PostShareSheetSelectors, POST_SHARE_SHEET_SELECTORS

PostDetailSelectors = PostSelectors
POST_DETAIL_SELECTORS = POST_SELECTORS

__all__ = [
    "POST_COMMENTS_SELECTORS",
    "POST_DETAIL_SELECTORS",
    "POST_GRID_SELECTORS",
    "POST_LIKERS_SELECTORS",
    "POST_SELECTORS",
    "POST_REELS_SELECTORS",
    "POST_SHARE_SHEET_SELECTORS",
    "PostCommentsSelectors",
    "PostDetailSelectors",
    "PostGridSelectors",
    "PostLikersSelectors",
    "PostSelectors",
    "PostReelsSelectors",
    "PostShareSheetSelectors",
]
