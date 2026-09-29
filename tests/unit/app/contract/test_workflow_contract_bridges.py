"""Each declared bridge reads the file the contract describes and prints the lines it declares.

The whole bridge runs, from its config file to its stdout, on the app's file for the workflow; only
what touches the phone, the network or the base is replaced (the workflow's screen work, the
start of TikTok, the IP rotation, the rows). What is held to the declaration:
- every key of the file is read, and every key read is declared (bridge and launcher together);
- every line printed is a declared `type` with its declared fields and types;
- every declared `type` is printed by a real path of the bridge.
"""

from __future__ import annotations

import json
import random
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from contract_probe import DEVICE, Recording, probe
from taktik.core.contract.schema import Field, ListOf, MapOf, OneOf, Shape, WorkflowContract, has_default
from taktik.core.contract.tiktok import TIKTOK_DM_OUTREACH, TIKTOK_SCRAPING, TIKTOK_UNFOLLOW
from taktik.core.contract.tiktok_automation import TIKTOK_FOR_YOU, TIKTOK_SEARCH

_WORKFLOWS = "taktik.core.social_media.tiktok.actions.business.workflows"


# ------------------------------------------------------------------------------------ helpers

#: Lines of the session start and of the AI provider, which these runs replace: each is proved on
#: its own real path (`test_workflow_contract_lines.py`).
_ELSEWHERE = {"bot_profile", "ai_profile_done", "ai_relevance"}


def bridge_file(contract: WorkflowContract, **overrides: Any) -> Dict[str, Any]:
    """The file the app writes: every app setting under its wire key, the bridge fields."""
    settings = {}
    for item in contract.settings:
        if item.key in ("device_id", "deviceId"):
            settings[item.key] = overrides.pop(item.key, DEVICE)
            continue
        if not item.app or item.by != "operator":
            continue
        plain = has_default(item) and not isinstance(item.default, tuple)
        settings[item.key] = overrides.pop(item.key, item.default if plain else probe(item))
    root: Dict[str, Any] = {}
    for item in contract.bridge_fields:
        if item.key in ("device_id", "deviceId"):
            value = DEVICE
        elif isinstance(item.type, OneOf):
            value = item.type.values[0]
        else:
            value = {"enabled": True, "method": "data"}
        target = settings if item.key in contract.beside_settings or not contract.nest else root
        target[item.key] = overrides.pop(item.key, value)
    assert not overrides, f"not in the declaration: {sorted(overrides)}"
    if contract.nest:
        root[contract.nest] = settings
        return root
    return {**root, **settings}


def declared_paths(contract: WorkflowContract) -> set:
    nest = (contract.nest,) if contract.nest else ()
    paths = set()

    def add(item: Field, prefix):
        for name in item.names:
            paths.add((*prefix, name))
            if isinstance(item.type, Shape):
                for sub in item.type.fields:
                    add(sub, (*prefix, name))

    for item in contract.settings:
        add(item, nest)
    for item in contract.bridge_fields:
        add(item, nest if item.key in contract.beside_settings else ())
    if contract.nest:
        paths.add(nest)
    return paths


def file_paths(data: Dict[str, Any], prefix=()) -> set:
    out = set()
    for key, value in data.items():
        out.add((*prefix, key))
        if isinstance(value, dict):
            out |= file_paths(value, (*prefix, key))
    return out


def conforms(item: Field, value: Any) -> bool:
    if value is None:
        return item.nullable
    return _is(item.type, value)


def _is(spec: Any, value: Any) -> bool:
    if spec == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if spec == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if spec == "bool":
        return isinstance(value, bool)
    if spec == "string":
        return isinstance(value, str)
    if spec == "json":
        return True
    if isinstance(spec, OneOf):
        return spec.allows(value)
    if isinstance(spec, ListOf):
        return isinstance(value, list) and all(_is(spec.item, v) for v in value)
    if isinstance(spec, MapOf):
        return isinstance(value, dict) and all(_is(spec.value, v) for v in value.values())
    if isinstance(spec, Shape):
        return isinstance(value, dict) and not problems_of(spec.fields, value)
    raise AssertionError(f"unknown spec {spec!r}")


