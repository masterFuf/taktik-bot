"""The caption field is focused through its selectors, or nothing is typed: no fixed point.

When no selector of the caption field answered, `_fill_caption` tapped a fixed point of the screen
(half its width, 30 % of its height, `tap_caption_focus_fallback`) and typed the caption anyway,
into whatever that tap had focused. Real screens of TikTok 47.0.3 in French (Pixel 6a, 1080x2400,
a publication piloted by hand on 2026-09-27, anonymized): on the editor, where the workflow can
land after a stray tap, the field does not exist; on the post screen, it is found by its id.
"""

import pytest

from screen_phone import ScreenPhone
from taktik.core.compat.selectors.setup import apply_version_overrides
from taktik.core.shared.device import adb
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.workflows.publish import upload_workflow as module

EDITOR = "tt4703_fr_publish_editor_no_sound.xml"
POST_SCREEN = "tt4703_fr_publish_post_screen.xml"


@pytest.fixture(autouse=True)
def tiktok_47_0_3_in_french(monkeypatch):
    set_active_locale("fr")
    apply_version_overrides("tiktok", "47.0.3")
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    yield
    apply_version_overrides("tiktok", "43.1.4")
    set_active_locale(None)


@pytest.fixture
def adb_commands(monkeypatch):
    """Every adb shell command sent (the keyboard's included); the phone answers none."""
    sent = []
    monkeypatch.setattr(adb, "_run_adb_shell", lambda device_id, command: sent.append(command) or "")
    return sent


def _workflow(screen: str) -> tuple[module.TikTokUploadWorkflow, ScreenPhone]:
    phone = ScreenPhone(screen, {screen: screen}, moves={})
    return module.TikTokUploadWorkflow(phone, "6a"), phone


def test_without_a_caption_field_nothing_is_tapped_nor_typed(adb_commands):
    workflow, phone = _workflow(EDITOR)

    assert workflow._fill_caption("Bonjour", ["paris"]) is False
    assert phone.taps == []
    assert adb_commands == []


def test_the_caption_field_found_is_the_one_tapped(adb_commands):
    workflow, phone = _workflow(POST_SCREEN)

    workflow._fill_caption("Bonjour", [])

    assert phone.tapped()[:1] == ["h8e"]
