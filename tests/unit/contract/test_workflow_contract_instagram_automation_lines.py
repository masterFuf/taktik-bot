"""The lines an Instagram automation run prints are the ones its contract declares.

Three real paths, and only the phone, the network, the base's AI cache and the stdin of the desktop
replaced:
- the run: `DesktopBridge` -> `run_instagram_automation` -> the real `InstagramAutomation`, its
  `WorkflowRunner`, the split between sources, the session row and its end, for every workflow of
  the family; the screen work of each source (a list walked, a feed scrolled) answers from a script;
- the AI and the decision round trip: the real AI hooks and the real AI service, whose HTTP
  transport answers from a script, and the real decision client, whose stdin answers from a script;
- what a run does on a profile or a post: every `IPCEmitter` entry point, the media capture and the
  step telemetry, called as the workflows call them.

Every line must be declared with its fields and their types, and every declared line must come out
of one of these paths.
"""

from __future__ import annotations

import io
import json
import threading
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from ig_automation_probe import (
    bridge_file,
    capture_lines,
    line_problems,
    printed_lines,
    protect_hooks,
    use_the_bridge_ipc,
)
from taktik.core.contract.instagram_automation import INSTAGRAM_AUTOMATION, WORKFLOW_TYPES

_BUSINESS = "taktik.core.social_media.instagram.actions.business"
#: IPCEmitter entry points only the scraping workflows call: not on this path.
_SCRAPING_ONLY = {"emit_scraping_profile_visit", "emit_scraping_dq_progress"}


# ------------------------------------------------------------------------------------ the run


class _Device:
    """The phone: nothing the orchestration asks of it reaches a screen."""

    def press(self, key):
        return True

    def __getattr__(self, name):
        raise AttributeError(name)


def _device_manager():
    return SimpleNamespace(
        device=_Device(),
        stop_app=lambda package: True,
        launch_app=lambda package, stop_first=False: True,
    )


def _script_the_sources(monkeypatch) -> None:
    """The screen work of each workflow answers from a script: nothing found, nothing done."""
    import importlib

    empty_interactions = {"interacted": 0, "processed": 0, "likes": 0, "follows": 0, "stop_reason": ""}
    sync = {"new_count": 2, "updated_count": 1, "stopped_early": False, "success": True, "total_seen": 3}

    patches = {
        f"{_BUSINESS}.management.profile.extraction:ProfileExtraction.get_complete_profile_info":
            lambda self, username=None, **k: {"username": username or "acting", "followers_count": 12,
                                              "following_count": 3, "posts_count": 4},
        f"{_BUSINESS}.workflows.followers.workflow:FollowerBusiness.interact_with_followers_direct":
            lambda self, *a, **k: dict(empty_interactions),
        f"{_BUSINESS}.workflows.followers.workflow:FollowerBusiness.interact_with_profile_list":
            lambda self, *a, **k: dict(empty_interactions),
        f"{_BUSINESS}.workflows.hashtag.workflow:HashtagBusiness.interact_with_hashtag_likers":
            lambda self, *a, **k: {"users_interacted": 0, "stop_reason": ""},
        f"{_BUSINESS}.workflows.post_url.workflow:PostUrlBusiness.interact_with_post_likers":
            lambda self, *a, **k: {"users_interacted": 0, "stop_reason": ""},
        f"{_BUSINESS}.workflows.feed.workflow:FeedBusiness.interact_with_feed":
            lambda self, *a, **k: {"posts_engaged": 0},
        f"{_BUSINESS}.workflows.unfollow.workflow:UnfollowBusiness.run_unfollow_workflow":
            lambda self, *a, **k: {"unfollows_made": 0, "success": True},
        f"{_BUSINESS}.workflows.unfollow.workflow:UnfollowBusiness.sync_following_list":
            lambda self, *a, **k: dict(sync),
        f"{_BUSINESS}.workflows.unfollow.workflow:UnfollowBusiness.sync_followers_list":
            lambda self, *a, **k: dict(sync),
        f"{_BUSINESS}.workflows.unfollow.workflow:UnfollowBusiness.scrape_non_followers_category":
            lambda self, *a, **k: {"non_followers_count": 1, "mutuals_count": 2, "success": True},
    }
    for dotted, replacement in patches.items():
        module, attribute = dotted.split(":")
        owner, name = attribute.split(".")
        monkeypatch.setattr(getattr(importlib.import_module(module), owner), name, replacement)


