from taktik.core.social_media.tiktok.ui.selectors.publish import (
    PUBLISH_COMPOSER_SELECTORS,
    PUBLISH_CREATION_ENTRY_SELECTORS,
    PUBLISH_EDITOR_SELECTORS,
    PUBLISH_MEDIA_PICKER_SELECTORS,
    PUBLISH_PROGRESS_SELECTORS,
    PUBLISH_SELECTORS,
)


def test_publish_aggregate_delegates_to_creation_entry_catalog():
    assert PUBLISH_SELECTORS.create_btn == PUBLISH_CREATION_ENTRY_SELECTORS.create_btn
    assert PUBLISH_SELECTORS.home_ready_indicators == PUBLISH_CREATION_ENTRY_SELECTORS.home_ready_indicators


def test_publish_aggregate_delegates_to_media_picker_catalog():
    assert PUBLISH_SELECTORS.upload_btn == PUBLISH_MEDIA_PICKER_SELECTORS.upload_btn
    assert PUBLISH_SELECTORS.gallery_first_item == PUBLISH_MEDIA_PICKER_SELECTORS.gallery_first_item


def test_publish_aggregate_delegates_to_editor_catalog():
    assert PUBLISH_SELECTORS.video_edit_cancel_btn == PUBLISH_EDITOR_SELECTORS.video_edit_cancel_btn
    assert PUBLISH_SELECTORS.popup_cancel_buttons == PUBLISH_EDITOR_SELECTORS.popup_cancel_buttons


def test_publish_aggregate_delegates_to_composer_catalog():
    assert PUBLISH_SELECTORS.caption_input == PUBLISH_COMPOSER_SELECTORS.caption_input
    assert PUBLISH_SELECTORS.publish_confirm_btn == PUBLISH_COMPOSER_SELECTORS.publish_confirm_btn


def test_publish_aggregate_delegates_to_progress_catalog():
    assert PUBLISH_SELECTORS.publish_progress_indicator == PUBLISH_PROGRESS_SELECTORS.publish_progress_indicator
    assert PUBLISH_SELECTORS.success_indicator == PUBLISH_PROGRESS_SELECTORS.success_indicator