def problems_of(fields, data: Dict[str, Any]) -> List[str]:
    declared = {item.key: item for item in fields}
    problems = [f"undeclared field {key}" for key in data if key not in declared and key != "type"]
    for key, item in declared.items():
        if key not in data:
            if not item.optional:
                problems.append(f"missing field {key}")
        elif not conforms(item, data[key]):
            problems.append(f"{key}={data[key]!r} is not {item.type!r}")
    return problems


def check_lines(contract: WorkflowContract, lines: List[Dict[str, Any]]) -> None:
    declared = {event.type: event for event in contract.events}
    for line in lines:
        json.dumps(line)
        assert line["type"] in declared, f"undeclared line {line}"
        assert not problems_of(declared[line["type"]].fields, line), (line, problems_of(declared[line["type"]].fields, line))


@pytest.fixture
def lines(monkeypatch):
    """Every line the bridge prints, through the real IPC helpers."""
    from bridges.common.runtime.ipc import IPC

    printed: List[Dict[str, Any]] = []
    monkeypatch.setattr(IPC, "send", lambda self, msg_type, **kwargs: printed.append({"type": msg_type, **kwargs}))
    return printed


@pytest.fixture
def no_ip_rotation(monkeypatch):
    import bridges.common.device.network as network

    monkeypatch.setattr(network, "_emit_network_baseline", lambda device_id: None)
    monkeypatch.setattr(
        network, "perform_network_reset",
        lambda *a, **k: SimpleNamespace(should_block_run=False, describe=lambda: "rotated"),
    )


def started(monkeypatch, bridge_module):
    from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

    start = TikTokStartup(device=object(), bot_username="acting")
    monkeypatch.setattr(bridge_module, "tiktok_startup_provider", lambda device_id: lambda: start)


def assert_reads(contract: WorkflowContract, data: Dict[str, Any], log: set) -> None:
    # Below a field declared as an opaque object ("json"), what is read is that object's business.
    opaque = {(item.key,) for item in contract.settings if item.type == "json"}
    unread = {p for p in file_paths(data) if not (p[:1] in opaque and len(p) > 1)} - log
    undeclared = {p for p in log if not (p[:1] in opaque and len(p) > 1)} - declared_paths(contract)
    assert not unread, f"keys of the file nobody reads: {sorted(unread)}"
    assert not undeclared, f"keys read and not declared: {sorted(undeclared)}"


# ------------------------------------------------------------------------------------ unfollow


class _Unfollow:
    fail = False

    def __init__(self, device, config):
        self.config = config
        self.callbacks = {}

    def __getattr__(self, name):
        if name.startswith("set_on_") and name.endswith("_callback"):
            return lambda cb: self.callbacks.__setitem__(name[len("set_on_"):-len("_callback")], cb)
        raise AttributeError(name)

    def run(self):
        from taktik.core.social_media.tiktok.actions.business.workflows.unfollow.models import UnfollowStats

        if self.fail:
            raise RuntimeError("the list did not open")
        self.callbacks["unfollow"]("alice", 1)
        self.callbacks["skip"]("bob", "friends")
        self.callbacks["skip"](None, "handle_unknown")
        self.callbacks["unconfirmed"]("carol", "following")
        stats = UnfollowStats(unfollowed=1, skipped_friends=1, unconfirmed=1, refusals={"friends": 1})
        self.callbacks["stats"](stats.to_dict())
        stats.stop_reason = "unfollow_unconfirmed"
        return stats


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_unfollow_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation, fail):
    import bridges.tiktok.automation.runtime.unfollow as bridge
    import taktik.core.social_media.tiktok.actions.business.workflows.unfollow.workflow as workflow

    started(monkeypatch, bridge)
    monkeypatch.setattr(_Unfollow, "fail", fail)
    monkeypatch.setattr(workflow, "UnfollowWorkflow", _Unfollow)
    data = bridge_file(TIKTOK_UNFOLLOW)
    log: set = set()

    assert bridge.TikTokUnfollowBridge(Recording(data, log)).run() == (1 if fail else 0)

    assert_reads(TIKTOK_UNFOLLOW, data, log)
    check_lines(TIKTOK_UNFOLLOW, lines)
    expected = {"status", "error"} if fail else {"status", "unfollow_event", "unfollow_stats"}
    assert {line["type"] for line in lines} == expected


# ------------------------------------------------------------------------------------- cold DM


