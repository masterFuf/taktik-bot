"""The story camera opens behind Android's camera and microphone prompts.

Pixel 3a, Android 12 in French, Instagram 410.0.0.53.71 in English: `taktik publish story <image>
--rehearse` failed with `gallery_item_not_found`. The STORY tab opened the camera, Android asked
for the camera, then for the microphone, and the workflow looked for the gallery button under
those prompts. The prompts here are the real dumps.
"""

import time
import types
from pathlib import Path

import pytest
from lxml import etree

from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.shared.device.ui_dump import iter_widgets, parse_bounds, parse_ui_dump
from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
    CONTENT_CREATION_SELECTORS as CC,
)
from taktik.core.social_media.instagram.workflows.publish.post_workflow import (
    InstagramPostWorkflow,
)

FIXTURES = Path(__file__).parents[3] / "shared" / "device" / "fixtures"
CAMERA = (FIXTURES / "android12_fr_permission_camera.xml").read_text(encoding="utf-8")
MICROPHONE = (FIXTURES / "android12_fr_permission_microphone.xml").read_text(encoding="utf-8")
APP = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    '<node index="0" text="" resource-id="com.instagram.android:id/quick_capture_root_container" '
    'class="android.widget.FrameLayout" package="com.instagram.android" content-desc="" '
    'clickable="false" enabled="true" bounds="[0,0][1080,2220]" /></hierarchy>'
)
ONE_TIME = "permission_allow_one_time_button"


def _without_one_time(xml: str) -> str:
    root = etree.fromstring(xml.encode("utf-8"))
    for node in root.iter("node"):
        if node.get("resource-id", "").endswith(ONE_TIME):
            node.getparent().remove(node)
    return etree.tostring(root, encoding="unicode")


class StoryPhone:
    """Instagram's story path with Android's prompts over the camera.

    App screens answer the workflow's selector lists; a tap on a list the screen shows moves to
    the next screen. Opening the camera raises the prompts; while one is up the app shows nothing
    and takes no tap. The prompts are read through the facade calls (`snapshot`, `human_tap`)."""

    def __init__(self, prompts=(), create_opens="creation"):
        self.screen = "feed"
        self._queued = list(prompts)
        self.prompts = []
        self.system_taps = []
        self._leads = [
            ("feed", CC.create_button_flow_xpaths(), create_opens),
            ("feed", CC.feed_story_tray_add_xpaths(), "camera"),
            ("creation", CC.destination_tab_xpaths("story"), "camera"),
            ("camera", CC.gallery_open_xpaths(), "gallery"),
            ("gallery", [CC.first_gallery_item_xpath()], "editor"),
        ]
        self._shown = {"gallery": CC.gallery_grid_xpaths(), "editor": CC.story_publish_xpaths()}

    # The app, as the workflow's click actions see it.
    def app_shows(self, selector: str) -> bool:
        if self.prompts:
            return False
        lists = [sels for screen, sels, _ in self._leads if screen == self.screen]
        lists.append(self._shown.get(self.screen, []))
        return any(selector in sels for sels in lists)

    def tap_app(self, selectors) -> bool:
        if self.prompts:
            return False
        selectors = [selectors] if isinstance(selectors, str) else list(selectors)
        for screen, sels, leads_to in self._leads:
            if screen == self.screen and any(s in sels for s in selectors):
                self.screen = leads_to
                if leads_to == "camera":
                    self.prompts, self._queued = self._queued, []
                return True
        return False

    def xpath(self, selector):
        return types.SimpleNamespace(exists=self.app_shows(selector))

    # The facade calls of the shared prompt answer.
    def snapshot(self, max_age_s=0.0):
        return ScreenSnapshot(self.prompts[0] if self.prompts else APP)

    def wait_for_snapshot(self, predicate, timeout, poll_ms=300):
        photo = self.snapshot()
        return photo if predicate(photo) else None

    def invalidate_snapshot(self):
        pass

    def human_tap(self, bounds, **_):
        tapped = ""
        for node in iter_widgets(parse_ui_dump(self.prompts[0] if self.prompts else APP)):
            if parse_bounds(node.get("bounds", "")) == tuple(bounds):
                tapped = node.get("resource-id", "")
        self.system_taps.append(tapped)
        if tapped.endswith(ONE_TIME):
            self.prompts.pop(0)
        return ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)


class Click:
    def __init__(self, phone):
        self.device = phone

    def _find_and_click(self, selectors, timeout=5.0, human_delay=True):
        return self.device.tap_app(selectors)

    def _is_element_present(self, selectors, timeout=None):
        selectors = [selectors] if isinstance(selectors, str) else selectors
        return any(self.device.app_shows(s) for s in selectors)

    def _wait_for_element(self, selectors, timeout=5.0, silent=False):
        return self._is_element_present(selectors)