@pytest.fixture
def automation_run(monkeypatch, tmp_path):
    """`DesktopBridge` down to the real automation, with the phone and the network replaced."""
    import sqlite3

    import bridges.common.network as network
    import taktik.core.database as database
    import bridges.instagram.automation.bridge as bridge
    import taktik.core.social_media.instagram.workflows.core.runtime_setup as runtime_setup
    import taktik.core.social_media.instagram.workflows.support.workflow_helpers as helpers
    from bridges.instagram.automation.session import InstagramDesktopRuntime

    sent = capture_lines(monkeypatch)
    ips = iter(["198.51.100.1", "198.51.100.2"] * 20)
    monkeypatch.setattr(network, "read_public_ip", lambda device_id: next(ips))
    monkeypatch.setitem(network._STRATEGIES, "data", lambda device_id: True)
    monkeypatch.setattr(network, "measure_network_baseline",
                        lambda device_id: {"rtt_ms": 41, "packet_loss_pct": 0, "received": 3})

    def connect(runtime):
        runtime.device_manager = _device_manager()
        return True

    # A real, empty base for the session row and the account; the service is put back afterwards.
    database_file = tmp_path / "automation.db"
    sqlite3.connect(database_file).close()
    monkeypatch.setenv("TAKTIK_DB_PATH", str(database_file))
    monkeypatch.setattr(database, "db_service", None)
    monkeypatch.setattr(InstagramDesktopRuntime, "connect_device", connect)
    monkeypatch.setattr(InstagramDesktopRuntime, "launch_instagram", lambda runtime: True)
    monkeypatch.setattr(InstagramDesktopRuntime, "stop_app", lambda runtime: None)
    monkeypatch.setattr(bridge, "register_desktop_shutdown_handlers", lambda handler, ipc: None)
    # The selector catalogs are matched to the phone's app and screen, and the active package is global.
    monkeypatch.setattr(runtime_setup, "prepare_instagram_selectors", lambda **kwargs: None)
    monkeypatch.setattr(runtime_setup, "set_active_package", lambda package: None)
    monkeypatch.setattr(helpers.WorkflowHelpers, "_handle_post_restart_popups", lambda self: None)
    monkeypatch.setattr(helpers, "capture_screen_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(helpers, "redetect_if_unknown", lambda device: None)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    monkeypatch.setattr(bridge, "DesktopProfileDecisionClient",
                        lambda **kwargs: _decision_client(kwargs["ipc"], kwargs.get("log")))
    _script_the_sources(monkeypatch)
    protect_hooks(monkeypatch)
    return bridge.DesktopBridge, sent


def _decision_client(ipc, log=None):
    from bridges.instagram.automation.decision_client import DesktopProfileDecisionClient

    return DesktopProfileDecisionClient(ipc=ipc, input_stream=_Desktop(), timeout_seconds=0.2, log=log)


@pytest.mark.parametrize("workflow_type", WORKFLOW_TYPES)
def test_an_automation_run_prints_declared_lines(automation_run, capsys, workflow_type):
    DesktopBridge, sent = automation_run

    assert DesktopBridge(bridge_file(workflow_type)).run() == 0
    lines = sent + printed_lines(capsys.readouterr().out)

    assert not line_problems(lines), line_problems(lines)
    types = {line["type"] for line in lines}
    assert {"session_config", "session_start", "active_account", "stats", "network_reset_complete",
            "step_metric"} <= types
    if workflow_type in ("target_followers", "target_following", "hashtags", "post_url"):
        assert "source_progress" in types
    if workflow_type.startswith("sync_"):
        # A sync ends the run itself (`session_finalized`), without the stop line.
        assert "sync_complete" in types and "session_stop" not in types
    else:
        assert "session_stop" in types


# ------------------------------------------------------------------------------------ AI, decision


class _Desktop(io.RawIOBase):
    """The desktop's stdin: answers each decision request with an empty plan."""

    def __init__(self):
        super().__init__()
        self._answers: List[bytes] = []
        self._ready = threading.Event()
        self._closed = threading.Event()

    def answer(self, request_id: str) -> None:
        plan = {"likes": 1, "follow": False, "comment": False, "watchStory": False, "likeStory": False,
                "maxComments": 0, "maxStorySlides": 0, "maxStoryLikes": 0}
        self._answers.append((json.dumps({"type": "agent_profile_decision_response", "requestId": request_id,
                                          "ok": True, "plan": plan}) + "\n").encode("utf-8"))
        self._ready.set()

    def readline(self, *args):
        while not self._closed.is_set():
            if self._answers:
                return self._answers.pop(0)
            self._ready.wait(0.05)
            self._ready.clear()
        return b""

    def cancel_read(self):
        self._closed.set()
        self._ready.set()