def _outreach_class():
    from taktik.core.social_media.tiktok.actions.business.workflows.dm import outreach

    class Outreach(outreach.TikTokDMOutreachWorkflow):
        """The production workflow; only what it asks of the phone answers from a script."""

        def __init__(self, device_id, **kwargs):
            super().__init__(device_id, rng=random.Random(0), sleeper=lambda seconds: None, **kwargs)

        def connect(self):
            self.navigation = SimpleNamespace(navigate_to_home=lambda: None)
            return True

        def navigate_to_user_profile(self, username):
            return username != "bob"

        def open_conversation_from_profile(self):
            return outreach.NO_MESSAGE_ENTRY if self._current == "carol" else outreach.CONVERSATION_OPENED

        def _process_recipient(self, recipient, *args, **kwargs):
            self._current = recipient
            return super()._process_recipient(recipient, *args, **kwargs)

        def send_dm(self, message):
            return {"dave": "privacy_blocked", "erin": False, "frank": outreach.ACTION_BLOCKED}.get(self._current, True)

    return Outreach


def test_the_cold_dm_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation):
    import bridges.tiktok.engagement.runtime.dm_outreach as bridge
    import taktik.core.database.tiktok_dm as sent_dms
    from taktik.core.social_media.tiktok.actions.business.workflows.dm import agent_handler

    monkeypatch.setattr(agent_handler, "_default_outreach_factory", _outreach_class)
    monkeypatch.setattr(sent_dms, "cold_dm_already_sent", lambda *a, **k: False)
    monkeypatch.setattr(sent_dms, "record_cold_dm", lambda *a, **k: None)
    recipients = ["alice", "bob", "carol", "dave", "erin", "frank"]
    data = bridge_file(TIKTOK_DM_OUTREACH, recipients=recipients, maxDms=len(recipients), messages=["Hello"])
    log: set = set()

    assert bridge.TikTokDMOutreachBridge(Recording(data, log)).run() == 0
    assert_reads(TIKTOK_DM_OUTREACH, data, log)

    from bridges.tiktok.runtime.ipc import _ipc, send_error

    # The AI transport's own report of a paid call, and the bridge's error helper.
    _ipc.ai_spend(0.0012, model="qwen", label="alice", kind="dm")
    send_error("DM Outreach error: the phone went away")
    check_lines(TIKTOK_DM_OUTREACH, lines)
    assert {line["type"] for line in lines} == {event.type for event in TIKTOK_DM_OUTREACH.events}


# ------------------------------------------------------------------------------------ scraping


class _Scraping:
    def __init__(self, device, navigation, config):
        from taktik.core.social_media.tiktok.actions.business.workflows.scraping.models import ScrapingStats

        self.config = config
        self.callbacks = {}
        self.completion_reason = None
        self.stats = ScrapingStats()

    def __getattr__(self, name):
        if name.startswith("set_on_") and name.endswith("_callback"):
            return lambda cb: self.callbacks.__setitem__(name[len("set_on_"):-len("_callback")], cb)
        raise AttributeError(name)

    def run(self):
        profile = {"username": "alice", "followers_count": 12, "following_count": 3}
        self.callbacks["status"]("running", "Reading @target's followers")
        self.callbacks["progress"](1, self.config.max_profiles, "alice")
        self.callbacks["profile"](profile)
        self.callbacks["save_profile"](profile)
        self.callbacks["error"]("One profile did not open")
        self.completion_reason = "completed"
        return [profile]


def test_the_scraping_bridge_follows_its_contract(monkeypatch, lines):
    import bridges.tiktok.scraping.runtime.workflow as bridge
    import taktik.core.database.tiktok_scraping as rows
    from taktik.core.social_media.tiktok.actions.business.workflows.scraping import agent_handler

    started(monkeypatch, bridge)
    monkeypatch.setattr(agent_handler, "_default_workflow_factory", lambda: _Scraping)
    monkeypatch.setattr(agent_handler, "_default_navigation_factory", lambda: (lambda device: object()))
    monkeypatch.setattr(rows, "open_scraping_session", lambda *a, **k: 7)
    monkeypatch.setattr(rows, "save_scraped_profile", lambda *a, **k: None)
    monkeypatch.setattr(rows, "close_scraping_session", lambda *a, **k: None)
    data = bridge_file(TIKTOK_SCRAPING)
    log: set = set()

    assert bridge.TikTokScrapingBridge(Recording(data, log)).run() == 0

    assert_reads(TIKTOK_SCRAPING, data, log)
    check_lines(TIKTOK_SCRAPING, lines)
    assert {line["type"] for line in lines} == {event.type for event in TIKTOK_SCRAPING.events}


