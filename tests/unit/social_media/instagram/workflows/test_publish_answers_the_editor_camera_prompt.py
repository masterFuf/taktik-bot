"""The Next loop of the publication answers the camera prompt the video editor raises, only this time.

Measured on a Pixel 3a (Instagram 410 in English, Android in French), Lab auto-test, 2026-09-28: the
first medium of the gallery was a video; the gallery's Next opened the video editor, and Android asked
for the camera over it. `_advance_to_composer` tapped nothing it could find under the prompt and
answered "composer not reached". The prompts were answered only when creation opened, and there the
gallery showed without a camera: in an app session without a grant, every video post stopped there.

The screens are real dumps, anonymized: the gallery with the video selected, the camera prompt over
the editor, the editor alone (the reel editor fixture), the caption screen. The phone answers `xpath`
from the screen on show; the gallery's Next raises the prompt, "Only this time" leaves the editor, the
editor's Next opens the caption screen.
"""

import pytest
from lxml import etree
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow
from unit.paths import CORE

PKG = "com.instagram.android"
FIXTURES = CORE / "tests/unit/social_media/instagram/fixtures"
SCREENS = {
    "gallery": (FIXTURES / "ig410_en_new_post_gallery_video_selected.xml").read_text(encoding="utf-8"),
    "camera prompt": (FIXTURES / "ig410_en_video_editor_camera_prompt_fr_system.xml").read_text(encoding="utf-8"),
    "editor": (FIXTURES / "ig410_en_reel_editor.xml").read_text(encoding="utf-8"),
    "composer": (FIXTURES / "ig410_en_new_reel_composer_download_nux.xml").read_text(encoding="utf-8"),
}
#: What a tap opens: (screen, resource-id of the element under the finger) -> the screen it brings up.
DOORS = {
    ("gallery", f"{PKG}:id/next_button_textview"): "camera prompt",
    ("camera prompt", "com.android.permissioncontroller:id/permission_allow_one_time_button"): "editor",
    ("editor", f"{PKG}:id/clips_right_action_button"): "composer",
}


def _bounds(node):
    left_top, right_bottom = node.get("bounds")[1:-1].split("][")
    left, top = (int(v) for v in left_top.split(","))
    right, bottom = (int(v) for v in right_bottom.split(","))
    return left, top, right, bottom


class _Phone:
    """uiautomator2 as the publication touches it, on the screen on show."""

    wait_timeout = 0.0

    def __init__(self):
        self.screen = "gallery"
        self.tapped = []
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *_a, **_k):
        return SCREENS[self.screen]

    def app_current(self):
        return {"package": PKG, "activity": "com.instagram.mainactivity.InstagramMainActivity"}

    def window_size(self):
        return 1080, 2220

    def click(self, x, y):
        root = etree.fromstring(SCREENS[self.screen].encode("utf-8"))
        for (screen, rid), opened in DOORS.items():
            if screen != self.screen:
                continue
            for node in root.iter("node"):
                left, top, right, bottom = _bounds(node)
                if node.get("resource-id") == rid and left <= x <= right and top <= y <= bottom:
                    self.tapped.append(rid.rsplit("/", 1)[-1])
                    self.screen = opened
                    return

    def long_click(self, x, y, _duration=0.0):
        self.click(x, y)

    def press(self, *_a):
        return True


@pytest.fixture(autouse=True)
def _quick(monkeypatch):
    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)


def test_the_camera_prompt_over_the_editor_is_answered_only_this_time_and_the_caption_screen_reached():
    phone = _Phone()
    workflow = InstagramPostWorkflow(phone, "lab", package_name=PKG, log=lambda *_a: None, status=lambda *_a: None)
    assert workflow._advance_to_composer() is True
    assert phone.screen == "composer"
    assert "permission_allow_one_time_button" in phone.tapped
    assert workflow.permission_prompts_answered == 1


def test_the_other_answers_of_the_prompt_are_never_tapped():
    phone = _Phone()
    workflow = InstagramPostWorkflow(phone, "lab", package_name=PKG, log=lambda *_a: None, status=lambda *_a: None)
    workflow._advance_to_composer()
    assert not any("foreground_only" in rid or "deny" in rid for rid in phone.tapped)

