"""Instagram post-surface selectors."""

from .comments import PostCommentsSelectors, POST_COMMENTS_SELECTORS
from .detail import PostSelectors, POST_SELECTORS
from .grid import PostGridSelectors, POST_GRID_SELECTORS
from .likers import PostLikersSelectors, POST_LIKERS_SELECTORS
from .reels import PostReelsSelectors, POST_REELS_SELECTORS
from .share_sheet import PostShareSheetSelectors, POST_SHARE_SHEET_SELECTORS

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