# ------------------------------------------------------------------ dispatcher: video workflows


class _Video:
    """A video workflow whose screen work answers from a script: each callback fires once."""

    fail = False

    def __init__(self, device, config):
        self.config = config
        self.callbacks = {}

    def __getattr__(self, name):
        if name.startswith("set_on_") and name.endswith("_callback"):
            return lambda cb: self.callbacks.__setitem__(name[len("set_on_"):-len("_callback")], cb)
        raise AttributeError(name)

    def run(self):
        from taktik.core.social_media.tiktok.actions.business.workflows._internal.models import VideoWorkflowStats

        if self.fail:
            raise RuntimeError("the feed did not open")
        video = {"author": "alice", "description": "A caption", "like_count": "1.2K", "is_liked": False,
                 "is_followed": False, "is_ad": False, "hashtags": ["cats"], "sound": "original sound",
                 "watch_time": 4.2}
        self.callbacks["video"](video)
        self.callbacks["like"](video)
        self.callbacks["follow"](video)
        self.callbacks["stats"]({"videos_watched": 1, "videos_liked": 1, "users_followed": 1})
        self.callbacks["pause"](30)
        return VideoWorkflowStats(videos_watched=1, videos_liked=1, users_followed=1, completion_reason="feed_stuck")


def _dispatcher(monkeypatch, runner_module):
    import bridges.tiktok.workflows.runtime.dispatcher as dispatcher
    from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

    monkeypatch.setattr(dispatcher, "force_stop_tiktok", lambda device_id: None)
    start = TikTokStartup(device=object(), bot_username="acting")
    monkeypatch.setattr(runner_module, "_startup", lambda device_id: lambda: start)
    return dispatcher


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_for_you_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation, fail):
    import bridges.tiktok.workflows.automation.for_you as runner
    import taktik.core.social_media.tiktok.actions.business.workflows.for_you.workflow as workflow

    dispatcher = _dispatcher(monkeypatch, runner)
    monkeypatch.setattr(_Video, "fail", fail)
    monkeypatch.setattr(workflow, "ForYouWorkflow", _Video)
    data = bridge_file(TIKTOK_FOR_YOU)
    log: set = set()

    assert dispatcher.TikTokDispatcherBridge(Recording(data, log)).run() == (1 if fail else 0)

    assert_reads(TIKTOK_FOR_YOU, data, log)
    check_lines(TIKTOK_FOR_YOU, lines)
    expected = {"status", "error"} if fail else {"status", "stats", "video_info", "action", "pause"}
    assert {line["type"] for line in lines} == expected


@pytest.mark.parametrize("workflow_type", ["search", "hashtag"])
def test_the_search_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation, workflow_type):
    import bridges.tiktok.workflows.automation.search as runner
    import taktik.core.social_media.tiktok.actions.business.workflows.search.agent_handler as launcher
    import taktik.core.social_media.tiktok.actions.business.workflows.search.workflow as workflow

    dispatcher = _dispatcher(monkeypatch, runner)
    monkeypatch.setattr(_Video, "fail", False)
    monkeypatch.setattr(workflow, "SearchWorkflow", _Video)
    monkeypatch.setattr(launcher, "_return_home", lambda device: None)
    data = bridge_file(TIKTOK_SEARCH, workflowType=workflow_type)
    log: set = set()

    assert dispatcher.TikTokDispatcherBridge(Recording(data, log)).run() == 0
    # The hashtag list wins: the other query keys of the file are never reached.
    later = {("searchQueries",), ("searchQuery",), *((a,) for a in TIKTOK_SEARCH.setting("searchQuery").aliases)}
    assert_reads(TIKTOK_SEARCH, data, log | later)

    from bridges.tiktok.runtime.ipc import send_error

    send_error("Search workflow error: the search field did not open")
    check_lines(TIKTOK_SEARCH, lines)
    assert {line["type"] for line in lines} == {event.type for event in TIKTOK_SEARCH.events} - _ELSEWHERE


# ---------------------------------------------------- dispatcher: profile-visiting workflows


