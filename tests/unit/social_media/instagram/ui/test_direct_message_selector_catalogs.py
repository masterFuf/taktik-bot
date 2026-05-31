from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import (
    DM_SELECTORS,
)


def test_dm_uiautomator_fallbacks_are_catalog_owned():
    assert DM_SELECTORS.message_input_class_selector == {
        "className": "android.widget.EditText"
    }
    assert DM_SELECTORS.text_view_class_selector == {
        "className": "android.widget.TextView"
    }


def test_dm_dynamic_selectors_are_built_by_catalog():
    assert DM_SELECTORS.thread_selector_for_username("target_user") == {
        "textContains": "target_user"
    }
    assert DM_SELECTORS.account_result_selector_for_username("target_user") == {
        "textContains": "target_user",
        "className": "android.widget.TextView",
    }
    assert DM_SELECTORS.send_button_selector_for_description("Send") == {
        "contentDescription": "Send"
    }
