"""Shared helpers for all workflow modules (scraping, discovery)."""

from taktik.core.social_media.instagram.workflows.common.detection import is_reel_post, is_in_post_view, is_likers_popup_open, is_comments_view_open
from taktik.core.social_media.instagram.workflows.common.post_navigation import open_first_post_of_profile, open_likers_list
from taktik.core.social_media.instagram.workflows.scraping.session import should_continue_session

__all__ = [
    'is_reel_post', 'is_in_post_view',
    'is_likers_popup_open', 'is_comments_view_open',
    'open_first_post_of_profile', 'open_likers_list',
    'should_continue_session',
]