class _Profiles:
    """A profile-visiting workflow whose screen work answers from a script."""

    fail = False

    def __init__(self, device, config, **kwargs):
        self.config = config
        self.callbacks = {}

    def __getattr__(self, name):
        if name.startswith("set_on_") and name.endswith("_callback"):
            return lambda cb: self.callbacks.__setitem__(name[len("set_on_"):-len("_callback")], cb)
        raise AttributeError(name)

    def run(self, bot_username=None):
        from taktik.core.social_media.tiktok.actions.business.workflows.followers.models import FollowersStats

        if self.fail:
            raise RuntimeError("the list did not open")
        stats = FollowersStats(followers_seen=3, profiles_visited=1, posts_watched=2, likes=1, follows=1)
        self.callbacks["action"]({"action": "like", "target": "alice"})
        self.callbacks["profile"]({"username": "alice", "display_name": "Alice", "followers_count": 12,
                                   "following_count": 3, "likes_count": 40, "videos_count": 5,
                                   "biography": "A bio", "is_private": False, "is_verified": False})
        self.callbacks["stats"](stats.to_dict())
        self.callbacks["pause"](20)
        stats.completion_reason = "completed"
        return stats


def _profile_run(monkeypatch, runner_module, workflow_module, class_name, fail=False):
    monkeypatch.setattr(_Profiles, "fail", fail)
    monkeypatch.setattr(workflow_module, class_name, _Profiles)
    return _dispatcher(monkeypatch, runner_module)


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_followers_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation, fail):
    import bridges.tiktok.workflows.automation.followers as runner
    import taktik.core.social_media.tiktok.actions.business.workflows.followers.agent_handler as launcher
    import taktik.core.social_media.tiktok.actions.business.workflows.followers.workflow as workflow
    from taktik.core.contract.tiktok_profiles import TIKTOK_FOLLOWERS

    dispatcher = _profile_run(monkeypatch, runner, workflow, "FollowersWorkflow", fail)
    monkeypatch.setattr(launcher, "_return_home", lambda device: True)
    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: None)
    data = bridge_file(TIKTOK_FOLLOWERS)
    log: set = set()

    assert dispatcher.TikTokDispatcherBridge(Recording(data, log)).run() == (1 if fail else 0)

    # The target list wins: the single-target keys of the file are never reached.
    later = {("targets",), ("searchQuery",), *((a,) for a in TIKTOK_FOLLOWERS.setting("searchQuery").aliases)}
    assert_reads(TIKTOK_FOLLOWERS, data, log | later)
    check_lines(TIKTOK_FOLLOWERS, lines)
    printed = {line["type"] for line in lines}
    if fail:
        assert printed == {"status", "error", "target_switch", "workflow_start"}
    else:
        assert printed == {event.type for event in TIKTOK_FOLLOWERS.events} - {"error"} - _ELSEWHERE


@pytest.mark.parametrize("name", ["target_profiles", "post_url"])
def test_the_single_pass_bridges_follow_their_contract(monkeypatch, lines, no_ip_rotation, name):
    import importlib

    from taktik.core.contract import tiktok_profiles

    contract = {"target_profiles": tiktok_profiles.TIKTOK_TARGET_PROFILES,
                "post_url": tiktok_profiles.TIKTOK_POST_URL}[name]
    runner = importlib.import_module(f"bridges.tiktok.workflows.automation.{name}")
    workflow = importlib.import_module(f"{_WORKFLOWS}.{name}.workflow")
    class_name = {"target_profiles": "TargetProfilesWorkflow", "post_url": "PostUrlWorkflow"}[name]
    dispatcher = _profile_run(monkeypatch, runner, workflow, class_name)
    overrides = {"postUrl": "https://www.tiktok.com/@example/video/1"} if name == "post_url" else {}
    data = bridge_file(contract, **overrides)
    log: set = set()

    assert dispatcher.TikTokDispatcherBridge(Recording(data, log)).run() == 0
    assert_reads(contract, data, log)

    from bridges.tiktok.runtime.ipc import send_error

    send_error("Workflow error: the profile did not open")
    check_lines(contract, lines)
    assert {line["type"] for line in lines} == {event.type for event in contract.events} - _ELSEWHERE


# ------------------------------------------- dispatcher: sync, DMs, inbox, notifications


class _Scripted:
    """A workflow whose screen work answers from a script; its methods fire its callbacks."""

    def __init__(self, device, config=None, **kwargs):
        self.config = config
        self.callbacks = {}

    def __getattr__(self, name):
        if name.startswith("set_on_") and name.endswith("_callback"):
            return lambda cb: self.callbacks.__setitem__(name[len("set_on_"):-len("_callback")], cb)
        raise AttributeError(name)


