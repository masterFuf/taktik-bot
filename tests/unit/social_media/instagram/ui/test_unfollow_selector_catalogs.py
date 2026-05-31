from taktik.core.social_media.instagram.ui.selectors.flows.unfollow import UNFOLLOW_SELECTORS


def test_unfollow_visible_text_probes_live_in_flow_catalog():
    assert UNFOLLOW_SELECTORS.following_tab_text_probe == "following"
    assert UNFOLLOW_SELECTORS.following_button_text == "Following"
    assert UNFOLLOW_SELECTORS.unfollow_confirm_text == "Unfollow"