#: What the model answers, whatever it is asked: a verdict, a qualification, a description, a comment.
_MODEL_ANSWER = json.dumps({
    "relevant": True, "score": 0.8, "relevance_tier": "direct", "reason": "fits the niche",
    "evidence": "the bio", "like": True, "follow": False,
    "niche": "yoga", "niche_category": "fitness", "gender": "female", "age_group": "25-34",
    "summary": "a yoga teacher",
    "engagement": {"relevant": True, "score": 0.8, "relevance_tier": "direct", "reason": "fits",
                   "like": True, "follow": False, "comment": False},
    "reasoning": "a warm reaction", "comment": "Lovely flow", "should_comment": True,
    "should_reply": True, "reply": "Thank you",
})


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _openrouter(answers: List[str]):
    """The HTTP transport of the AI service: each call takes the next answer; `fail` is a 500."""
    import urllib.error

    def urlopen(request, timeout=None):
        answer = answers.pop(0) if answers else _MODEL_ANSWER
        if answer == "fail":
            raise urllib.error.HTTPError(request.full_url, 500, "down", {}, io.BytesIO(b"down"))
        body = {"model": "probe-model", "provider": "probe",
                "choices": [{"message": {"content": answer}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.0001}}
        return _Response(json.dumps(body).encode("utf-8"))

    return urlopen


def _ai_and_decision_lines(monkeypatch, tmp_path) -> List[Dict[str, Any]]:
    """The AI hooks and the AI service of a run in decision mode, the desktop answering each plan."""
    from PIL import Image

    import bridges.instagram.common.ipc as instagram_ipc
    import taktik.core.social_media.instagram.workflows.core.ai_hooks as ai_hooks
    from bridges.common.ipc import IPC
    from bridges.instagram.automation.decision_client import DesktopProfileDecisionClient
    from bridges.instagram.common.ai import create_instagram_ai_service
    from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
        InteractionEngineMixin,
    )
    from taktik.core.social_media.instagram.workflows.core.config_builder import build_instagram_automation_config
    from taktik.core.social_media.instagram.workflows.management.session import SessionManager

    desktop = _Desktop()
    sent: List[Dict[str, Any]] = []

    def send(self, msg_type, **kwargs):
        sent.append({"type": msg_type, **kwargs})
        if msg_type == "agent_profile_decision_request":
            desktop.answer(kwargs["requestId"])

    monkeypatch.setattr(IPC, "send", send)
    use_the_bridge_ipc(monkeypatch)
    protect_hooks(monkeypatch)
    answers: List[str] = []
    monkeypatch.setattr("urllib.request.urlopen", _openrouter(answers))
    # The base knows the profile already: the hook judges it on text, without a screenshot.
    monkeypatch.setattr(ai_hooks, "_load_cached_qualification",
                        lambda username: {"niche": "yoga", "niche_category": "fitness", "biography": "teacher"})
    monkeypatch.setattr(InteractionEngineMixin, "_perform_interactions_on_profile",
                        lambda self, username, config, profile_data=None: {"likes": 0})

    payload = bridge_file("target_followers")
    ai_config = payload["ai"]
    enabled, ai = create_instagram_ai_service(ai_config=ai_config, ipc=instagram_ipc._ipc, log=lambda *a: None)
    assert enabled
    client = DesktopProfileDecisionClient(ipc=instagram_ipc._ipc, input_stream=desktop, timeout_seconds=2)
    try:
        ai_hooks.install_instagram_ai_hooks(ai=ai, ai_config=ai_config, device=_Device(), language="en",
                                            log=lambda *a: None, decision_provider=client.request_plan)
        workflow_config = build_instagram_automation_config(payload)
        engine = SimpleNamespace(session_manager=SessionManager(workflow_config))
        InteractionEngineMixin._perform_interactions_on_profile(
            engine, "a_profile", workflow_config["actions"][0],
            {"followers_count": 120, "following_count": 80, "posts_count": 30},
        )
    finally:
        client.close()

    screenshot = tmp_path / "post.png"
    Image.new("RGB", (8, 8)).save(screenshot)
    ai.classify_profile_niche(username="a_profile", screenshot_path=str(screenshot), include_engagement=True)
    ai.analyze_post(screenshot_path=str(screenshot), username="a_profile")
    ai.generate_smart_comment(post_description="A yoga pose", username="a_profile")
    answers.append("fail")
    ai.analyze_post(screenshot_path=str(screenshot), username="a_profile")
    return sent