class StoryRun(InstagramPostWorkflow):
    """The real story orchestration; media push, launch and language read are left out."""

    def __init__(self, phone, story_via_feed=False):
        self.device = phone
        self.device_id = "test-device"
        self._log = lambda *a, **k: None
        self._status = lambda *a, **k: None
        self.package_name = "com.instagram.android"
        self.post_type = "story"
        self.story_via_feed = story_via_feed
        self.permission_prompts_answered = 0
        self.information_windows_acknowledged = 0
        self._a = {"click": Click(phone)}

    def _push_all(self, media_paths) -> bool:
        return True

    def _launch_and_home(self) -> None:
        pass

    def _detect_app_language(self) -> None:
        pass


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda *_: None)


def _rehearse(phone, story_via_feed=False):
    workflow = StoryRun(phone, story_via_feed=story_via_feed)
    result = workflow.execute(media_paths=[__file__], stop_before_share=True)
    return workflow, result


@pytest.mark.parametrize("via_feed", [False, True], ids=["create_button", "feed_tray"])
def test_the_story_answers_both_prompts_only_this_time_and_reaches_its_share_screen(via_feed):
    phone = StoryPhone([CAMERA, MICROPHONE])

    workflow, result = _rehearse(phone, story_via_feed=via_feed)

    assert result["success"] is True, result
    assert phone.screen == "editor"
    assert workflow.permission_prompts_answered == 2
    assert phone.system_taps == [f"com.android.permissioncontroller:id/{ONE_TIME}"] * 2


def test_create_reopening_the_story_camera_answers_the_prompts_first():
    """Create reopens the last mode used: after a story, the story camera, prompts included."""
    phone = StoryPhone([CAMERA, MICROPHONE], create_opens="camera")

    workflow, result = _rehearse(phone)

    assert result["success"] is True, result
    assert workflow.permission_prompts_answered == 2


def test_a_prompt_without_the_one_time_choice_stops_the_story_with_its_reason():
    phone = StoryPhone([_without_one_time(CAMERA)])

    workflow, result = _rehearse(phone)

    assert result["success"] is False
    assert result["error_type"] == "permission_prompt_unanswered"
    assert "no_one_time_choice" in result["message"]
    assert phone.system_taps == []
    assert phone.screen == "camera"


def test_without_a_prompt_the_story_is_unchanged():
    phone = StoryPhone()

    workflow, result = _rehearse(phone)

    assert result["success"] is True, result
    assert workflow.permission_prompts_answered == 0
    assert phone.system_taps == []


class RawPhone:
    """A uiautomator2 device: the prompts' dumps, and the ids under each touch."""

    def __init__(self, *prompts):
        self.prompts = list(prompts)
        self.touched = []

    def dump_hierarchy(self, *_, **__):
        return self.prompts[0] if self.prompts else APP

    def _touch(self, x, y):
        touched = ""
        for node in iter_widgets(parse_ui_dump(self.dump_hierarchy())):
            b = parse_bounds(node.get("bounds", ""))
            if b and b[0] <= x < b[2] and b[1] <= y < b[3]:
                touched = node.get("resource-id", "")
        self.touched.append(touched)
        if touched.endswith(ONE_TIME):
            self.prompts.pop(0)

    def long_click(self, x, y, duration=0.1):
        self._touch(x, y)

    def click(self, x, y):
        self._touch(x, y)


def test_the_lab_action_runs_the_production_step_with_a_human_tap():
    """Same id on both sides (`actionCatalog` of the app); the workflow's own step, the facade's
    sampled tap point, never a coordinate: every touch lands inside "Only this time"."""
    from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    phone = RawPhone(CAMERA, MICROPHONE)

    result = ACTION_REGISTRY["publish.answer_permission_prompts"](
        types.SimpleNamespace(device=phone, device_id="device-1"), {})

    assert result["success"] is True, result
    assert result["details"] == {"answered": 2}
    assert phone.touched == [f"com.android.permissioncontroller:id/{ONE_TIME}"] * 2


def test_the_lab_action_reports_a_prompt_it_leaves_unanswered():
    from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    phone = RawPhone(_without_one_time(CAMERA))

    result = ACTION_REGISTRY["publish.answer_permission_prompts"](
        types.SimpleNamespace(device=phone, device_id="device-1"), {})

    assert result["success"] is False
    assert result["details"] == {"answered": 0, "error_type": "permission_prompt_unanswered"}
    assert phone.touched == []
