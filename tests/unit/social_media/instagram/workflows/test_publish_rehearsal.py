"""The rehearsal mode must never publish.

`stop_before_share=True` is what lets the diagnostic bench walk the whole publish flow on a real
account without posting. If a change ever makes that flag tap the share button anyway, the bench
would publish for real — so the guarantee is pinned here rather than left to review.
"""
from taktik.core.social_media.instagram.actions.atomic.interaction.information_window import (
    InformationWindows,
)
from taktik.core.social_media.instagram.workflows.publish.post_workflow import (
    InstagramPostWorkflow,
)


class SpyWorkflow(InstagramPostWorkflow):
    """Replaces every screen interaction with a recorder, keeping the real orchestration."""

    def __init__(self, post_type: str, share_button_present=True):
        # Bypass __init__: it builds action facades against a live device.
        self.device = None
        self.device_id = "test-device"
        self._log = lambda *a, **k: None
        self._status = lambda *a, **k: None
        self.package_name = "com.instagram.android"
        self.post_type = post_type
        self.story_via_feed = False
        self._a = {}
        self.taps = []
        self.presence_checks = []
        # One answer per presence check, the last one repeated; a bool answers them all.
        self._share_answers = [share_button_present] if isinstance(share_button_present, bool)             else list(share_button_present)
        self.publish_commit_waited = False
        self.upload_end_waited = False
        self.back_presses = 0
        self.language_detections = 0
        self.information_windows_acknowledged = 0
        self.window_checks = 0

    # --- screen interactions, all recorded -------------------------------
    def _tap(self, selectors, timeout: float = 4.0) -> bool:
        self.taps.append(selectors)
        return True

    def _acknowledge_information_windows(self, unless_on_screen=(), wait_s: float = 6.0):
        self.window_checks += 1
        return InformationWindows()

    def _present(self, selectors, timeout: float = 4.0) -> bool:
        self.presence_checks.append(selectors)
        answers = self._share_answers
        return answers.pop(0) if len(answers) > 1 else answers[0]

    def _push_all(self, media_paths) -> bool:
        return True

    def _launch_and_home(self) -> None:
        pass

    def _detect_app_language(self) -> None:
        self.language_detections += 1

    def _open_creation_and_gallery(self):
        return None

    def _open_story_from_feed_tray(self):
        return None

    def _advance_to_composer(self, max_taps: int = 3) -> bool:
        return True

    def _fill_caption(self, text: str) -> bool:
        return True

    def _dismiss_keyboard(self) -> None:
        self.back_presses += 1

    def _wait_for_publish_commit(self, timeout: float = 120.0) -> bool:
        self.publish_commit_waited = True
        return True

    def _wait_for_upload_confirmation(self, *args, **kwargs) -> bool:
        self.upload_end_waited = True
        return False

    def _select_carousel(self, count: int) -> bool:
        return True


def _run(post_type: str, stop_before_share: bool, **kwargs):
    workflow = SpyWorkflow(post_type, **kwargs)
    # os.path.isfile is checked on media paths, so point at a file that exists: this one.
    result = workflow.execute(
        caption="hello",
        media_paths=[__file__],
        stop_before_share=stop_before_share,
    )
    return workflow, result


def test_rehearsal_reports_success_without_publishing():
    workflow, result = _run("post", stop_before_share=True)

    assert result["success"] is True
    assert "not published" in result["message"]
    # The share button was looked for, never tapped, and no publish commit was awaited.
    assert workflow.presence_checks, "the share button should have been checked for presence"
    assert workflow.publish_commit_waited is False
    assert workflow.upload_end_waited is False


def test_rehearsal_fails_when_the_share_screen_was_not_reached():
    workflow, result = _run("post", stop_before_share=True, share_button_present=False)

    assert result["success"] is False
    assert result["error_type"] == "share_not_found"
    assert workflow.publish_commit_waited is False


def test_story_rehearsal_does_not_publish_either():
    """The story flow has its own tail, so it needs its own guarantee."""
    workflow, result = _run("story", stop_before_share=True)

    assert result["success"] is True
    assert "not published" in result["message"]
    assert workflow.publish_commit_waited is False
    # The editor's information windows are looked for before "Your story", rehearsal included.
    assert workflow.window_checks == 1


def test_normal_run_still_publishes():
    """The flag must be opt-in: the production path is unchanged when it is not set."""
    workflow, result = _run("post", stop_before_share=False)

    assert result["success"] is True
    assert workflow.publish_commit_waited is True
    assert workflow.upload_end_waited is True
    assert workflow.presence_checks == []


def test_rehearsal_does_not_press_back_on_the_share_screen():
    """The caption editor is closed with OK, which returns to the composer. Back there leaves the
    composer, and the share button with it: the rehearsal failed on share_not_found (Pixel 3a,
    Instagram 410) while a real publish, which only presses Back when the button is hidden, went on."""
    workflow, result = _run("post", stop_before_share=True)

    assert result["success"] is True
    assert workflow.back_presses == 0


def test_rehearsal_presses_back_once_when_the_keyboard_hides_the_share_button():
    workflow, result = _run("post", stop_before_share=True, share_button_present=[False, True])

    assert result["success"] is True
    assert workflow.back_presses == 1
    assert len(workflow.presence_checks) == 2