def test_the_ai_and_the_decision_round_trip_print_declared_lines(monkeypatch, tmp_path):
    lines = _ai_and_decision_lines(monkeypatch, tmp_path)

    assert not line_problems(lines), line_problems(lines)
    types = {line["type"] for line in lines}
    assert {"agent_profile_decision_request", "instagram_action", "ai_profile_start", "ai_profile_done",
            "ai_screenshot_start", "ai_screenshot_done", "ai_comment_start", "ai_comment_done", "ai_error",
            "ai_spend"} <= types


# ------------------------------------------------------------------------------------ on a profile


def _emitter_lines(monkeypatch, capsys) -> List[Dict[str, Any]]:
    """What a run does on a profile or a post, through the entry points the workflows call."""
    import bridges.instagram.common.ipc as instagram_ipc
    from bridges.instagram.automation.media_capture import InstagramMediaCaptureRuntime
    from bridges.instagram.common.ipc_stats import setup_stats_callback
    from taktik.core.shared.telemetry import emit_step
    from taktik.core.social_media.instagram.actions.business.workflows.followers.workflow import FollowerBusiness
    from taktik.core.social_media.instagram.actions.core.base_business.interaction_engine import (
        InteractionEngineMixin,
    )
    from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter
    from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager
    from taktik.core.social_media.instagram.media.capture.media_capture import MediaCaptureService

    sent = capture_lines(monkeypatch)
    use_the_bridge_ipc(monkeypatch)
    profile = {"username": "a_profile", "full_name": "A Profile", "followers_count": 120,
               "following_count": 80, "posts_count": 30, "is_private": False, "is_verified": False,
               "biography": "yoga"}

    entry_points = {name for name in dir(IPCEmitter) if name.startswith("emit_")}
    engine = SimpleNamespace()
    InteractionEngineMixin._emit_follow_event(engine, "a_profile", profile)
    InteractionEngineMixin._emit_like_event(engine, "a_profile", 2, profile)
    InteractionEngineMixin._emit_story_event(engine, "a_profile", 3, 1, profile)
    InteractionEngineMixin._emit_follow_event(engine, "a_suggestion")
    IPCEmitter.emit_profile_visit("a_profile")
    IPCEmitter.emit_profile_captured(username="a_profile", profile_data=profile,
                                     profile_pic_base64="data:image/jpeg;base64,AAAA")
    IPCEmitter.emit_profile_captured(username="a_private", profile_data={**profile, "full_name": None})
    IPCEmitter.emit_profile_skipped("a_profile", "already_processed", detail="3")
    IPCEmitter.emit_profile_skipped("a_profile")
    IPCEmitter.emit_profile_classification("a_profile", {"niche": "yoga"}, result="[fitness] yoga",
                                           model=None, provider="openrouter", cost_usd=0.0001)
    IPCEmitter.emit_action("like", "a_profile", {"count": 2})
    IPCEmitter.emit_action("greeting", "")
    IPCEmitter.emit_feed_decision("an_author", "like_comment", reason="fits", comment="Lovely", visit_profile=True)
    IPCEmitter.emit_feed_decision(None, "skip")
    IPCEmitter.emit_unfollow("a_profile", success=True)
    IPCEmitter.emit_unfollow("a_profile", success=False)
    IPCEmitter.emit_unfollow_plan(mode="non-followers", candidates=12, refusals={"whitelist": 2})
    IPCEmitter.emit_stats(unfollows=3)
    IPCEmitter.emit_current_post("an_author", likes_count=120, comments_count=4, caption="x" * 150, hashtag="yoga")
    IPCEmitter.emit_current_post("an_author")
    IPCEmitter.emit_post_skipped(author="an_author", reason="already_processed", hashtag="yoga")
    IPCEmitter.emit_post_skipped(author="an_author")
    uncalled = entry_points - _SCRAPING_ONLY - {
        "emit_follow", "emit_like", "emit_story", "emit_profile_visit", "emit_profile_captured",
        "emit_profile_skipped", "emit_profile_classification", "emit_action", "emit_feed_decision",
        "emit_unfollow", "emit_unfollow_plan", "emit_stats", "emit_current_post", "emit_post_skipped",
    }
    assert not uncalled, f"IPCEmitter entry points this test does not hold: {sorted(uncalled)}"

    # The live counters: every stats manager reports each change.
    monkeypatch.setattr(BaseStatsManager, "__init__", BaseStatsManager.__init__)
    setup_stats_callback()
    BaseStatsManager("target_followers").increment("likes")

    # The step telemetry, and the target account opened by a followers run.
    emit_step("tap", action="follow_button", target="a_profile", x=10, y=20)
    nav = SimpleNamespace(navigate_to_profile=lambda *a, **k: True, open_followers_list=lambda: True,
                          open_following_list=lambda: True)
    follower = SimpleNamespace(
        logger=SimpleNamespace(info=lambda *a: None, warning=lambda *a: None, error=lambda *a: None),
        nav_actions=nav, _human_like_delay=lambda kind: None,
        profile_business=SimpleNamespace(get_complete_profile_info=lambda *a, **k: {
            "followers_count": 5400, "following_count": 300, "media_count": 80}),
    )
    FollowerBusiness._setup_direct_workflow(follower, "a_target", {}, {"interaction_type": "followers"}, 0, False)

    # The follow-graph sync, as both lists print it while they are read.
    from taktik.core.social_media.instagram.actions.business.workflows.unfollow.mixins.sync_events import (
        emit_sync_progress,
        emit_sync_user_discovered,
    )

    emit_sync_user_discovered("following", "a_profile", "A Profile", True)
    emit_sync_user_discovered("followers", "a_fan", "", False)
    emit_sync_progress("followers", {"new_count": 2, "updated_count": 1, "total_seen": 3, "expected": 1219})
    emit_sync_progress("following", {"new_count": 0, "updated_count": 0, "total_seen": 0, "expected": None})

    # The media capture: the profiles and posts the app loads, read from its traffic.
    runtime = InstagramMediaCaptureRuntime(device_id="emulator-5554", enabled=True)
    service = MediaCaptureService(device_id="emulator-5554",
                                  desktop_bridge_callback=lambda kind, data: instagram_ipc.send_message(kind, **data))
    service.on_profile_captured = runtime._on_profile
    service.on_media_captured = runtime._on_media
    service._handle_profile_data({"username": "a_profile", "full_name": "A Profile", "follower_count": 120,
                                  "profile_pic_url": "https://cdn.example/pic.jpg"})
    service._handle_media_data({"media_id": "1", "media_type": "photo", "image_url": "https://cdn.example/1.jpg",
                                "like_count": 12, "comment_count": 1, "caption": "yoga", "username": "a_profile"})
    return sent + printed_lines(capsys.readouterr().out)


