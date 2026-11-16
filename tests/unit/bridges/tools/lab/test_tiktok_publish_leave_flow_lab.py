"""`tt.publish.leave_flow` is the way out the upload workflow takes after a failure past the gallery.

The Lab action calls the production `leave_publish_flow` on the raw device, as the workflow does.
The screens are the real TikTok 47.0.3 captures in French of `test_tiktok_publish_exit` (`EXIT_SCREENS`).
"""

from types import SimpleNamespace

import pytest

from bridges.tools.lab.actions.tiktok import ACTION_REGISTRY, register_actions
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.social_media.tiktok.services.navigation import reset
from taktik.core.social_media.tiktok.services.publish import navigation
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from unit.social_media.tiktok.workflows.publish.screen_phone import EXIT_BACKS, EXIT_SCREENS, ScreenPhone


@pytest.fixture(autouse=True)
def phone_4703_in_french(monkeypatch):
    monkeypatch.setattr(reset.time, "sleep", lambda _seconds: None)
    apply_version_overrides("tiktok", "47.0.3")
    set_active_locale("fr")
    yield
    set_active_locale(None)
    apply_version_overrides("tiktok", "43.1.4")


def _bundle(phone):
    """The bundle as the Lab hands it: the facade, and under it the raw uiautomator2 device."""
    return SimpleNamespace(device=SimpleNamespace(device=phone, device_id="lab"))


def test_the_lab_action_backs_out_to_the_feed_by_the_production_function(monkeypatch):
    register_actions()
    calls = []
    production = navigation.leave_publish_flow

    def _spy(device, **kwargs):
        calls.append(device)
        return production(device, **kwargs)

    monkeypatch.setattr(navigation, "leave_publish_flow", _spy)
    phone = ScreenPhone("post_screen", EXIT_SCREENS, EXIT_BACKS)

    result = ACTION_REGISTRY["tt.publish.leave_flow"](_bundle(phone), {})

    assert result == {"success": True, "message": "feed reached"}
    assert calls == [phone]
    assert phone.keys == ["back"] * 4 and phone.taps == []


def test_a_feed_never_read_is_a_failure_of_the_action():
    register_actions()
    phone = ScreenPhone("post_screen", EXIT_SCREENS, EXIT_BACKS, unreadable=("feed",))

    result = ACTION_REGISTRY["tt.publish.leave_flow"](_bundle(phone), {})

    assert result["success"] is False
    assert "may still be on the publication" in result["message"]
