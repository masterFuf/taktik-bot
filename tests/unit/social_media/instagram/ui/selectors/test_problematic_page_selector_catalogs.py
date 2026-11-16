from taktik.core.shared.ui.selectors.system.permission_prompt import PERMISSION_PROMPT_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.shell.blocking_states import (
    PROBLEMATIC_PAGE_SELECTORS,
)


def test_the_permission_prompt_is_read_from_androids_own_catalogue():
    """Android's permission prompt is not Instagram's: the check of pages proves it and grants it
    by the ids of the catalogue of Android's windows, the one the publishing workflow reads.

    Instagram's catalogue used to keep its own list (`allow_permission_button_selectors`), whose
    words « Autoriser »/« Allow » found no button on the prompts of Android 12 and later, and
    whose one id found the grant of a contacts request.
    """
    pattern = PROBLEMATIC_PAGE_SELECTORS.detection_patterns["android_permission_dialog"]

    assert pattern["system_xpaths"] == PERMISSION_PROMPT_SELECTORS.prompt
    assert "indicators" not in pattern
    assert not hasattr(PROBLEMATIC_PAGE_SELECTORS, "allow_permission_button_selectors")


def test_the_grant_buttons_never_refuse_nor_grant_for_good_nor_limit_the_gallery():
    grant = " ".join(PERMISSION_PROMPT_SELECTORS.grant)

    for never in ("deny", "foreground_only", "allow_selected", "no_upgrade"):
        assert never not in grant
    tokens = [xpath.split('="', 1)[1].split('"', 1)[0] for xpath in PERMISSION_PROMPT_SELECTORS.grant]
    assert tokens == ["permission_allow_all_button", "permission_allow_one_time_button",
                      "permission_allow_button"]