def test_what_a_run_does_on_a_profile_prints_declared_lines(monkeypatch, capsys):
    lines = _emitter_lines(monkeypatch, capsys)

    assert not line_problems(lines), line_problems(lines)


# ------------------------------------------------------------------------------------ coverage


def test_every_declared_line_comes_out_of_a_real_path(automation_run, capsys, monkeypatch, tmp_path):
    DesktopBridge, sent = automation_run
    lines: List[Dict[str, Any]] = []
    for workflow_type in WORKFLOW_TYPES:
        sent.clear()
        assert DesktopBridge(bridge_file(workflow_type)).run() == 0
        lines += sent + printed_lines(capsys.readouterr().out)
    lines += _emitter_lines(monkeypatch, capsys)
    lines += _ai_and_decision_lines(monkeypatch, tmp_path)

    printed = {line["type"] for line in lines}
    # A crash is its own path: the bridge's error line (`send_instagram_workflow_error`).
    from bridges.instagram.automation.events import send_instagram_workflow_error
    from bridges.common.ipc import IPC

    crash: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: crash.append({"type": msg_type, **kwargs}))
    send_instagram_workflow_error(TimeoutError("the list did not load"))
    assert not line_problems(crash), line_problems(crash)
    printed |= {line["type"] for line in crash}

    declared = {event.type for event in INSTAGRAM_AUTOMATION.events}
    assert declared - printed == set(), f"declared, printed by no real path: {sorted(declared - printed)}"
