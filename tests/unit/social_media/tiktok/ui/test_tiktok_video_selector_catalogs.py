from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import (
    VIDEO_CREATOR_SELECTORS,
    VIDEO_ENGAGEMENT_SELECTORS,
    VIDEO_MEDIA_SELECTORS,
    VIDEO_SELECTORS,
    VIDEO_STATE_SELECTORS,
)
from tests.unit.social_media.tiktok.ui.test_tiktok_video_snapshot import VIDEO_43_XML


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


def test_43_1_4_action_selectors_resolve_rail_buttons_not_creator_profile():
    tree = etree.fromstring(VIDEO_43_XML.encode("utf-8"))

    like_matches = tree.xpath(VIDEO_ENGAGEMENT_SELECTORS.like_button[0])
    comment_matches = tree.xpath(VIDEO_ENGAGEMENT_SELECTORS.comment_button[0])

    assert [node.get("resource-id").rsplit("/", 1)[-1] for node in like_matches] == ["f57"]
    assert [node.get("resource-id").rsplit("/", 1)[-1] for node in comment_matches] == ["dtv"]
    assert like_matches[0].get("bounds") == "[608,861][720,966]"
    assert comment_matches[0].get("bounds") == "[580,966][720,1071]"
