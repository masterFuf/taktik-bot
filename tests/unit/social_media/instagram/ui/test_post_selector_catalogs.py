from taktik.core.social_media.instagram.ui.selectors import (
    POST_COMMENTS_SELECTORS,
    POST_DETAIL_SELECTORS,
    POST_GRID_SELECTORS,
    POST_LIKERS_SELECTORS,
    POST_REELS_SELECTORS,
    POST_SELECTORS,
    POST_SHARE_SHEET_SELECTORS,
)


def test_specialized_post_catalogs_remain_compatible_with_legacy_aggregate():
    assert POST_DETAIL_SELECTORS is POST_SELECTORS
    assert POST_DETAIL_SELECTORS.all_button_nodes_selector == '//android.widget.Button'
    assert POST_DETAIL_SELECTORS.all_view_group_nodes_selector == '//android.view.ViewGroup'
    assert (
        POST_DETAIL_SELECTORS.caption_layout_selector
        == '//com.instagram.ui.widget.textview.IgTextLayoutView'
    )

    assert POST_COMMENTS_SELECTORS.comment_button_selectors == POST_SELECTORS.comment_button_selectors
    assert POST_COMMENTS_SELECTORS.comments_list_resource_id == POST_SELECTORS.comments_list_resource_id
    assert (
        POST_COMMENTS_SELECTORS.commenter_button_nodes_selector
        == POST_SELECTORS.all_button_nodes_selector
    )
    assert POST_COMMENTS_SELECTORS.comments_list_selector() == (
        f'//*[@resource-id="{POST_SELECTORS.comments_list_resource_id}"]'
    )

    assert POST_LIKERS_SELECTORS.liked_by_selectors == POST_SELECTORS.liked_by_selectors
    assert POST_LIKERS_SELECTORS.like_count_selectors == POST_SELECTORS.like_count_selectors

    assert POST_SHARE_SHEET_SELECTORS.share_button_selectors == POST_SELECTORS.share_button_selectors
    assert POST_SHARE_SHEET_SELECTORS.share_picker_url_selectors == POST_SELECTORS.share_picker_url_selectors

    assert POST_GRID_SELECTORS.first_post_grid == POST_SELECTORS.first_post_grid
    assert POST_GRID_SELECTORS.hashtag_post_selectors == POST_SELECTORS.hashtag_post_selectors

    assert POST_REELS_SELECTORS.reel_indicators == POST_SELECTORS.reel_indicators
    assert POST_REELS_SELECTORS.reel_like_selectors == POST_SELECTORS.reel_like_selectors
