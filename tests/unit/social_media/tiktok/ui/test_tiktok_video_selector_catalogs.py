from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import (
    VIDEO_CREATOR_SELECTORS,
    VIDEO_ENGAGEMENT_SELECTORS,
    VIDEO_MEDIA_SELECTORS,
    VIDEO_SELECTORS,
    VIDEO_STATE_SELECTORS,
)


def test_video_aggregate_delegates_to_creator_catalog():
    assert (
        VIDEO_SELECTORS.creator_profile_image_resource_id_selectors
        == VIDEO_CREATOR_SELECTORS.creator_profile_image_resource_id_selectors
    )
    assert VIDEO_SELECTORS.creator_profile_image == VIDEO_CREATOR_SELECTORS.creator_profile_image
    assert VIDEO_SELECTORS.follow_button == VIDEO_CREATOR_SELECTORS.follow_button


def test_video_aggregate_delegates_to_engagement_catalog():
    assert VIDEO_SELECTORS.like_button == VIDEO_ENGAGEMENT_SELECTORS.like_button
    assert (
        VIDEO_SELECTORS.like_button_content_desc_fallbacks
        == VIDEO_ENGAGEMENT_SELECTORS.like_button_content_desc_fallbacks
    )
    assert all(
        selector in VIDEO_SELECTORS.like_button_for_count
        for selector in VIDEO_ENGAGEMENT_SELECTORS.like_button_content_desc_fallbacks
    )
    assert VIDEO_SELECTORS.share_button == VIDEO_ENGAGEMENT_SELECTORS.share_button


def test_video_aggregate_delegates_to_media_catalog():
    assert VIDEO_SELECTORS.sound_button == VIDEO_MEDIA_SELECTORS.sound_button
    assert VIDEO_SELECTORS.video_container == VIDEO_MEDIA_SELECTORS.video_container


def test_video_aggregate_delegates_to_state_catalog():
    assert VIDEO_SELECTORS.video_page_indicator == VIDEO_STATE_SELECTORS.video_page_indicator
    assert VIDEO_SELECTORS.like_button_unliked == VIDEO_STATE_SELECTORS.like_button_unliked
