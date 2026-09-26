"""Android's camera and microphone prompts are answered "Only this time", never for good.

Dumps: Pixel 3a, Android 12 in French, over Instagram 410.0.0.53.71, when the story camera opens
(camera prompt, then microphone prompt). The window's package is
`com.google.android.permissioncontroller`, its ids carry `com.android.permissioncontroller`.
Variants (Google prefix, no one-time button, Android 9 installer) are derived from those dumps.
"""

import time
from pathlib import Path

import pytest
from lxml import etree

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device import permissions
from taktik.core.shared.device.permissions import (
    NO_ONE_TIME_CHOICE,
    TOO_MANY_PROMPTS,
    allow_prompts_this_time_only,
)
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.shared.device.ui_dump import iter_widgets, parse_bounds, parse_ui_dump
from taktik.core.shared.ui.selectors.system.permission_prompt import PERMISSION_PROMPT_SELECTORS

FIXTURES = Path(__file__).parent / "fixtures"
CAMERA = (FIXTURES / "android12_fr_permission_camera.xml").read_text(encoding="utf-8")
MICROPHONE = (FIXTURES / "android12_fr_permission_microphone.xml").read_text(encoding="utf-8")
INSTAGRAM_PROFILE = (
    Path(__file__).parents[2] / "social_media" / "instagram" / "fixtures"
    / "ig410_fr_profile_opened_from_search.xml"
).read_text(encoding="utf-8")
STORY_CAMERA = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    '<node index="0" text="" resource-id="com.instagram.android:id/quick_capture_root_container" '
    'class="android.widget.FrameLayout" package="com.instagram.android" content-desc="" '
    'clickable="false" enabled="true" bounds="[0,0][1080,2220]" /></hierarchy>'
)

ONE_TIME = "permission_allow_one_time_button"


def _without_one_time(xml: str) -> str:
    """The same prompt with only "Allow" and "Deny", as Android 10 and older draw it."""
    root = etree.fromstring(xml.encode("utf-8"))
    for node in root.iter("node"):
        if node.get("resource-id", "").endswith(ONE_TIME):
            node.getparent().remove(node)
        elif node.get("resource-id", "").endswith("permission_allow_foreground_only_button"):
            node.set("resource-id", node.get("resource-id").replace("foreground_only_", ""))
    return etree.tostring(root, encoding="unicode")