def _patch_dm_rows(monkeypatch):
    import taktik.core.database.tiktok_dm as rows

    for name in ("record_conversations", "record_sent_results"):
        monkeypatch.setattr(rows, name, lambda *a, **k: None)
    monkeypatch.setattr(rows, "resolve_account_id", lambda *a, **k: 1)


def _engagement_run(monkeypatch, runner_name, contract, workflow_class, *, provider=True, **overrides):
    import importlib

    import bridges.tiktok.workflows.runtime.dispatcher as dispatcher
    from taktik.core.social_media.tiktok.workflows.runtime.startup import TikTokStartup

    runner = importlib.import_module(f"bridges.tiktok.workflows.{runner_name}")
    monkeypatch.setattr(dispatcher, "force_stop_tiktok", lambda device_id: None)
    start = TikTokStartup(device=object(), bot_username="acting")
    if provider:
        monkeypatch.setattr(runner, "tiktok_startup_provider", lambda device_id: lambda: start)
    else:
        monkeypatch.setattr(runner, "_startup", lambda device_id: lambda: start)
    monkeypatch.setattr(importlib.import_module(f"{_WORKFLOWS}.dm.workflow"), "DMWorkflow", workflow_class)
    data = bridge_file(contract, **overrides)
    log: set = set()
    code = dispatcher.TikTokDispatcherBridge(Recording(data, log)).run()
    return code, data, log


def _printed(lines):
    return {line["type"] for line in lines}


def test_the_sync_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation):
    import bridges.tiktok.workflows.automation.sync_lists as runner
    import taktik.core.social_media.tiktok.actions.business.workflows.sync_lists.workflow as workflow
    from taktik.core.contract.tiktok_engagement import TIKTOK_SYNC
    from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists.models import SyncListsStats

    class Sync(_Scripted):
        def run(self, bot_username=None):
            self.callbacks["row"]({"list_type": "following", "username": "alice", "display_name": "Alice",
                                   "relationship": "following", "is_new": True})
            return SyncListsStats(rows_seen=1, new_count=1, completion_reason="completed")

    dispatcher = _dispatcher(monkeypatch, runner)
    monkeypatch.setattr(workflow, "SyncListsWorkflow", Sync)
    data = bridge_file(TIKTOK_SYNC, workflowType="sync_following")
    log: set = set()

    assert dispatcher.TikTokDispatcherBridge(Recording(data, log)).run() == 0

    assert_reads(TIKTOK_SYNC, data, log)
    check_lines(TIKTOK_SYNC, lines)
    assert _printed(lines) == {"status", "workflow_start", "sync_user_discovered", "sync_stats"}


def test_the_dm_read_and_send_bridges_follow_their_contract(monkeypatch, lines, no_ip_rotation):
    from taktik.core.contract.tiktok_engagement import TIKTOK_DM_READ, TIKTOK_DM_SEND
    from taktik.core.social_media.tiktok.actions.business.workflows.dm.models import ConversationData, DMStats

    class Dm(_Scripted):
        def read_conversations(self):
            conversation = ConversationData(name="Alice", messages=[
                {"sender": None, "text": "Hi", "type": "text", "is_sent": False}], last_message="Hi")
            self.callbacks["progress"](1, 1, "Alice")
            self.callbacks["conversation"](conversation.to_dict())
            self.callbacks["stats"](DMStats(conversations_read=1).to_dict())
            return [conversation]

        def send_bulk_messages(self, messages):
            self.callbacks["progress"](1, len(messages), messages[0]["conversation"])
            self.callbacks["message_sent"]({"conversation": messages[0]["conversation"], "success": True})
            return [{"conversation": messages[0]["conversation"], "success": True}]

        def get_stats(self):
            return DMStats(conversations_read=1)

    _patch_dm_rows(monkeypatch)
    code, data, log = _engagement_run(monkeypatch, "engagement.dm_read", TIKTOK_DM_READ, Dm)
    assert code == 0
    assert_reads(TIKTOK_DM_READ, data, log)
    check_lines(TIKTOK_DM_READ, lines)
    assert _printed(lines) == {"status", "dm_progress", "dm_conversation", "dm_stats"}

    lines.clear()
    code, data, log = _engagement_run(monkeypatch, "engagement.dm_send", TIKTOK_DM_SEND, Dm)
    assert code == 0
    assert_reads(TIKTOK_DM_SEND, data, log)
    check_lines(TIKTOK_DM_SEND, lines)
    assert _printed(lines) == {"status", "dm_progress", "dm_sent", "dm_stats"}


