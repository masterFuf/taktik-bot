"""The publish flow reads the app language once Instagram is launched, before its first localized selector.

Create, Next, Share and the story button are localized (`content_creation.*` in the locales). The
publish bridge, `taktik publish` and the Lab bench all run `InstagramPostWorkflow.execute`, and none
of them read the language: the selectors stayed in the union of every locale whatever the phone showed.

The language is read in the start step the automation and the scraping take after their restart
(`prepare_instagram_selectors`), right after the launch and before the way home, whose tab ids are
matched to a clone in that same step (`test_publish_runs_the_clone_its_payload_names.py`).
"""
import pytest

from taktik.core.social_media.instagram.workflows.common import runtime_setup
from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow


class _WayHome:
    def __init__(self, steps: list):
        self.steps = steps

    def navigate_to_home(self) -> bool:
        self.steps.append("navigate_to_home")
        return True


class StageWorkflow(InstagramPostWorkflow):
    """The real orchestration, the real launch-and-home stage and the real language step; the screen
    stages are recorded."""

    def __init__(self, post_type: str, steps: list):
        self.device = object()
        self.device_id = "test-device"
        self._log = lambda *a, **k: None
        self._status = lambda *a, **k: None
        self.package_name = "com.instagram.android"
        self.post_type = post_type
        self.story_via_feed = False
        self._a = {"nav": _WayHome(steps)}
        self.steps = steps

    def _push_all(self, media_paths) -> bool:
        return True

    def _launch_app(self) -> None:
        self.steps.append("launch")

    def _open_creation_and_gallery(self):
        self.steps.append("open_creation")
        return {"success": False, "message": "stop here", "error_type": "test_stop"}


@pytest.fixture
def steps(monkeypatch):
    recorded = []
    monkeypatch.setattr(runtime_setup, "detect_and_optimize",
                        lambda device: recorded.append(("detect_language", device)) or "en")
    return recorded


@pytest.mark.parametrize("post_type", ["post", "reel", "carousel", "story"])
def test_the_language_is_read_after_the_launch_before_the_way_home_and_the_creation_screen(steps, post_type):
    workflow = StageWorkflow(post_type, steps)

    workflow.execute(caption="hello", media_paths=[__file__], stop_before_share=True)

    assert steps == ["launch", ("detect_language", workflow.device), "navigate_to_home", "open_creation"]
