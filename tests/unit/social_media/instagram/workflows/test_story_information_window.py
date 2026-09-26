"""An information window covers the story editor's "Your story" button.

Pixel 3a, Instagram 410.0.0.53.71 in English: a real story failed with `share_not_found`. Instagram
had laid "Your stories can now reach more people" over the editor, with "OK" and "View settings";
once closed with "OK", the same workflow published. The window here is that real dump, without the
system navigation bar. The editor under it is a minimal screen carrying the "Your story" button.
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

FIXTURES = Path(__file__).parents[1] / "fixtures"
WINDOW = (FIXTURES / "ig410_en_story_share_information_window.xml").read_text(encoding="utf-8")
PRIMARY = "com.instagram.android:id/igds_headline_primary_action_button"
SECONDARY = "com.instagram.android:id/igds_headline_secondary_action_text_button"
HEADLINE = "Your stories can now reach more people"
APP = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    '<node index="0" text="" resource-id="com.instagram.android:id/quick_capture_root_container" '
    'class="android.widget.FrameLayout" package="com.instagram.android" content-desc="" '
    'clickable="false" enabled="true" bounds="[0,0][1080,2220]" /></hierarchy>'
)
EDITOR = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    '<node index="0" text="" resource-id="com.instagram.android:id/quick_capture_root_container" '
    'class="android.widget.FrameLayout" package="com.instagram.android" content-desc="" '
    'clickable="false" enabled="true" bounds="[0,0][1080,2220]">'
    '<node index="0" text="Your story" resource-id="" class="android.widget.TextView" '
    'package="com.instagram.android" content-desc="" clickable="true" enabled="true" '
    'bounds="[40,1960][420,2060]" /></node></hierarchy>'
)


def _window_primary_labelled(label: str) -> str:
    """The same window, its primary action accepting something instead of acknowledging."""
    return WINDOW.replace('content-desc="OK"', f'content-desc="{label}"').replace('text="OK"', f'text="{label}"')


def _window_without_body() -> str:
    """The IGDS chassis without the promo structure: no body under the headline."""
    root = etree.fromstring(WINDOW.encode("utf-8"))
    for node in list(root.iter("node")):
        if node.get("resource-id", "").endswith("igds_headline_body"):
            node.getparent().remove(node)
    return etree.tostring(root, encoding="unicode")


class EditorPhone:
    """The story path, the editor read from real dumps.

    Up to the gallery the screens answer the workflow's selector lists (a tap on a list the screen
    shows moves on). The editor is a dump: the window while it is up, the editor once it is gone.
    Taps on the window are read from the node under the bounds the facade is given."""

    def __init__(self, window=WINDOW, window_after_first_look=False):
        self.screen = "feed"
        self.window = None if window_after_first_look else window
        self._late_window = window if window_after_first_look else None
        self.window_taps = []
        self.tapped_bounds = []
        self._leads = [
            ("feed", CC.create_button_flow_xpaths(), "creation"),
            ("creation", CC.destination_tab_xpaths("story"), "camera"),
            ("camera", CC.gallery_open_xpaths(), "gallery"),
            ("gallery", [CC.first_gallery_item_xpath()], "editor"),
        ]

    def xml(self) -> str:
        if self.screen == "editor":
            return self.window or EDITOR
        return APP

    # The app, as the workflow's click actions see it.
    def app_shows(self, selector: str) -> bool:
        if self.screen == "editor":
            return ScreenSnapshot(self.xml()).exists(selector)
        return any(selector in sels for screen, sels, _ in self._leads if screen == self.screen) or (
            self.screen == "gallery" and selector in CC.gallery_grid_xpaths())

    def tap_app(self, selectors) -> bool:
        selectors = [selectors] if isinstance(selectors, str) else list(selectors)
        if self.screen == "editor":
            if self._late_window is not None and selectors == CC.story_publish_xpaths():
                # The window comes up between the look and the tap.
                self.window, self._late_window = self._late_window, None
                return False
            if selectors == CC.story_publish_xpaths() and ScreenSnapshot(self.xml()).exists(selectors):
                self.screen = "published"
                return True
            return False
        for screen, sels, leads_to in self._leads:
            if screen == self.screen and any(s in sels for s in selectors):
                self.screen = leads_to
                return True
        return False

    def xpath(self, selector):
        return types.SimpleNamespace(exists=self.app_shows(selector))

    # The facade calls of the information window step.
    def snapshot(self, max_age_s=0.0):
        return ScreenSnapshot(self.xml())

    def wait_for_snapshot(self, predicate, timeout, poll_ms=300):
        photo = self.snapshot()
        return photo if predicate(photo) else None

    def invalidate_snapshot(self):
        pass

    def human_tap(self, bounds, **_):
        self.tapped_bounds.append(tuple(bounds))
        tapped = ""
        for node in iter_widgets(parse_ui_dump(self.xml())):
            if parse_bounds(node.get("bounds", "")) == tuple(bounds):
                tapped = node.get("resource-id", "")
        self.window_taps.append(tapped)
        if tapped == PRIMARY:
            self.window = None
        elif tapped == SECONDARY:
            self.screen = "settings"
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

    def __init__(self, phone):
        self.device = phone
        self.device_id = "test-device"
        self._log = lambda *a, **k: None
        self._status = lambda *a, **k: None
        self.package_name = "com.instagram.android"
        self.post_type = "story"
        self.story_via_feed = False
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


def _run(phone, stop_before_share=False):
    workflow = StoryRun(phone)
    result = workflow.execute(media_paths=[__file__], stop_before_share=stop_before_share)
    return workflow, result


def test_the_story_closes_the_window_with_ok_and_publishes():
    phone = EditorPhone()

    workflow, result = _run(phone)

    assert result["success"] is True, result
    assert phone.screen == "published"
    assert phone.window_taps == [PRIMARY]
    assert workflow.information_windows_acknowledged == 1


def test_the_tap_lands_inside_ok_never_on_view_settings():
    phone = EditorPhone()

    _run(phone)

    assert phone.tapped_bounds == [(133, 1725, 947, 1846)]
    assert SECONDARY not in phone.window_taps


def test_the_rehearsal_reaches_your_story_past_the_window_without_publishing():
    phone = EditorPhone()

    workflow, result = _run(phone, stop_before_share=True)

    assert result["success"] is True, result
    assert "not published" in result["message"]
    assert phone.screen == "editor"
    assert phone.window_taps == [PRIMARY]


def test_a_window_that_comes_up_after_the_button_showed_is_closed_then_the_tap_retried():
    phone = EditorPhone(window_after_first_look=True)

    workflow, result = _run(phone)

    assert result["success"] is True, result
    assert phone.screen == "published"
    assert phone.window_taps == [PRIMARY]


def test_a_window_whose_primary_action_does_not_acknowledge_is_left_alone():
    phone = EditorPhone(window=_window_primary_labelled("Turn on"))

    workflow, result = _run(phone)

    assert result["success"] is False
    assert result["error_type"] == "information_window_unanswered"
    assert HEADLINE in result["message"]
    assert phone.window_taps == []
    assert phone.screen == "editor"


def test_the_igds_chassis_without_the_promo_structure_is_not_touched():
    phone = EditorPhone(window=_window_without_body())

    workflow, result = _run(phone)

    assert result["success"] is False
    assert result["error_type"] == "share_not_found"
    assert phone.window_taps == []


def test_without_a_window_nothing_is_tapped_and_the_story_publishes():
    phone = EditorPhone(window=None)

    workflow, result = _run(phone)

    assert result["success"] is True, result
    assert phone.window_taps == []
    assert workflow.information_windows_acknowledged == 0


class RawPhone:
    """A uiautomator2 device: the window's dump, then the editor; the clickable under each touch."""

    def __init__(self, window=WINDOW):
        self.window = window
        self.touched = []

    def dump_hierarchy(self, *_, **__):
        return self.window or EDITOR

    def _touch(self, x, y):
        touched = ""
        for node in iter_widgets(parse_ui_dump(self.dump_hierarchy())):
            b = parse_bounds(node.get("bounds", ""))
            if node.get("clickable") == "true" and b and b[0] <= x < b[2] and b[1] <= y < b[3]:
                touched = node.get("resource-id", "")
        self.touched.append(touched)
        if touched == PRIMARY:
            self.window = None

    def long_click(self, x, y, duration=0.1):
        self._touch(x, y)

    def click(self, x, y):
        self._touch(x, y)


