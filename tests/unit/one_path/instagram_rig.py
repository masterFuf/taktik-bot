"""A recording phone for the Instagram automation one-path tests.

The same page payload goes through the desktop bridge (`desktop_bridge`) and through the CLI
(`taktik workflows run instagram.automation.<type>`). Every seam below is one the production code
looks up at call time, so the rig holds whichever side owns a step. Nothing here reaches adb, the
network or the database.
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

DEVICE_ID = "emulator-5554"
INSTAGRAM = "com.instagram.android"
INSTALLED_VERSION = "410.0.0.53.71"
AI_KEY = "sk-or-v1-" + "b" * 48

#: The run totals the fake automation reports, the shape `final_stats()` returns.
FINAL_STATS = {"likes": 0, "follows": 0, "comments": 0, "unfollows": 0, "interactions": 3}


def feed_payload(**overrides) -> dict:
    """What the Feed page sends, with what Electron adds (warmup caps, pacing profile)."""
    payload = {
        "deviceId": DEVICE_ID,
        "workflowType": "feed",
        "target": "feed",
        "limits": {"maxProfiles": 3, "minLikesPerProfile": 1, "maxLikesPerProfile": 2, "maxFeedStoryProfiles": 5},
        "probabilities": {"like": 0, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0,
                          "feedStoryReaction": 0},
        "feedStories": {"enabled": False, "maxProfiles": 5, "reaction": "laugh"},
        "filters": {"minFollowers": 0, "maxFollowers": 100000, "minPosts": 0, "maxFollowing": 10000,
                    "allowPrivate": False, "skipFollowsUs": True, "skipAlreadyFollowing": True},
        "session": {"durationMinutes": 30},
        "comments": {"customComments": []},
        "feed": {"skipSuggested": True, "readCaptions": True, "browseCarousels": False, "captureAds": False},
        "language": "fr",
        "warmupPolicy": {"maxActionsPerDay": 40, "maxFollowsPerDay": 5, "maxCommentsPerDay": 0,
                         "maxUnfollowsPerDay": 10, "minActionGapSeconds": 12, "maxActionsPerSession": 20},
        "behaviorPolicy": {"profile": "prudent"},
    }
    payload.update(overrides)
    return payload


def target_payload(**overrides) -> dict:
    """What the Target page sends for two sources, split one after the other."""
    payload = {
        "deviceId": DEVICE_ID,
        "workflowType": "target_followers",
        "target": "alpha,beta",
        "distribution": "sequential",
        "limits": {"maxProfiles": 4, "minLikesPerProfile": 1, "maxLikesPerProfile": 2},
        "probabilities": {"like": 0, "follow": 0, "comment": 0, "watchStories": 0, "likeStories": 0},
        "filters": {"minFollowers": 10, "maxFollowers": 5000, "minPosts": 1, "maxFollowing": 2000,
                    "allowPrivate": True, "allowVerified": False, "allowBusiness": True},
        "session": {"durationMinutes": 20, "minDelay": 4, "maxDelay": 9, "maxConsecutiveKnownUsernames": 40},
        "language": "fr",
        "warmupPolicy": {"maxActionsPerDay": 30, "maxFollowsPerDay": 0, "maxCommentsPerDay": 0,
                         "maxUnfollowsPerDay": 0, "minActionGapSeconds": 8, "maxActionsPerSession": 15},
    }
    payload.update(overrides)
    return payload


class InstagramRig:
    DEVICE_ID = DEVICE_ID

    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        self.tmp_path = tmp_path
        self.calls: list[str] = []
        self.events: list[tuple[str, dict]] = []
        self.workflows: list = []
        self.ai_services: list[dict] = []
        self.ai_installs: list[dict] = []
        self.built_config: dict | None = None
        self.cli_results: list = []
        self.signal_handlers: dict = {}
        self.connect_ok = True
        self.installed = True
        self.launch_ok = True
        self.workflow_raises: Exception | None = None
        self._install()

    # ------------------------------------------------------------------ fakes

    def _install(self) -> None:
        rig = self
        mp = self.monkeypatch

        import signal
        import time

        mp.setattr(time, "sleep", lambda *_a, **_k: None)
        mp.setattr(signal, "signal", lambda signum, handler: rig.signal_handlers.__setitem__(signum, handler))

        from bridges.common.runtime import ipc as ipc_module

        def _send(_self, msg_type, **kwargs):
            if msg_type != "step_metric":
                rig.events.append((msg_type, kwargs))

        mp.setattr(ipc_module.IPC, "send", _send)

        from bridges.common.runtime import signal_handler

        mp.setattr(signal_handler, "_workflow", None)

        from bridges.common.device import network

        mp.setattr(network, "measure_network_baseline",
                   lambda device_id: rig.calls.append(f"network_baseline {device_id}"))

        import taktik.core.database as database

        mp.setattr(database, "configure_db_service", lambda *a, **k: rig.calls.append("configure_db"))

        class FakeDevice:
            serial = DEVICE_ID

        self.device = FakeDevice()

        class FakeDeviceManager:
            def __init__(self):
                self.device = rig.device
                self.device_id = DEVICE_ID

            def connect(self, device_id=None):
                rig.calls.append(f"cli_connect {device_id}")
                return True

            def is_app_installed(self, package):
                rig.calls.append(f"is_installed {package}")
                return rig.installed

            def launch_app(self, package, activity=None, stop_first=False):
                rig.calls.append(f"launch {package} {activity} stop_first={stop_first}")
                return rig.launch_ok

            def stop_app(self, package):
                rig.calls.append(f"stop {package}")
                return True

        self.device_manager = FakeDeviceManager()

        class FakeConnection:
            def __init__(self, device_id=None):
                self.device_id = device_id
                self.device_manager = None
                self.device = None

            def connect(self):
                rig.calls.append(f"connect {self.device_id}")
                if not rig.connect_ok:
                    return False
                self.device_manager = rig.device_manager
                self.device = rig.device
                return True

            def check_atx_health(self, repair=True, max_retries=3):
                rig.calls.append(f"atx_health repair={repair} retries={max_retries}")
                return {"atx_healthy": True}

        mp.setattr("bridges.common.device.connection.ConnectionService", FakeConnection)
        from bridges.instagram.automation.runtime import session as session_module

        mp.setattr(session_module, "ConnectionService", FakeConnection)

        from bridges.common.device import app_manager

        def fake_version(device_id, package, platform):
            rig.calls.append(f"installed_version {package}")
            return INSTALLED_VERSION

        mp.setattr(app_manager, "get_installed_app_version", fake_version)

        # The selector and language setup of a run, recorded instead of applied.
        from taktik.core.social_media.instagram.workflows.core import runtime_setup

        mp.setattr(runtime_setup, "set_active_package", lambda package: rig.calls.append(f"active_package {package}"))
        mp.setattr(runtime_setup, "patch_selectors_for_package",
                   lambda platform, package: rig.calls.append(f"clone_patch {package}") or 0)
        mp.setattr(runtime_setup, "detect_and_optimize",
                   lambda device, *a, **k: rig.calls.append("detect_language") or "fr")
        from taktik.core.compat.selectors import setup as compat_setup

        mp.setattr(compat_setup, "apply_version_overrides",
                   lambda platform, version: rig.calls.append(f"version_overrides {version}") or 0)

        from taktik.core.social_media.instagram.workflows.core.automation import InstagramAutomation

        def fake_init(automation, device_manager, config=None, session_name=None):
            automation.device_manager = device_manager
            automation.device = getattr(device_manager, "device", None)
            automation.config = config
            automation.stats = dict(FINAL_STATS)
            rig.workflows.append(automation)

        def fake_run(automation):
            rig.calls.append("run_workflow")
            rig.built_config = json.loads(json.dumps(automation.config))
            if rig.workflow_raises is not None:
                raise rig.workflow_raises

        mp.setattr(InstagramAutomation, "__init__", fake_init)
        mp.setattr(InstagramAutomation, "run_workflow", fake_run)
        mp.setattr(InstagramAutomation, "final_stats", lambda automation: dict(FINAL_STATS))

        # The AI service the run asks for, and the hooks it installs.
        def fake_create_ai_service(*, ai_config, ipc=None, log=None, ready_message=None, **_kwargs):
            key = (ai_config or {}).get("openrouterApiKey")
            if not (ai_config or {}).get("enabled") or not key:
                return False, None
            service = {"service": len(rig.ai_services) + 1, "key": key}
            rig.ai_services.append({"key": key, "ipc": ipc is not None})
            return True, service

        mp.setattr("taktik.core.app.ai.factory.create_ai_service", fake_create_ai_service)
        mp.setattr("bridges.instagram.runtime.ai.create_ai_service", fake_create_ai_service)

        def fake_install(*, ai, ai_config, device=None, language="en", log=None, decision_provider=None, **_k):
            rig.ai_installs.append({
                "ai": ai,
                "ai_config": dict(ai_config or {}),
                "device": device is rig.device,
                "language": language,
                "decision_provider": decision_provider is not None,
            })

        mp.setattr("taktik.core.social_media.instagram.workflows.core.ai_hooks.install_instagram_ai_hooks",
                   fake_install)

    # ------------------------------------------------------------------ paths

    def run_bridge(self, payload: dict) -> int:
        """The desktop path: `desktop_bridge <config.json>`, to its exit code."""
        config_path = self.tmp_path / "instagram_config.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        self.monkeypatch.setattr(sys, "argv", ["desktop_bridge", str(config_path)])

        from bridges.instagram.automation import desktop

        self.monkeypatch.setattr(desktop, "setup_stats_callback", lambda: self.calls.append("stats_callback"))
        with pytest.raises(SystemExit) as exit_info:
            desktop.main()
        return exit_info.value.code

    def run_cli(self, payload: dict, env: dict | None = None, workflow_id: str | None = None):
        """The standalone path: `taktik workflows run instagram.automation.<type>`."""
        from click.testing import CliRunner

        from taktik.cli.commands import workflow_cmds

        workflow_id = workflow_id or f"instagram.automation.{payload['workflowType']}"
        self.monkeypatch.setattr(workflow_cmds, "_connect", lambda device_id: (self.device_manager, DEVICE_ID))
        print_result = workflow_cmds._print_result

        def keep_result(result):
            self.cli_results.append(result)
            print_result(result)

        self.monkeypatch.setattr(workflow_cmds, "_print_result", keep_result)
        return CliRunner().invoke(
            workflow_cmds.workflows,
            ["run", workflow_id, "--device", DEVICE_ID, "--json", json.dumps(payload)],
            env=env,
        )

    def reset(self) -> None:
        self.calls.clear()
        self.events.clear()
        self.workflows.clear()
        self.ai_services.clear()
        self.ai_installs.clear()
        self.built_config = None


__all__ = [
    "AI_KEY",
    "DEVICE_ID",
    "FINAL_STATS",
    "INSTAGRAM",
    "INSTALLED_VERSION",
    "InstagramRig",
    "feed_payload",
    "target_payload",
]
