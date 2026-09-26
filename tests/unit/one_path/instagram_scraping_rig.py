"""A recording phone for the Instagram scraping one-path tests.

The same scraping payload goes through the desktop bridge (`scraping_bridge <config.json>`) and
through the CLI (`taktik workflows run instagram.scraping.<type>`). Every seam below is one the
production code looks up at call time. Nothing here reaches adb, the network or the database.
"""
from __future__ import annotations

import io
import json
import sys

import pytest

DEVICE_ID = "emulator-5554"
INSTAGRAM = "com.instagram.android"
AI_KEY = "sk-or-v1-" + "c" * 48


def target_payload(**overrides) -> dict:
    """What the Scraping page sends for the followers of two accounts, filters set."""
    payload = {
        "deviceId": DEVICE_ID,
        "type": "target",
        "targetUsernames": ["alpha", "beta"],
        "scrapeType": "followers",
        "scrapePostLikers": True,
        "scrapePostCommenters": False,
        "maxProfiles": 3,
        "sessionDurationMinutes": 20,
        "exportCsv": False,
        "saveToDb": True,
        "enrichProfiles": True,
        "fetchLocation": True,
        "minFollowers": 10,
        "maxFollowers": 0,
        "minFollowing": None,
        "maxFollowing": 2000,
        "minPosts": 1,
        "requireProfilePicture": True,
        "skipPrivateProfiles": False,
        "rescrapeAfterDays": 0,
        "deepQualify": True,
        "deepQualifyMaxFollowing": 12,
        "appLanguage": "fr",
    }
    payload.update(overrides)
    return payload


def hashtag_payload(**overrides) -> dict:
    payload = {
        "deviceId": DEVICE_ID,
        "type": "hashtag",
        "hashtags": ["cuisine", "recette"],
        "scrapeHashtagLikers": False,
        "scrapeHashtagCommenters": True,
        "maxProfiles": 4,
        "maxPosts": 6,
        "sessionDurationMinutes": 15,
        "exportCsv": False,
        "saveToDb": True,
        "minPosts": 2,
        "ai": {"enabled": True, "profileAnalysis": True, "niche": "food", "qualificationPrompt": "Cooks only",
               "openrouterApiKey": AI_KEY, "visionModel": "vision-x", "nicheTaxonomy": {"food": ["baking"]}},
        "aiRescrapeMode": "stats_only",
    }
    payload.update(overrides)
    return payload


def post_url_payload(**overrides) -> dict:
    payload = {
        "deviceId": DEVICE_ID,
        "type": "post_url",
        "postUrls": ["https://www.instagram.com/p/AbC123/", "https://www.instagram.com/reel/XyZ9/"],
        "scrapePostUrlLikers": False,
        "scrapePostUrlCommenters": True,
        "maxProfiles": 5,
        "sessionDurationMinutes": 10,
        "exportCsv": False,
        "saveToDb": True,
    }
    payload.update(overrides)
    return payload


def usernames_payload(**overrides) -> dict:
    payload = {
        "deviceId": DEVICE_ID,
        "type": "usernames",
        "usernames": ["first_account", "second_account"],
        "sourceName": "shortlist",
        "maxProfiles": 2,
        "sessionDurationMinutes": 10,
        "exportCsv": False,
        "saveToDb": True,
        "skipPrivateProfiles": True,
    }
    payload.update(overrides)
    return payload


def profile_posts_payload(**overrides) -> dict:
    payload = {
        "deviceId": DEVICE_ID,
        "type": "profile_posts",
        "targetUsernames": ["alpha"],
        "maxPostsPerTarget": 0,
        "maxProfiles": 1,
        "sessionDurationMinutes": 10,
        "exportCsv": False,
        "saveToDb": True,
    }
    payload.update(overrides)
    return payload