def test_the_lab_action_runs_the_production_step_with_a_human_tap():
    """Same id on both sides (`actionCatalog` of the app); the workflow's own step, the facade's
    sampled tap point, never a coordinate: the touch lands inside "OK"."""
    from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    phone = RawPhone()

    result = ACTION_REGISTRY["publish.dismiss_story_promo"](
        types.SimpleNamespace(device=phone, device_id="device-1"), {})

    assert result["success"] is True, result
    assert result["details"] == {"acknowledged": 1}
    assert phone.touched == [PRIMARY]


class RelayPhone(RawPhone):
    """The raw device the story relay drives: its taps also go through `xpath(...)`."""

    def __init__(self, window=WINDOW):
        super().__init__(window)
        self.published = False

    def _touch(self, x, y):
        on_editor = self.window is None
        super()._touch(x, y)
        if on_editor and self.touched[-1] == "your_story":
            self.published = True

    def dump_hierarchy(self, *_, **__):
        return self.window or EDITOR.replace('text="Your story" resource-id=""',
                                             'text="Your story" resource-id="your_story"')

    def xpath(self, selector):
        node = ScreenSnapshot(self.dump_hierarchy()).first(selector)
        phone = self

        class Element:
            exists = node is not None

            def get(self, timeout=0.5):
                return types.SimpleNamespace(bounds=node.bounds)

            def click(self):
                phone._touch((node.bounds[0] + node.bounds[2]) // 2, (node.bounds[1] + node.bounds[3]) // 2)

        return Element()


def test_the_story_relay_publishes_past_the_same_window():
    """The relay taps the same "Your story" button, through the same step."""
    from taktik.core.social_media.instagram.actions.business.actions.story_relay import (
        StoryRelayBusiness,
    )

    phone = RelayPhone()

    assert StoryRelayBusiness(phone).publish_opened_story() is True
    assert phone.touched == [PRIMARY, "your_story"]
    assert phone.published is True


def test_the_lab_action_reports_a_window_it_leaves_on_screen():
    from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    phone = RawPhone(_window_primary_labelled("Turn on"))

    result = ACTION_REGISTRY["publish.dismiss_story_promo"](
        types.SimpleNamespace(device=phone, device_id="device-1"), {})

    assert result["success"] is False
    assert result["details"] == {"acknowledged": 0, "error_type": "information_window_unanswered"}
    assert phone.touched == []