class PromptPhone:
    """A device facade: Android's prompts stacked over the app, the first one on screen.

    `human_tap` records the id of the button under the tapped bounds; the one-time button closes
    the prompt shown, unless the prompt ignores taps (`stuck`)."""

    def __init__(self, *prompts, app=STORY_CAMERA, stuck=False):
        self.prompts = list(prompts)
        self.app = app
        self.stuck = stuck
        self.tapped = []

    def _xml(self):
        return self.prompts[0] if self.prompts else self.app

    def snapshot(self, max_age_s=0.0):
        return ScreenSnapshot(self._xml())

    def wait_for_snapshot(self, predicate, timeout, poll_ms=300):
        photo = self.snapshot()
        return photo if predicate(photo) else None

    def invalidate_snapshot(self):
        pass

    def human_tap(self, bounds, **_):
        tapped = ""
        for node in iter_widgets(parse_ui_dump(self._xml())):
            if parse_bounds(node.get("bounds", "")) == tuple(bounds):
                tapped = node.get("resource-id", "")
        self.tapped.append(tapped)
        if tapped.endswith(ONE_TIME) and not self.stuck:
            self.prompts.pop(0)
        return ((bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2)


@pytest.fixture(autouse=True)
def no_reaction_pause(monkeypatch):
    monkeypatch.setattr(permissions.time, "sleep", lambda *_: None)


@pytest.mark.parametrize("xml", [CAMERA, MICROPHONE], ids=["camera", "microphone"])
def test_the_real_prompts_are_recognised(xml):
    photo = ScreenSnapshot(xml)
    assert photo.exists(PERMISSION_PROMPT_SELECTORS.prompt)
    assert photo.exists(PERMISSION_PROMPT_SELECTORS.allow_one_time)


@pytest.mark.parametrize("xml", [STORY_CAMERA, INSTAGRAM_PROFILE], ids=["story_camera", "profile"])
def test_an_app_screen_is_not_a_prompt(xml):
    assert not ScreenSnapshot(xml).exists(PERMISSION_PROMPT_SELECTORS.prompt)


def test_only_this_time_is_tapped_on_the_camera_prompt():
    phone = PromptPhone(CAMERA)

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.ok and outcome.answered == 1
    assert phone.tapped == [f"com.android.permissioncontroller:id/{ONE_TIME}"]
    assert "photos" in outcome.question


def test_camera_then_microphone_are_both_answered_only_this_time():
    phone = PromptPhone(CAMERA, MICROPHONE)

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.ok and outcome.answered == 2
    assert all(tapped.endswith(ONE_TIME) for tapped in phone.tapped)
    assert len(phone.tapped) == 2
    assert phone.prompts == []


def test_no_prompt_touches_nothing():
    phone = PromptPhone()

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.ok and outcome.answered == 0
    assert phone.tapped == []


@pytest.mark.parametrize("unless, ends_early", [
    (['//*[contains(@resource-id, "avatar_image_view")]'], True),
    ((), False),
], ids=["named_screen", "nothing_named"])
def test_a_screen_named_as_the_end_of_the_wait_ends_it_early(unless, ends_early):
    """The gallery grid means no camera: the publish flow does not wait for a prompt there."""
    waits = []

    class Watched(PromptPhone):
        def wait_for_snapshot(self, predicate, timeout, poll_ms=300):
            photo = self.snapshot()
            waits.append(predicate(photo))
            return photo if predicate(photo) else None

    phone = Watched(app=INSTAGRAM_PROFILE)

    outcome = allow_prompts_this_time_only(phone, unless_on_screen=unless)

    assert outcome.ok and outcome.answered == 0 and phone.tapped == []
    assert waits == [ends_early]


def test_a_prompt_without_the_one_time_choice_is_left_alone():
    """Android 10 and older: only Allow and Deny. Nothing is granted, the reason is given."""
    phone = PromptPhone(_without_one_time(CAMERA))

    outcome = allow_prompts_this_time_only(phone)

    assert not outcome.ok
    assert outcome.unanswered == NO_ONE_TIME_CHOICE
    assert phone.tapped == []


def test_the_second_prompt_without_the_one_time_choice_stops_after_the_first():
    phone = PromptPhone(CAMERA, _without_one_time(MICROPHONE))

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.unanswered == NO_ONE_TIME_CHOICE and outcome.answered == 1
    assert len(phone.tapped) == 1 and phone.tapped[0].endswith(ONE_TIME)


def test_the_ids_under_the_google_package_are_accepted_too():
    google = CAMERA.replace("com.android.permissioncontroller:id/",
                            "com.google.android.permissioncontroller:id/")
    phone = PromptPhone(google)

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.ok and outcome.answered == 1
    assert phone.tapped == [f"com.google.android.permissioncontroller:id/{ONE_TIME}"]


def test_the_android_9_installer_prompt_is_recognised_and_left_alone():
    installer = _without_one_time(CAMERA).replace("com.android.permissioncontroller:id/",
                                                  "com.android.packageinstaller:id/")
    phone = PromptPhone(installer)

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.unanswered == NO_ONE_TIME_CHOICE
    assert phone.tapped == []


def test_the_same_ids_under_an_app_package_are_not_a_prompt():
    """The clone proxy makes an id equality package-agnostic: these selectors must not rely on it."""
    foreign = CAMERA.replace("com.android.permissioncontroller:id/", "com.instagram.android:id/")
    phone = PromptPhone(foreign)

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.ok and outcome.answered == 0 and phone.tapped == []


def test_the_clone_proxy_leaves_every_prompt_selector_as_written():
    proxy = CloneAwareDeviceProxy(object(), "com.taktik.ig1")
    for selector in PERMISSION_PROMPT_SELECTORS.all_xpaths():
        assert proxy.rewrite_xpath(selector) == selector


def test_a_prompt_that_never_closes_is_tapped_at_most_three_times():
    phone = PromptPhone(CAMERA, stuck=True)

    outcome = allow_prompts_this_time_only(phone)

    assert outcome.unanswered == TOO_MANY_PROMPTS
    assert len(phone.tapped) == 3
    assert all(tapped.endswith(ONE_TIME) for tapped in phone.tapped)


def test_a_person_reads_the_prompt_before_answering(monkeypatch):
    pauses = []
    monkeypatch.setattr(permissions.time, "sleep", pauses.append)

    allow_prompts_this_time_only(PromptPhone(CAMERA))

    assert len(pauses) == 1 and 0.6 <= pauses[0] <= 1.5


def test_a_raw_device_is_wrapped_in_the_shared_facade(monkeypatch):
    seen = []

    class RawDevice:
        def dump_hierarchy(self):
            return STORY_CAMERA

    real_facade = permissions._as_facade

    def spy(device):
        facade = real_facade(device)
        seen.append(type(facade).__name__)
        return facade

    monkeypatch.setattr(permissions, "_as_facade", spy)
    started = time.monotonic()

    outcome = allow_prompts_this_time_only(RawDevice(), wait_s=0.0)

    assert outcome.ok and outcome.answered == 0
    assert seen == ["BaseDeviceFacade"]
    assert time.monotonic() - started < 2.0
