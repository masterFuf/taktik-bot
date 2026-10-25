"""An Instagram publication reads and drives the Instagram its payload names, as the automation and the
scraping do.

The app hands the publication the clone chosen for the phone (`packageName`, the launch gate's), and the
publication launched that clone, then looked for its tab bar, its Create button and its gallery with the
official package's ids: it never made the clone the active package nor matched the selectors to it
(`activate_instagram_package` and `prepare_instagram_selectors(package_name=...)`, the automation's and
the scraping's start step). On a clone the way home found no tab, judged Instagram closed by the
official package and opened the official app: another account published. The publication now matches
the selectors to the app it launched, right after the launch and before its first selector, as the
automation and the scraping do after their restart.

The run goes through `run_instagram_publish`, the one launcher of the bridge, the CLI and the Lab; only
the screen is replaced.
"""

from __future__ import annotations

import pytest

from taktik.core.clone import get_active_package, set_active_package
from taktik.core.social_media.instagram.workflows.common import runtime_setup
from taktik.core.social_media.instagram.workflows.publish.agent_handler import run_instagram_publish
from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow

INSTAGRAM = "com.instagram.android"
CLONE = "com.taktik.ig1"


class _WayHome:
    """The way home, recorded with the package that is active when it starts looking for the tab."""

    def __init__(self, calls: list):
        self.calls = calls

    def navigate_to_home(self) -> bool:
        self.calls.append(f"navigate_to_home active={get_active_package()}")
        return True


def _screenless(calls: list):
    """The production workflow, its orchestration and start step real; the screen is recorded."""

    class Screenless(InstagramPostWorkflow):
        @staticmethod
        def _build_actions(device) -> dict:
            return {"nav": _WayHome(calls)}

        def _push_all(self, media_paths) -> bool:
            return True

        def _launch_app(self) -> None:
            calls.append(f"launch {self.package_name}")

        def _open_creation_and_gallery(self):
            calls.append("open_creation")
            return self._error("test_stop", "stop before the creation screen")

    return Screenless


@pytest.fixture
def calls(monkeypatch):
    recorded: list = []
    monkeypatch.setattr(runtime_setup, "patch_selectors_for_package",
                        lambda platform, package: recorded.append(f"clone_patch {platform} {package}") or 0)
    monkeypatch.setattr(runtime_setup, "detect_and_optimize",
                        lambda device: recorded.append("detect_language") or "en")
    set_active_package(INSTAGRAM)
    yield recorded
    set_active_package(INSTAGRAM)


def _publish(calls: list, **payload):
    return run_instagram_publish(
        {"deviceId": "emulator-5554", "postType": "post", "mediaPaths": [__file__], "caption": "hello",
         **payload},
        device_id="emulator-5554",
        connect=lambda: object(),
        workflow_factory=_screenless(calls),
    )


def test_a_publication_launches_the_clone_its_payload_names(calls):
    _publish(calls, packageName=CLONE)

    assert f"launch {CLONE}" in calls, calls


def test_a_publication_matches_the_selectors_to_its_clone_before_the_way_home(calls):
    _publish(calls, packageName=CLONE)

    patched = calls.index(f"clone_patch instagram {CLONE}")
    home = next(i for i, call in enumerate(calls) if call.startswith("navigate_to_home"))
    assert calls.index(f"launch {CLONE}") < patched < home, calls


def test_a_publication_makes_its_clone_the_active_package_before_the_way_home(calls):
    _publish(calls, packageName=CLONE)

    # The way home reopens Instagram by the active package when it cannot see the tab bar.
    assert f"navigate_to_home active={CLONE}" in calls, calls
    assert get_active_package() == CLONE


def test_a_publication_reads_the_app_language_before_the_creation_screen(calls):
    _publish(calls, packageName=CLONE)

    assert calls.index("detect_language") < calls.index("open_creation"), calls


def test_a_publication_without_a_clone_drives_the_official_app(calls):
    _publish(calls)

    assert f"launch {INSTAGRAM}" in calls, calls
    assert f"navigate_to_home active={INSTAGRAM}" in calls, calls
    assert not [call for call in calls if call.startswith("clone_patch") and INSTAGRAM not in call], calls