class InstagramScrapingRig:
    DEVICE_ID = DEVICE_ID

    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        self.tmp_path = tmp_path
        self.calls: list[str] = []
        self.events: list[tuple[str, dict]] = []
        self.stdout_lines: list = []
        self.configs: list[dict] = []
        self.ai_builds: list[dict] = []
        self.cli_results: list = []
        self.connect_ok = True
        self.installed = True
        self.installed_version = "410.0.0.53.71"
        self.run_result = {"success": True, "total_scraped": 2, "completion_reason": "limit_reached"}
        self.run_raises: Exception | None = None
        self._install()

    @property
    def built_config(self) -> dict | None:
        return self.configs[-1] if self.configs else None

    def _install(self) -> None:
        rig = self
        mp = self.monkeypatch

        import signal
        import time

        mp.setattr(time, "sleep", lambda *_a, **_k: None)
        mp.setattr(signal, "signal", lambda signum, handler: None)

        from bridges.common.runtime import ipc as ipc_module

        def _send(_self, msg_type, **kwargs):
            if msg_type != "step_metric":
                rig.events.append((msg_type, kwargs))

        mp.setattr(ipc_module.IPC, "send", _send)

        import taktik.core.database as database

        mp.setattr(database, "configure_db_service", lambda *a, **k: rig.calls.append("configure_db"))
        from bridges.instagram.scraping.runtime import session as session_module

        mp.setattr(session_module, "configure_db_service", lambda *a, **k: rig.calls.append("configure_db"))

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
                return True

            def stop_app(self, package):
                rig.calls.append(f"stop {package}")
                return True

        self.device_manager = FakeDeviceManager()

        class FakeConnection:
            def __init__(self, device_id=None):
                self.device_id = device_id
                self.device_manager = None
                self.device = None
                rig.calls.append(f"connection {device_id}")

            def connect(self):
                rig.calls.append("connect")
                if not rig.connect_ok:
                    return False
                self.device_manager = rig.device_manager
                self.device = rig.device
                return True

            def disconnect(self):
                rig.calls.append("disconnect")

        mp.setattr("bridges.common.device.connection.ConnectionService", FakeConnection)
        mp.setattr(session_module, "ConnectionService", FakeConnection)

        from bridges.common.device import app_manager

        def fake_version(device_id, package, platform):
            rig.calls.append(f"installed_version {package}")
            return rig.installed_version

        mp.setattr(app_manager, "get_installed_app_version", fake_version)

        # The selector and language setup of a run, recorded instead of applied.
        from taktik.core.social_media.instagram.workflows.core import runtime_setup

        mp.setattr(runtime_setup, "patch_selectors_for_package",
                   lambda platform, package: rig.calls.append(f"clone_patch {package}") or 0)
        mp.setattr(runtime_setup, "detect_and_optimize",
                   lambda device, *a, **k: rig.calls.append("detect_language") or "en")
        from taktik.core.compat.selectors import setup as compat_setup

        mp.setattr(compat_setup, "apply_version_overrides",
                   lambda platform, version: rig.calls.append(f"version_overrides {version}") or 0)

        def fake_build_ai_service(*, api_key, ipc=None, vision_model=None, text_model=None, niche_taxonomy=None):
            rig.ai_builds.append({"api_key": api_key, "ipc": ipc is not None, "vision_model": vision_model,
                                  "niche_taxonomy": niche_taxonomy})
            return {"ai": len(rig.ai_builds)}

        mp.setattr("taktik.core.app.ai.factory.build_ai_service", fake_build_ai_service)
        mp.setattr("bridges.instagram.scraping.runtime.ai.build_ai_service", fake_build_ai_service)

        from taktik.core.social_media.instagram.workflows.scraping.scraping_workflow import ScrapingWorkflow

        def fake_init(workflow, device_manager, config, ai_notifier=None, ai_service=None, ai_service_factory=None):
            workflow.device_manager = device_manager
            workflow.config = config
            rig.configs.append(json.loads(json.dumps(config)))
            rig.calls.append(f"workflow notifier={ai_notifier is not None} ai_factory={ai_service_factory is not None}")
            # What the real constructor does with the factory, so the AI build is observed.
            if config.get("ai_mode") and ai_service is None and config.get("openrouter_api_key") and ai_service_factory:
                ai_service_factory(
                    api_key=config["openrouter_api_key"],
                    ipc=ai_notifier,
                    vision_model=config.get("vision_model") or None,
                    niche_taxonomy=config.get("niche_taxonomy") or None,
                )

        def fake_run(workflow):
            rig.calls.append("run_scraping")
            if rig.run_raises is not None:
                raise rig.run_raises
            return dict(rig.run_result)

        mp.setattr(ScrapingWorkflow, "__init__", fake_init)
        mp.setattr(ScrapingWorkflow, "run", fake_run)

    # ------------------------------------------------------------------ paths

    def run_bridge(self, payload, argv: list[str] | None = None) -> int:
        """The desktop path: `scraping_bridge <config.json>`, to its exit code."""
        if argv is None:
            config_path = self.tmp_path / "scraping_config.json"
            config_path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
            argv = ["scraping_bridge", str(config_path)]
        self.monkeypatch.setattr(sys, "argv", argv)

        from bridges.instagram.scraping import scraping

        out = io.StringIO()
        self.monkeypatch.setattr(sys, "stdout", out)
        try:
            with pytest.raises(SystemExit) as exit_info:
                scraping.main()
        finally:
            self.monkeypatch.setattr(sys, "stdout", sys.__stdout__)
        for line in out.getvalue().splitlines():
            line = line.strip()
            if line:
                try:
                    self.stdout_lines.append(json.loads(line))
                except json.JSONDecodeError:
                    self.stdout_lines.append(line)
        return exit_info.value.code

    def run_cli(self, payload: dict, env: dict | None = None, workflow_id: str | None = None):
        """The standalone path: `taktik workflows run instagram.scraping.<type>`."""
        from click.testing import CliRunner

        from taktik.cli.commands import workflow_cmds

        workflow_id = workflow_id or f"instagram.scraping.{payload['type']}"
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
        self.stdout_lines.clear()
        self.configs.clear()
        self.ai_builds.clear()


__all__ = [
    "AI_KEY",
    "DEVICE_ID",
    "INSTAGRAM",
    "InstagramScrapingRig",
    "hashtag_payload",
    "post_url_payload",
    "profile_posts_payload",
    "target_payload",
    "usernames_payload",
]
