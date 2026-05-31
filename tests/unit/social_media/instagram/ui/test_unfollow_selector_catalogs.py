from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS


def test_unfollow_visible_text_probes_live_in_flow_catalog():
    assert UNFOLLOW_SELECTORS.following_tab_text_probe == "following"
    assert UNFOLLOW_SELECTORS.following_button_text == "Following"
    assert UNFOLLOW_SELECTORS.follow_back_button_text == "Follow back"
    assert UNFOLLOW_SELECTORS.unfollow_confirm_text == "Unfollow"


def test_unfollow_active_package_resource_builders():
    app_id = "com.instagram.android"

    assert (
        UNFOLLOW_SELECTORS.active_follow_list_username_resource_id(app_id)
        == "com.instagram.android:id/follow_list_username"
    )
    assert (
        UNFOLLOW_SELECTORS.active_follow_list_button_resource_id(app_id)
        == "com.instagram.android:id/follow_list_row_large_follow_button"
    )
    assert UNFOLLOW_SELECTORS.unified_followers_tab_selector(app_id) == (
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]'
        '//*[contains(@text, "Followers")]'
    )