class _Inbox(_Scripted):
    def read_new_followers(self, max_items):
        row = {"username": "Alice", "activity": "started following you", "can_follow_back": True}
        self.callbacks["new_follower"](row)
        return [row]

    def follow_back_users(self, usernames):
        result = {"username": usernames[0], "success": True}
        self.callbacks["follow_back_result"](result)
        return [result]

    def read_unreplied_conversations(self, max_items, only_unreplied):
        row = {"username": "Alice", "preview": "Hello?", "unreplied": True}
        self.callbacks["unreplied"](row)
        return [row]

    def read_message_requests(self, max_items):
        row = {"username": "Bob", "preview": "Hi", "timestamp": "2h"}
        self.callbacks["message_request"](row)
        return [row]

    def process_message_requests(self, decisions):
        result = {"username": decisions[0]["username"], "action": "accept", "success": True, "replied": False}
        self.callbacks["request_result"](result)
        return [result]

    def read_notifications(self, max_items):
        row = {"title": "System notifications", "preview": "Your video", "category": "system"}
        self.callbacks["notification"](row)
        return [row]


#: (runner, contract, file overrides, lines printed, keys of the file this mode does not reach)
_INBOX_RUNS = (
    # Listing: the names to act on and the pace between two actions are the other mode's; the
    # language is read by the AI welcome pass only, off here.
    ("engagement.new_followers", "TIKTOK_NEW_FOLLOWERS", {}, {"status", "new_follower"},
     {"usernames", "delayBetweenActions", "language"}),
    # Following back: no list read, no welcome pass.
    ("engagement.new_followers", "TIKTOK_NEW_FOLLOWERS", {"mode": "follow_back"}, {"status", "follow_back_result"},
     {"maxItems", "ai", "language"}),
    ("engagement.unreplied", "TIKTOK_UNREPLIED", {}, {"status", "unreplied_conversation"}, set()),
    ("engagement.requests", "TIKTOK_REQUESTS", {}, {"status", "message_request"},
     {"decisions", "delayBetweenActions"}),
    ("engagement.requests", "TIKTOK_REQUESTS", {"mode": "execute"}, {"status", "request_result"}, {"maxItems"}),
    ("engagement.activity", "TIKTOK_ACTIVITY", {}, {"status", "activity_notification"}, set()),
)


@pytest.mark.parametrize("runner, name, overrides, printed, other_mode", _INBOX_RUNS)
def test_the_inbox_bridges_follow_their_contract(monkeypatch, lines, no_ip_rotation, runner, name, overrides,
                                                 printed, other_mode):
    from taktik.core.contract import tiktok_engagement

    contract = getattr(tiktok_engagement, name)
    code, data, log = _engagement_run(monkeypatch, runner, contract, _Inbox, **overrides)

    assert code == 0
    assert_reads(contract, data, log | {(key,) for key in other_mode if key in data})
    check_lines(contract, lines)
    assert _printed(lines) == printed


@pytest.mark.parametrize("fail", [False, True], ids=["run", "failure"])
def test_the_notifications_bridge_follows_its_contract(monkeypatch, lines, no_ip_rotation, fail):
    import taktik.core.social_media.tiktok.actions.business.workflows.notifications.scan as scan
    from taktik.core.contract.tiktok_engagement import TIKTOK_NOTIFICATIONS

    def scanned(device, account_username, max_resolutions):
        if fail:
            raise RuntimeError("the new-followers page did not open")
        return {"listed": 2, "resolved": 1, "skipped_over_budget": 0}

    monkeypatch.setattr(scan, "scan_new_followers", scanned)
    code, data, log = _engagement_run(monkeypatch, "engagement.notifications", TIKTOK_NOTIFICATIONS, _Scripted,
                                      provider=False, readActivity=False)

    assert code == (1 if fail else 0)
    assert_reads(TIKTOK_NOTIFICATIONS, data, log)
    check_lines(TIKTOK_NOTIFICATIONS, lines)
    assert _printed(lines) == {"status", "notifications_result"}
