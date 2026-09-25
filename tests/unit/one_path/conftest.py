"""A recording phone for the one-path tests.

The same TikTok payload is run through the desktop bridge and through the CLI. Every seam below
is the one the production code imports at call time, so the same rig holds whichever side of the
code owns a step. Nothing here reaches adb.
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

DEVICE_ID = "emulator-5554"


class Rig:
    DEVICE_ID = DEVICE_ID

    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        self.tmp_path = tmp_path
        self.calls: list[str] = []
        self.events: list[tuple[str, dict]] = []
        self.workflows: list = []
        self.ai_installs: list[dict] = []
        self.ai_services: list[dict] = []
        self.permission_visible = True
        #: The acting account the phone shows; None when its profile cannot be read.
        self.own_username = "acting_account"
        #: What each profile-visiting run returns, in order; missing fields keep their default.
        self.profile_runs: list[dict] = []
        self._install()

    # ------------------------------------------------------------------ fakes

    def _install(self) -> None:
        rig = self
        mp = self.monkeypatch

        import time

        mp.setattr(time, "sleep", lambda *_a, **_k: None)

        from bridges.common.runtime import ipc as ipc_module

        def _send(_self, msg_type, **kwargs):
            if msg_type != "step_metric":
                rig.events.append((msg_type, kwargs))

        mp.setattr(ipc_module.IPC, "send", _send)

        from bridges.common.runtime import signal_handler

        mp.setattr(signal_handler, "_workflow", None)

        from bridges.common.device import network

        mp.setattr(network, "measure_network_baseline", lambda _device_id: None)

        from bridges.common.device import app_manager

        mp.setattr(app_manager, "force_stop_app",
                   lambda device_id, platform: rig.calls.append(f"force_stop {platform}"))

        class FakeDevice:
            def xpath(self, _selector):
                rig.calls.append("wait_app_surface")
                return SimpleNamespace(exists=True)

        self.device = FakeDevice()

        class FakeTikTokManager:
            def __init__(self, device_id=None):
                rig.calls.append(f"manager {device_id}")
                self.device_manager = SimpleNamespace(device=rig.device, device_id=device_id)

            def restart(self):
                rig.calls.append("restart")
                return True

        mp.setattr("taktik.core.social_media.tiktok.TikTokManager", FakeTikTokManager)

        class FakePermissionHandler:
            def __init__(self, device, device_id=""):
                pass

            def is_visible(self, timeout=2.0):
                rig.calls.append("permission_visible?")
                return rig.permission_visible

            def deny(self, rounds=2, per_round_wait=3.0):
                rig.calls.append("permission_deny")
                return 1

        mp.setattr("taktik.core.shared.device.permissions.PermissionHandler", FakePermissionHandler)

        class FakeNavigationActions:
            def __init__(self, device):
                pass

            def _press_back(self):
                rig.calls.append("press_back")

            def navigate_to_home(self):
                rig.calls.append("navigate_home")

        mp.setattr(
            "taktik.core.social_media.tiktok.actions.atomic.navigation.navigation_actions.NavigationActions",
            FakeNavigationActions,
        )

        def fake_detect(device, *args, **kwargs):
            rig.calls.append("detect_language")
            return "fr"

        mp.setattr("taktik.core.social_media.tiktok.ui.language.detect_and_optimize", fake_detect)

        class FakeProfileActions:
            def __init__(self, device):
                pass

            def fetch_own_profile(self):
                rig.calls.append("fetch_own_profile")
                if rig.own_username is None:
                    return None
                return SimpleNamespace(
                    username=rig.own_username, display_name="Acting", followers_count=10,
                    following_count=20, likes_count=30, bio="bio", profile_pic_base64=None,
                )

        mp.setattr(
            "taktik.core.social_media.tiktok.actions.business.actions.profile_actions.ProfileActions",
            FakeProfileActions,
        )

        from taktik.core.social_media.tiktok.actions.business.workflows._internal.models import (
            VideoWorkflowStats,
        )

        class FakeVideoWorkflow:
            """For You and Search alike: records its config, fires each callback once, returns
            one video watched, liked and followed."""

            def __init__(self, device, config):
                rig.calls.append("workflow_built")
                self.device = device
                self.config = config
                self.callbacks = {}
                rig.workflows.append(self)

            def set_on_video_callback(self, cb):
                self.callbacks["video"] = cb

            def set_on_like_callback(self, cb):
                self.callbacks["like"] = cb

            def set_on_follow_callback(self, cb):
                self.callbacks["follow"] = cb

            def set_on_stats_callback(self, cb):
                self.callbacks["stats"] = cb

            def set_on_pause_callback(self, cb):
                self.callbacks["pause"] = cb

            def run(self):
                rig.calls.append("workflow_run")
                video = {"author": "creator", "description": "#one", "like_count": "42"}
                for name, arg in (("video", video), ("like", video), ("follow", video),
                                  ("stats", {"videos_watched": 1, "videos_liked": 1}), ("pause", 8)):
                    if name in self.callbacks:
                        self.callbacks[name](arg)
                return VideoWorkflowStats(videos_watched=1, videos_liked=1, users_followed=1)

        from taktik.core.social_media.tiktok.actions.business.workflows.for_you import (
            agent_handler as for_you_handler,
            workflow as for_you_workflow,
        )
        from taktik.core.social_media.tiktok.actions.business.workflows.search import (
            agent_handler as search_handler,
            workflow as search_workflow,
        )

        mp.setattr(for_you_workflow, "ForYouWorkflow", FakeVideoWorkflow)
        mp.setattr(search_workflow, "SearchWorkflow", FakeVideoWorkflow)

        from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import (
            FollowersStats,
        )

        class ScriptedFollowersStats(FollowersStats):
            """A fixed elapsed time, so a snapshot of `to_dict()` holds still."""

            def to_dict(self):
                return {**super().to_dict(), "elapsed_seconds": 0, "elapsed_formatted": "0m 0s"}

        class FakeProfileWorkflow:
            """Followers, Target Profiles and Post URL alike: records its config and the account it
            runs as, fires each callback once, and returns the next outcome of `rig.profile_runs`
            (by default one profile visited, liked and followed)."""

            def __init__(self, device, config, device_id=None):
                rig.calls.append("workflow_built")
                self.device = device
                self.config = config
                self.callbacks = {}
                rig.workflows.append(self)

            def set_on_action_callback(self, cb):
                self.callbacks["action"] = cb

            def set_on_profile_callback(self, cb):
                self.callbacks["profile"] = cb

            def set_on_stats_callback(self, cb):
                self.callbacks["stats"] = cb

            def set_on_pause_callback(self, cb):
                self.callbacks["pause"] = cb

            def run(self, bot_username=None):
                rig.calls.append(f"workflow_run as {bot_username}")
                outcome = {"followers_seen": 1, "profiles_visited": 1, "posts_watched": 2, "likes": 1,
                           "follows": 1, "completion_reason": "max_profiles_reached"}
                if rig.profile_runs:
                    outcome.update(rig.profile_runs.pop(0))
                if outcome["profiles_visited"]:
                    if "action" in self.callbacks:
                        self.callbacks["action"]({"action": "like", "target": "fan"})
                    if "profile" in self.callbacks:
                        self.callbacks["profile"]({"username": "fan", "followers_count": 12})
                if "stats" in self.callbacks:
                    self.callbacks["stats"]({key: outcome[key] for key in
                                             ("followers_seen", "profiles_visited", "likes", "follows")})
                if "pause" in self.callbacks:
                    self.callbacks["pause"](9)
                return ScriptedFollowersStats(**outcome)

        from taktik.core.social_media.tiktok.actions.business.workflows import (
            followers as followers_package,
            post_url as post_url_package,
            target_profiles as target_profiles_package,
        )
        from taktik.core.social_media.tiktok.actions.business.workflows.followers import (
            agent_handler as followers_handler,
            workflow as followers_workflow,
        )
        from taktik.core.social_media.tiktok.actions.business.workflows.post_url import (
            workflow as post_url_workflow,
        )
        from taktik.core.social_media.tiktok.actions.business.workflows.target_profiles import (
            workflow as target_profiles_workflow,
        )

        for module, name in ((followers_workflow, "FollowersWorkflow"),
                             (followers_package, "FollowersWorkflow"),
                             (target_profiles_workflow, "TargetProfilesWorkflow"),
                             (target_profiles_package, "TargetProfilesWorkflow"),
                             (post_url_workflow, "PostUrlWorkflow"),
                             (post_url_package, "PostUrlWorkflow")):
            mp.setattr(module, name, FakeProfileWorkflow)

        # A registrar may bind its default factory when it is defined: patch that too, so the
        # rig never builds a real workflow whatever the handler does.
        for fake, registrars in (
            (FakeVideoWorkflow, (for_you_handler.register_tiktok_for_you_handlers,
                                 for_you_handler.build_tiktok_for_you_handler,
                                 search_handler.register_tiktok_search_handlers,
                                 search_handler.build_tiktok_search_handler)),
            (FakeProfileWorkflow, (followers_handler.register_tiktok_followers_handlers,
                                   followers_handler.build_tiktok_followers_handler)),
        ):
            for fn in registrars:
                if "workflow_factory" in (fn.__kwdefaults__ or {}):
                    mp.setitem(fn.__kwdefaults__, "workflow_factory", fake)

        def fake_return_home(device, *args, **kwargs):
            rig.calls.append("return_home")
            return True

        from taktik.core.social_media.tiktok.services.navigation import reset

        mp.setattr(reset, "return_to_tiktok_home", fake_return_home)
        # Bound by name at import in the old Search and Followers bridges.
        from bridges.tiktok.workflows.automation import followers as followers_bridge
        from bridges.tiktok.workflows.automation.runtime import search_callbacks

        if hasattr(search_callbacks, "return_device_to_tiktok_home"):
            mp.setattr(search_callbacks, "return_device_to_tiktok_home", fake_return_home)
        if hasattr(followers_bridge, "return_to_tiktok_home"):
            mp.setattr(followers_bridge, "return_to_tiktok_home", fake_return_home)

        from taktik.core.app.ai import factory

        def fake_build_ai_service(*, api_key, ipc=None, **kwargs):
            rig.ai_services.append({"api_key": api_key, "has_ipc": ipc is not None})
            return SimpleNamespace(name="fake-ai")

        mp.setattr(factory, "build_ai_service", fake_build_ai_service)

        from taktik.core.social_media.tiktok.workflows.core import ai_hooks

        def fake_install(ai, ai_config, *, log=None, emit_relevance=None,
                         emit_classification=None, language="en"):
            rig.ai_installs.append({"ai_config": dict(ai_config), "language": language})
            if emit_relevance:
                emit_relevance("creator", {"relevant": True, "score": 8, "reason": "fits"})
            if emit_classification:
                emit_classification("creator", {"niche_category": "sport", "niche": "running"})

        mp.setattr(ai_hooks, "install_tiktok_ai_hooks", fake_install)

    # --------------------------------------------------------------- the paths

    def run_bridge(self, payload: dict) -> int:
        """The desktop path: the TikTok bridge process, from its config file to its exit code."""
        config_path = self.tmp_path / "tiktok_config.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        self.monkeypatch.setattr(sys, "argv", ["tiktok_bridge", str(config_path)])

        from bridges.tiktok.workflows import dispatcher

        with pytest.raises(SystemExit) as exit_info:
            dispatcher.main()
        return exit_info.value.code

    def run_cli(self, payload: dict, env: dict | None = None, workflow_id: str = "tiktok.automation.for_you"):
        """The standalone path: `taktik workflows run <workflow_id>`."""
        from click.testing import CliRunner

        from taktik.cli.commands import workflow_cmds

        manager = SimpleNamespace(device=self.device)
        self.monkeypatch.setattr(workflow_cmds, "_connect", lambda device_id: (manager, DEVICE_ID))
        return CliRunner().invoke(
            workflow_cmds.workflows,
            ["run", workflow_id, "--device", DEVICE_ID, "--json", json.dumps(payload)],
            env=env,
        )

    @property
    def built_configs(self) -> list:
        return [workflow.config for workflow in self.workflows]

    @property
    def built_config(self):
        assert self.workflows, "no workflow was built"
        return self.workflows[-1].config


@pytest.fixture
def rig(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    return Rig(monkeypatch, tmp_path)


@pytest.fixture
def page_payload():
    return _page_payload


@pytest.fixture
def followers_payload():
    return _followers_payload


def _followers_payload(**overrides) -> dict:
    """What TikTokFollowers.tsx sends in followers mode, key for key, AI off, with values that
    tell the readers apart (two targets, "1 %" of likes)."""
    payload = {
        "deviceId": DEVICE_ID,
        "allowRouterDevice": False,
        "workflowType": "followers",
        "language": "fr",
        "targets": ["alpha", "@beta"],
        "maxFollowers": 3,
        "maxConsecutiveKnownUsernames": 150,
        "postsPerProfile": 2,
        "maxLikesPerSession": 40,
        "maxFollowsPerSession": 15,
        "minWatchTime": 5,
        "maxWatchTime": 15,
        "likeProbability": 1,
        "favoriteProbability": 30,
        "followProbability": 50,
        "storyLikeProbability": 50,
        "minDelay": 1,
        "maxDelay": 3,
        "pauseAfterActions": 10,
        "pauseDurationMin": 30,
        "pauseDurationMax": 60,
        "includeFriends": False,
    }
    payload.update(overrides)
    return payload


def _page_payload(**overrides) -> dict:
    """What TikTokForYou.tsx sends, key for key, with values that tell the readers apart."""
    payload = {
        "deviceId": DEVICE_ID,
        "allowRouterDevice": False,
        "workflowType": "for_you",
        "maxVideos": 5,
        "maxLikesPerSession": 40,
        "maxFollowsPerSession": 15,
        "minWatchTime": 2,
        "maxWatchTime": 8,
        "likeProbability": 1,
        "followProbability": 10,
        "favoriteProbability": 5,
        "commentProbability": 20,
        "maxCommentsPerSession": 4,
        "commentTexts": ["Nice one", "#love it"],
        "repostProbability": 10,
        "maxRepostsPerSession": 2,
        "trainingKeywords": ["running", "trail"],
        "trainingRejectOffNiche": False,
        "maxRejectionsPerSession": 7,
        "requiredHashtags": [],
        "excludedHashtags": ["ads"],
        "minLikes": None,
        "maxLikes": 5000,
        "skipAlreadyLiked": True,
        "skipAds": True,
        "followBackSuggestions": False,
        "pauseAfterActions": 10,
        "pauseDurationMin": 30,
        "pauseDurationMax": 60,
    }
    payload.update(overrides)
    return payload
