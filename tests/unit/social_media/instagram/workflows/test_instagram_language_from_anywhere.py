"""The Instagram language switch starts from its own profile tab; started on a screen without the
tab bar (a reel, a search, the 410 notifications), it now goes back to the feed once first."""

import taktik.core.social_media.instagram.actions.atomic.navigation as navigation
from taktik.core.social_media.instagram.workflows.management.language.change_language_workflow import (
    ChangeLanguageWorkflow,
)


def test_without_the_tab_bar_it_goes_home_once_before_giving_up(monkeypatch):
    homes = []

    class _Nav:
        def __init__(self, device):
            pass

        def navigate_to_home(self):
            homes.append(True)
            return True

    monkeypatch.setattr(navigation, "NavigationActions", _Nav)
    monkeypatch.setattr(
        "taktik.core.social_media.instagram.workflows.management.language.change_language_workflow.detect_and_optimize",
        lambda device: None,
    )
    workflow = ChangeLanguageWorkflow(device=object(), device_id="test-device")
    tries = []
    workflow._click_first_match = lambda selectors, name: tries.append(name) or False

    result = workflow.execute(language="fr")

    assert homes == [True]
    assert tries == ["Profile tab", "Profile tab"]
    assert result["error_type"] == "profile_tab_not_found"
