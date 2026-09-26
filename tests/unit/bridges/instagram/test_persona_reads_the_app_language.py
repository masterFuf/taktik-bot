"""The persona analysis reads the app language after its restart, before the profile's reads.

The profile, its posts and its comments are read with localized selectors (private notice, "more"
of a bio, counters); the bridge never read the language, so they stayed in the union of every
locale whatever the phone showed.
"""
from bridges.instagram.analysis.runtime.persona_bridge import PersonaAnalysisBridge
from taktik.core.social_media.instagram.workflows.core import runtime_setup


def test_the_language_is_read_after_the_restart_and_before_the_profile(monkeypatch):
    steps = []

    import time

    monkeypatch.setattr(time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr("bridges.common.runtime.ipc.IPC.send", lambda _self, *a, **k: None)
    monkeypatch.setattr(runtime_setup, "detect_and_optimize",
                        lambda device: steps.append(("detect_language", device)) or "en")

    class App:
        def restart(self):
            steps.append("restart")
            return True

    bridge = PersonaAnalysisBridge.__new__(PersonaAnalysisBridge)
    bridge.target_username = "alpha"
    bridge.profile_screenshot_only = True
    bridge._app = App()
    bridge.device = object()

    def open_target_profile(_collected):
        steps.append("open_target_profile")
        return None, {"success": False, "error": "stop here"}

    bridge.open_target_profile = open_target_profile

    bridge.run()

    assert steps == ["restart", ("detect_language", bridge.device), "open_target_profile"]
