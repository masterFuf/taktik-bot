"""The Threads, task and publication bridges read the file the contract describes and print the
lines it declares.

Same rules as `test_workflow_contract_bridges.py`, on the Threads dispatcher, the Instagram task
bridge and the YouTube and TikTok publication bridges: the whole bridge runs on the app's file;
only the phone (connection, app restart, the engine's screen work) is replaced.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict

import pytest

from contract_probe import DEVICE, Recording, expected, merge, nest, payload_for, probe, skeleton, value_of
from taktik.core.contract.publish import INSTAGRAM_PUBLISH, TIKTOK_UPLOAD, YOUTUBE_UPLOAD
from taktik.core.contract import WORKFLOW_CONTRACTS
from taktik.core.contract.schema import OneOf, Shape, WorkflowContract, has_default, nested_fields
from taktik.core.contract.tasks import INSTAGRAM_STORY_RELAY
from taktik.core.contract.threads import THREADS_FEED, THREADS_SEARCH
from test_workflow_contract_bridges import assert_reads, check_lines, lines  # noqa: F401 (fixture)

_DEVICE_KEYS = ("deviceId", "device_id")


def app_file(contract: WorkflowContract, **overrides: Any) -> Dict[str, Any]:
    """The file the app writes: every app setting (a nested one key by key), the bridge fields."""
    settings: Dict[str, Any] = {}
    for item in contract.settings:
        if not item.app:
            continue
        if item.key in _DEVICE_KEYS:
            settings[item.key] = DEVICE
        elif item.key in overrides:
            settings[item.key] = overrides.pop(item.key)
        elif isinstance(item.type, Shape) and item.via is None:
            settings[item.key] = skeleton((item,))[item.key]
        elif has_default(item) and not isinstance(item.default, tuple):
            settings[item.key] = item.default
        else:
            settings[item.key] = probe(item)
    root: Dict[str, Any] = {}
    for item in contract.bridge_fields:
        if item.key in overrides:
            value = overrides.pop(item.key)
        elif item.key in _DEVICE_KEYS:
            value = DEVICE
        elif isinstance(item.type, OneOf):
            value = item.type.values[0]
        else:
            value = probe(item)
        target = settings if item.key in contract.beside_settings or not contract.nest else root
        target[item.key] = value
    assert not overrides, f"not in the declaration: {sorted(overrides)}"
    if contract.nest:
        return {**root, contract.nest: settings}
    return {**root, **settings}


# ------------------------------------------------------------------ aliases of a nested setting

GROUP_ALIASES = [
    pytest.param(contract, path, leaf, alias, id=f"{contract.workflow_id}:{'.'.join(path)}<-{alias}")
    for contract in WORKFLOW_CONTRACTS
    for group_path, group, when, via in nested_fields(contract.settings)
    if len(group_path) == 1 and isinstance(group.type, Shape) and via is None and not when
    for alias in group.aliases
    for path, leaf, _, _ in nested_fields(group.type.fields, group_path)
    if not isinstance(leaf.type, Shape)
]


@pytest.mark.parametrize("contract, path, leaf, alias", GROUP_ALIASES)
def test_a_nested_setting_is_read_under_its_aliases_after_its_wire_name(contract, path, leaf, alias):
    """`actions` for `actionProbabilities`: the keys below keep their meaning, the wire name first."""
    value, other = probe(leaf, 0), probe(leaf, 1)
    under_alias = nest((alias, *path[1:]), value)

    assert value_of(contract, leaf, payload_for(contract, under_alias)) == expected(leaf, value)
    both = merge(nest(path, value), nest((alias, *path[1:]), other))
    assert value_of(contract, leaf, payload_for(contract, both)) == expected(leaf, value)


def printed(lines_):
    return {line["type"] for line in lines_}


# ------------------------------------------------------------------------------------- Threads


def _threads_engine(fail: bool):
    def engine(config, *, on_log, on_stats, on_profile_visit, on_action, startup):
        from taktik.core.social_media.threads.workflows.search_and_interact import InteractStats

        if fail:
            raise RuntimeError("the search field did not open")
        stats = InteractStats(profiles_visited=1, follows=1, likes=1)
        on_profile_visit({"username": "alice", "followers": 1200, "is_private": False})
        on_action("follow", "alice", {"username": "alice", "followers": 1200})
        on_action("like", "alice", {"username": "alice", "post_index": 0})
        on_stats(stats)
        return stats

    return engine


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
@pytest.mark.parametrize("contract", [THREADS_SEARCH, THREADS_FEED], ids=["search", "feed"])
def test_the_threads_bridge_follows_its_contract(monkeypatch, lines, contract, fail):
    import taktik.core.shared.device.app_manager as app_manager
    import bridges.threads.automation.threads_bridge as dispatcher
    from taktik.core.social_media.threads.workflows import agent_handler

    monkeypatch.setattr(app_manager, "force_stop_app", lambda *a, **k: None)
    launcher, slot = ((agent_handler.run_threads_search, "search_runner") if contract is THREADS_SEARCH
                      else (agent_handler.run_threads_feed, "feed_runner"))
    monkeypatch.setitem(launcher.__kwdefaults__, slot, _threads_engine(fail))
    data = app_file(contract)
    log: set = set()

    with pytest.raises(SystemExit) as exited:
        dispatcher.ThreadsDispatch(Recording(data, log)).run()

    assert exited.value.code == (1 if fail else 0)
    assert_reads(contract, data, log)
    check_lines(contract, lines)
    expected = {"log", "status", "error"} if fail else {e.type for e in contract.events} - {"error"}
    assert printed(lines) == expected


# ------------------------------------------------------------------------ Instagram task


def _relay(fail: bool):
    def relay(*, device, source_username, account_id, max_stories):
        if fail:
            raise RuntimeError("the story viewer did not open")
        return {
            "success": True, "source_username": source_username, "considered": 2, "relayed": 1,
            "already_handled": 0, "unavailable": 1, "failed": 0, "skipped_ads": 0, "reason": None,
            "outcomes": [
                {"index": 1, "signature": "src|5 h|1", "status": "relayed", "reason": None},
                {"index": 2, "signature": "src|5 h|2", "status": "unavailable", "reason": "not_mentioned"},
            ],
        }

    return relay


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_task_bridge_follows_its_contract(monkeypatch, lines, fail):
    import bridges.instagram.tasks.bridge as bridge
    from taktik.core.social_media.instagram.workflows.tasks import agent_handler

    restarted = []
    monkeypatch.setattr(bridge.TaskBridge, "_prepare_runtime_session", lambda self: object())
    monkeypatch.setattr(bridge.TaskBridge, "_restart_instagram",
                        lambda self, device, package_name: restarted.append(package_name) or device)
    monkeypatch.setitem(agent_handler.run_instagram_story_relay.__kwdefaults__, "relay", _relay(fail))
    data = app_file(INSTAGRAM_STORY_RELAY, packageName="com.instagram.android")
    log: set = set()

    assert bridge.TaskBridge(Recording(data, log)).run() == (1 if fail else 0)

    # The launcher read the clone of the task and the bridge restarted that Instagram.
    assert restarted == ["com.instagram.android"]

    assert_reads(INSTAGRAM_STORY_RELAY, data, log)
    check_lines(INSTAGRAM_STORY_RELAY, lines)
    assert printed(lines) == ({"status", "error", "log"} if fail else {"status", "task_result"})


# ------------------------------------------------------------------------------ YouTube


def _youtube_workflow(fail: bool):
    class Upload:
        def __init__(self, device, device_id):
            pass

        def execute(self, **params):
            if fail:
                raise RuntimeError("the gallery did not open")
            return {"success": True, "message": "uploaded"}

    return Upload


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_youtube_upload_bridge_follows_its_contract(monkeypatch, lines, tmp_path, fail):
    import bridges.youtube.publish.youtube_upload_bridge as bridge
    from taktik.core.social_media.youtube.workflows.publish import agent_handler

    monkeypatch.setattr(bridge, "prepare_youtube_session",
                        lambda device_id, status, error: SimpleNamespace(device=object(), connection=None))
    monkeypatch.setattr(bridge, "cleanup_youtube_app", lambda device_id: None)
    monkeypatch.setitem(agent_handler.run_youtube_upload.__kwdefaults__, "workflow_factory",
                        _youtube_workflow(fail))
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    # A Short's title longer than YouTube takes: the launcher says it cut it.
    data = app_file(YOUTUBE_UPLOAD, localPath=str(video), title="x" * 120)
    log: set = set()

    assert bridge.YouTubeUploadBridge(Recording(data, log)).run() == (1 if fail else 0)

    assert_reads(YOUTUBE_UPLOAD, data, log)
    check_lines(YOUTUBE_UPLOAD, lines)
    expected = {"status", "log", "error"} if fail else {"status", "log", "upload_result"}
    assert printed(lines) == expected


def test_the_youtube_upload_bridge_refuses_a_missing_file_before_the_phone(monkeypatch, lines, tmp_path):
    import bridges.youtube.publish.youtube_upload_bridge as bridge

    def no_phone(*args, **kwargs):
        raise AssertionError("the phone was touched")

    monkeypatch.setattr(bridge, "prepare_youtube_session", no_phone)
    data = app_file(YOUTUBE_UPLOAD, localPath=str(tmp_path / "missing.mp4"))

    assert bridge.YouTubeUploadBridge(data).run() == 1
    check_lines(YOUTUBE_UPLOAD, lines)
    assert [line["error"] for line in lines] == [f"File not found: {tmp_path / 'missing.mp4'}"]


# ------------------------------------------------------------------------------- TikTok


def _tiktok_workflow(fail: bool):
    class Upload:
        def __init__(self, device, device_id, notifier=None, step_hook=None):
            self.notifier = notifier

        def execute(self, local_path, caption, hashtags, package_name):
            if fail:
                raise RuntimeError("the gallery did not open")
            self.notifier.log("info", "Pushing file to device")
            self.notifier.status("publishing", "Publishing...")
            return {"success": True, "message": "Post published successfully!", "error_type": None}

    return Upload


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_tiktok_publish_bridge_follows_its_contract(monkeypatch, lines, tmp_path, fail):
    import bridges.tiktok.publish.bridge as bridge
    from taktik.core.social_media.tiktok.workflows.publish import agent_handler

    class Connection:
        def __init__(self, device_id):
            self.device = object()

        def connect(self):
            return True

    monkeypatch.setattr(bridge, "ConnectionService", Connection)
    monkeypatch.setattr(bridge.TikTokPublishBridge, "_capture_phase", lambda self, device, phase: None)
    monkeypatch.setitem(agent_handler.run_tiktok_publish.__kwdefaults__, "workflow_factory", _tiktok_workflow(fail))
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    data = app_file(TIKTOK_UPLOAD, localPath=str(video), packageName="com.zhiliaoapp.musically")
    log: set = set()

    assert bridge.TikTokPublishBridge(Recording(data, log)).run() == (1 if fail else 0)

    assert_reads(TIKTOK_UPLOAD, data, log)
    check_lines(TIKTOK_UPLOAD, lines)
    expected = {"status", "error", "log"} if fail else {"status", "log", "upload_result"}
    assert printed(lines) == expected


# ------------------------------------------------------------------------------- Instagram


def _instagram_workflow(fail: bool):
    class Post:
        def __init__(self, device, device_id, *, log=None, status=None, package_name=None,
                     post_type="post", story_via_feed=False, account_username=None):
            self.log, self.status = log, status

        def execute(self, caption="", hashtags=None, media_paths=None, stop_before_share=False):
            self.log("info", "Pushing media")
            self.status("publishing", "Publishing...")
            if fail:
                return {"success": False, "message": "Could not select media from gallery",
                        "error_type": "gallery_item_not_found", "confirmed": False}
            return {"success": True, "message": "post published", "error_type": None, "confirmed": True}

    return Post


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_instagram_publish_bridge_follows_its_contract(monkeypatch, lines, fail):
    import bridges.instagram.publish.bridge as bridge
    from taktik.core.social_media.instagram.workflows.publish import agent_handler

    class Connection:
        def __init__(self, device_id):
            self.device = object()

        def connect(self):
            return True

        def disconnect(self):
            pass

    monkeypatch.setattr(bridge, "ConnectionService", Connection)
    monkeypatch.setitem(agent_handler.run_instagram_publish.__kwdefaults__, "workflow_factory", _instagram_workflow(fail))
    data = app_file(INSTAGRAM_PUBLISH, packageName="com.instagram.android")
    log: set = set()

    assert bridge.InstagramPublishBridge(Recording(data, log)).run() == (1 if fail else 0)

    assert_reads(INSTAGRAM_PUBLISH, data, log)
    check_lines(INSTAGRAM_PUBLISH, lines)
    expected_lines = {"status", "log", "error"} if fail else {"status", "log"}
    assert printed(lines) == expected_lines


def test_the_instagram_publish_bridge_refuses_nothing_to_publish_before_the_phone(monkeypatch, lines):
    import bridges.instagram.publish.bridge as bridge

    def no_phone(*args, **kwargs):
        raise AssertionError("the phone was touched")

    monkeypatch.setattr(bridge, "ConnectionService", no_phone)
    data = app_file(INSTAGRAM_PUBLISH, mediaPaths=[])

    assert bridge.InstagramPublishBridge(data).run() == 1
    check_lines(INSTAGRAM_PUBLISH, lines)
    assert [line["error"] for line in lines] == ["At least one media path is required (mediaPaths/localPath)"]
