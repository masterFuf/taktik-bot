from taktik.core.social_media.tiktok.ui.language import filter_selectors
from taktik.core.social_media.tiktok.ui.selectors.flows.publish import PublishSelectors


def test_publish_post_screen_markers_are_centralized():
    selectors = PublishSelectors()

    assert selectors.has_post_screen_marker(
        '<node resource-id="com.zhiliaoapp.musically:id/g19" />'
    )
    assert selectors.has_post_screen_marker('<node text="Ajouter une description" />')


def test_publish_caption_selectors_are_language_classified():
    selectors = PublishSelectors()

    fr_selectors = filter_selectors(selectors.caption_input, "fr")
    en_selectors = filter_selectors(selectors.caption_input, "en")

    assert any("Ajouter une description" in selector for selector in fr_selectors)
    assert not any("Add a description" in selector for selector in fr_selectors)
    assert any("Add a description" in selector for selector in en_selectors)
    assert not any("Ajouter une description" in selector for selector in en_selectors)


def test_publish_video_edit_and_hashtag_selectors_are_centralized():
    selectors = PublishSelectors()

    assert selectors.has_video_edit_screen_marker(
        '<node text="Annuler" /><node text="Enregistrer" /><node text="Aperçu" />'
    )
    assert selectors.video_edit_cancel_btn
    assert selectors.hashtag_suggestion_nodes
    assert selectors.hashtag_suggestion_rows


def test_publish_screen_state_markers_are_centralized():
    selectors = PublishSelectors()

    assert selectors.home_ready_indicators
    assert selectors.upload_dump_selectors
    assert selectors.publish_progress_text_nodes
    assert selectors.has_gallery_picker_marker('<node resource-id="pkg:id/mub" />')
    assert selectors.has_camera_creation_marker(
        '<node text="Add sound" /><node resource-id="pkg:id/r3r" />'
    )
