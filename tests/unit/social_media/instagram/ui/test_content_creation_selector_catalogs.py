from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
    CONTENT_CREATION_SELECTORS,
)


def test_content_creation_uiautomator_fallbacks_are_catalog_owned():
    assert CONTENT_CREATION_SELECTORS.gallery_image_container_selector == {
        "className": "android.view.ViewGroup",
        "clickable": True,
    }
    assert CONTENT_CREATION_SELECTORS.location_search_field_selector == {
        "className": "android.widget.EditText"
    }
    assert CONTENT_CREATION_SELECTORS.location_first_result_selector == {
        "className": "android.widget.TextView",
        "instance": 0,
    }
    assert CONTENT_CREATION_SELECTORS.keyboard_window_selector == {
        "className": "android.inputmethodservice.SoftInputWindow"
    }
