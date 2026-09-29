"""The Taktik Agent bridge reads the file the contract describes and prints the lines it declares.

As for the other Instagram bridges (`test_workflow_contract_instagram_bridges.py`): the whole bridge
runs, from its config file to its stdout, on the app's file, through the real launcher, the real
`TaktikAgentWorkflow`, the real `AgentAI` and the real AI service; only the screen work, the base,
the model's HTTP transport and the clock are replaced. The lines come from the production emitters
(the IPC's Agent and AI helpers, `IPCEmitter`, the step telemetry), not from the test.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest

from contract_probe import Recording
from ig_automation_probe import use_the_bridge_ipc
from taktik.core.contract.instagram_agent import INSTAGRAM_TAKTIK_AGENT
from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService
from test_workflow_contract_bridges import check_lines
from test_workflow_contract_instagram_bridges import app_file, assert_reads, printed  # noqa: F401

AGENT = INSTAGRAM_TAKTIK_AGENT

#: What the desktop prepared: one planned step it words itself, and an intro.
ORCHESTRATION = {
    "introMessage": "The last sessions liked a lot; this one explores.",
    "nextSteps": [{"tool": "browse_feed", "message": "Scroll the home feed first"}],
}

#: The account's warmup caps as the launch gate hands them to the bot (`WarmupPolicyForBot`): the
#: cold start of the curve.
WARMUP = {"maxActionsPerDay": 50, "maxFollowsPerDay": 10, "maxCommentsPerDay": 5, "minActionGapSeconds": 45,
          "maxActionsPerSession": 25, "maxUnfollowsPerDay": 10}

_FEED_POST = "Analyse this feed post"
_SKIP = {"action": "skip", "visit_profile": False, "reason": "off topic"}
_LIKE_COMMENT = {"action": "like_comment", "visit_profile": True, "comment": "Lovely bread", "reason": "bakes"}


class _Response:
    """What OpenRouter answers: the text and its cost."""

    def __init__(self, text: str):
        self.body = json.dumps({
            "model": "qwen", "choices": [{"message": {"content": text}, "finish_reason": "stop"}],
            "usage": {"cost": 0.0002, "prompt_tokens": 40, "completion_tokens": 12},
        }).encode("utf-8")

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _OpenRouter:
    """The model: a post liked and commented with its author to visit, then posts left alone.

    `engaged` posts are liked and commented instead of one; `extra_likes` are asked on the author's
    profile, after the follow."""

    def __init__(self, engaged: int = 1, extra_likes: int = 1):
        self.feed = [_LIKE_COMMENT] * engaged
        self.extra_likes = extra_likes

    def __call__(self, request, timeout=None):
        message = json.loads(request.data.decode("utf-8"))["messages"][-1]["content"]
        text = message if isinstance(message, str) else next(p["text"] for p in message if p.get("type") == "text")
        if "hashtags" in text:
            return _Response('["bakery", "bread"]')
        if text.startswith("Should I follow"):
            return _Response(json.dumps({"follow": True, "extra_likes": self.extra_likes, "reason": "a baker"}))
        assert text.startswith(_FEED_POST), text
        return _Response(json.dumps(self.feed.pop(0) if self.feed else _SKIP))


class _Screen:
    """The phone: nothing on it matches a selector; a screenshot is a small picture."""

    info = {"displayWidth": 1080, "displayHeight": 2340}

    def xpath(self, selector):
        return SimpleNamespace(exists=False, click=lambda: None, all=lambda: [])

    def screenshot(self, path):
        from PIL import Image

        Image.new("RGB", (8, 8), "white").save(path, "PNG")

    def human_scroll(self, direction, **kwargs):
        # The facade's gesture reports itself to the step telemetry.
        from taktik.core.shared.telemetry import emit_step

        emit_step("scroll", action="curve", target=direction)
        return True

    def press(self, key):
        return None


def _feed_class():
    from loguru import logger

    from taktik.core.social_media.instagram.actions.core.base_business.stats_recording import StatsRecordingMixin

    class Feed(StatsRecordingMixin):
        """The feed's own recording of a gesture (`_record_action`); only its screen answers here."""

        def __init__(self, device_manager, automation=None):
            self.device_manager = device_manager
            self.automation = automation
            self.session_manager = None
            self.active_account_id = None
            self.logger = logger

        def _is_sponsored_post(self):
            return False

        def _is_reel_post(self):
            return False

        def _get_current_post_author(self):
            return "alice"

        def _like_current_post(self, record_as=None):
            return self._record_action(record_as, "LIKE", 1)

        def _comment_feed_post(self, author, config, comment_text=None):
            self._record_action(author, "COMMENT", 1, content=comment_text)
            return {"commented": True}

        def _scroll_to_next_post(self):
            self.device_manager.device.human_scroll("down", distance_ratio=0.5)

    return Feed


class _OwnProfile:
    """The acting account's profile, read the way the extraction announces it."""

    def __init__(self, device_manager):
        pass

    def get_complete_profile_info(self, navigate_if_needed=True, **kwargs):
        from taktik.core.social_media.instagram.actions.core.ipc import IPCEmitter

        info = {"username": "acting", "full_name": "Acting", "biography": "Bakery", "followers_count": 340,
                "following_count": 12, "posts_count": 9, "is_private": False, "is_verified": False}
        IPCEmitter.emit_profile_captured(username="acting", profile_data=info,
                                         profile_pic_base64="data:image/jpeg;base64,AAAA")
        return info


class _Navigation:
    def __init__(self, device_manager):
        pass

    def navigate_to_profile_tab(self):
        return True

    def navigate_to_home(self):
        return True

    def navigate_to_profile(self, username):
        return True

    def navigate_to_hashtag(self, hashtag):
        return True


class _Click:
    def __init__(self, device):
        pass

    def get_follow_button_state(self):
        return "follow"

    def follow_user(self, username):
        return True


def _likes_class():
    from loguru import logger

    from taktik.core.social_media.instagram.actions.core.base_business.stats_recording import StatsRecordingMixin

    class Likes(StatsRecordingMixin):
        """The likes on a profile, filed in one batch like the production sequence."""

        def __init__(self, device_manager, automation=None):
            self.automation = automation
            self.session_manager = None
            self.active_account_id = None
            self.logger = logger

        def like_profile_posts(self, username, max_likes=1, navigate_to_profile=False):
            self._record_action(username, "LIKE", max_likes)
            return {"posts_liked": max_likes}

    return Likes


@pytest.fixture
def agent_bridge(monkeypatch, tmp_path):
    """The bridge's module, its phone and its base replaced; `restarts` says whether Instagram opens."""
    import tempfile

    import bridges.instagram.agent.runtime.commands as commands
    import taktik.core.social_media.instagram.workflows.agent.autopilot as autopilot
    import taktik.core.shared.diagnostics.action_block as action_block
    import taktik.core.social_media.instagram.actions.atomic.interaction as interaction
    import taktik.core.social_media.instagram.actions.atomic.navigation as navigation
    import taktik.core.social_media.instagram.actions.business.actions.like as like
    import taktik.core.social_media.instagram.actions.business.management.profile as profile
    import taktik.core.social_media.instagram.actions.business.workflows.feed as feed
    import taktik.core.social_media.instagram.ui.detectors.problematic_page as problematic_page
    import taktik.core.social_media.instagram.ui.language as language
    import taktik.core.social_media.instagram.workflows.common.post_navigation as post_navigation
    import taktik.core.social_media.instagram.workflows.management.session.warmup_budget as warmup_budget
    from taktik.core.database.instagram_workflow_state import InstagramWorkflowStateService

    state = SimpleNamespace(restarts=True, packages=[])

    class Bridge(commands.TaktikAgentBridge):
        """The bridge's connection, on the launcher's package; the restart of Instagram answers here."""

        def __init__(self, device_id, package_name=None):
            state.packages.append(package_name)
            self.device_manager = SimpleNamespace(device=_Screen())
            self._app = SimpleNamespace(restart=lambda: state.restarts)

        def connect(self):
            return True

    monkeypatch.setattr(commands, "TaktikAgentBridge", Bridge)
    monkeypatch.setattr(commands, "configure_agent_database", lambda: None)
    monkeypatch.setattr(commands, "start_agent_stop_listener", lambda: None)
    use_the_bridge_ipc(monkeypatch)

    monkeypatch.setattr(urllib.request, "urlopen", _OpenRouter())
    # The base: the acting account on record, an empty day for the warmup budget.
    base = SimpleNamespace(get_account_by_username=lambda username: {"account_id": 3, "niche": "bakery"},
                           get_today_totals=lambda account_id: {"total": 0, "follows": 0, "comments": 0})
    monkeypatch.setattr(autopilot, "get_db_service", lambda: base)
    monkeypatch.setattr(warmup_budget, "get_db_service", lambda: base)
    monkeypatch.setattr(InstagramWorkflowStateService, "record_individual_actions",
                        staticmethod(lambda *args, **kwargs: None))
    monkeypatch.setattr(language, "detect_and_optimize", lambda device: None)
    monkeypatch.setattr(profile, "ProfileBusiness", _OwnProfile)
    monkeypatch.setattr(navigation, "NavigationActions", _Navigation)
    monkeypatch.setattr(interaction, "ClickActions", _Click)
    monkeypatch.setattr(like, "LikeBusiness", _likes_class())
    monkeypatch.setattr(feed, "FeedBusiness", _feed_class())
    monkeypatch.setattr(post_navigation, "open_first_post_of_profile", lambda device, log=None: True)
    monkeypatch.setattr(problematic_page, "ProblematicPageDetector", lambda device: None)
    monkeypatch.setattr(action_block, "look_for_action_block", lambda detector, after=None: False)
    monkeypatch.setattr(autopilot.random, "randint", lambda low, high: low)
    monkeypatch.setattr(autopilot.random, "uniform", lambda low, high: low)
    monkeypatch.setattr(autopilot.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    commands.state = state
    return commands


def _session(**chosen: Any) -> Dict[str, Any]:
    """The app's file: one post engaged and its author followed, a hashtag explored, then the end.

    With the warmup caps of the launch gate's ticket, as the main process writes it."""
    chosen = {"desktop_orchestration_context": dict(ORCHESTRATION), "warmupPolicy": dict(WARMUP), **chosen}
    data = app_file(AGENT, **chosen)
    data.update(max_posts_seen=13, session_duration_min=5)
    return data


def test_the_agent_bridge_follows_its_contract(agent_bridge, printed):
    data = _session()
    log: set = set()

    assert agent_bridge.TaktikAgentRun(Recording(data, log)).run() == 0

    assert_reads(AGENT, data, log)
    # The launcher read the clone of the file and the bridge connected on it.
    assert agent_bridge.state.packages == [data["packageName"]]
    lines = printed()
    check_lines(AGENT, lines)
    # Every declared line but a failure's, each from the session's own path.
    assert {line["type"] for line in lines} == {event.type for event in AGENT.events} - {"error"}
    statuses = [line["status"] for line in lines if line["type"] == "agent_status"]
    assert statuses == ["account_detected", "orchestration_context", "planning", "navigating", "running",
                        "completed"]
    assert [line["to_strategy"] for line in lines if line["type"] == "strategy_switch"] == ["hashtag", "feed"]


@pytest.mark.parametrize("failure", ["no_device", "no_connection", "no_instagram"])
def test_a_failure_of_the_bridge_is_an_error_line(agent_bridge, printed, failure):
    data = _session()
    if failure == "no_device":
        del data["deviceId"]
    elif failure == "no_connection":
        agent_bridge.TaktikAgentBridge.connect = lambda self: False
    else:
        agent_bridge.state.restarts = False

    assert agent_bridge.TaktikAgentRun(data).run() == 1

    lines = printed()
    check_lines(AGENT, lines)
    assert lines[-1]["type"] == "error"


def test_a_session_without_a_key_is_refused_before_instagram_is_touched(agent_bridge, printed):
    data = _session()
    del data["openrouter_api_key"]
    agent_bridge.state.restarts = None  # a restart would fail the session another way

    assert agent_bridge.TaktikAgentRun(data).run() == 1

    assert agent_bridge.state.packages == []  # never connected
    lines = printed()
    check_lines(AGENT, lines)
    assert [line["type"] for line in lines] == ["agent_status"]
    assert lines[0]["status"] == "error" and lines[0]["message_key"] == "agentStatusErrNoAi"


# ------------------------------------------------------------------------------ the warmup budget

#: How a gesture is filed, kept before a fixture replaces it: the budget test files for real.
_FILE_GESTURES = InstagramWorkflowStateService.__dict__["record_individual_actions"]


@pytest.fixture
def ledger(agent_bridge, monkeypatch, tmp_path):
    """A real, empty base: the session files its gestures in it, the budget reads the day from it."""
    import taktik.core.social_media.instagram.workflows.agent.autopilot as autopilot
    import taktik.core.database as database
    import taktik.core.database.local.service as service
    import taktik.core.social_media.instagram.workflows.management.session.warmup_budget as warmup_budget

    base = service.LocalDatabaseService(db_path=str(tmp_path / "agent.db"))
    monkeypatch.setattr(service, "_local_db_instance", base)
    client = database.LocalDatabaseClient()
    monkeypatch.setattr(database, "db_service", client)
    monkeypatch.setattr(autopilot, "get_db_service", database.get_db_service)
    monkeypatch.setattr(warmup_budget, "get_db_service", database.get_db_service)
    monkeypatch.setattr(InstagramWorkflowStateService, "record_individual_actions", _FILE_GESTURES)
    account_id, _ = client.get_or_create_account("acting", is_bot=True)

    def earlier(kind: str, count: int) -> None:
        """Gestures of an earlier run today, filed like the session's."""
        for index in range(count):
            client.record_interaction(account_id, f"earlier_{kind.lower()}_{index}", interaction_type=kind)

    yield SimpleNamespace(today=lambda: client.get_today_totals(account_id), earlier=earlier)
    base.close()


def _budget_run(agent_bridge, printed, monkeypatch, warmup: Dict[str, Any], engaged: int = 20,
                extra_likes: int = 0, model: Optional[_OpenRouter] = None) -> Dict[str, Any]:
    """The bridge run on the app's file with the ticket's caps; the model engages every post."""
    monkeypatch.setattr(urllib.request, "urlopen", model or _OpenRouter(engaged=engaged, extra_likes=extra_likes))
    assert agent_bridge.TaktikAgentRun(_session(warmupPolicy=dict(warmup))).run() == 0
    lines = printed()
    check_lines(AGENT, lines)
    return next(line for line in lines if line["type"] == "agent_status" and line["status"] == "completed")["stats"]


def test_the_agent_stops_when_the_day_budget_is_spent_gesture_by_gesture(agent_bridge, ledger, printed,
                                                                          monkeypatch):
    """Launched 2 actions under the day's budget: a like, a comment, then no follow, and the end."""
    ledger.earlier("LIKE", 48)

    stats = _budget_run(agent_bridge, printed, monkeypatch, WARMUP)

    assert ledger.today()["total"] == WARMUP["maxActionsPerDay"]
    assert (stats["likes"], stats["comments"], stats["follows"]) == (1, 1, 0)
    assert stats["stop_reason"] == "daily_budget"
    # The numbers of the sentence the app shows for it ("Budget du jour atteint (50/50)").
    assert stats["stop_reason_params"] == {"count": 50, "limit": 50}
    # The session ends there: no visit of the author, no other post, no model call paid for them.
    assert stats["profile_visits"] == 0
    assert stats["posts_seen"] == 1


class _AnotherRunFilesDuringTheDecision(_OpenRouter):
    """The model, while another run of the same account files a like during the first decision."""

    def __init__(self, file_one_like):
        super().__init__(engaged=20, extra_likes=0)
        self._file_one_like = file_one_like

    def __call__(self, request, timeout=None):
        if self._file_one_like is not None and _FEED_POST in request.data.decode("utf-8"):
            self._file_one_like()
            self._file_one_like = None
        return super().__call__(request, timeout)


def test_the_day_is_read_again_just_before_the_like(agent_bridge, ledger, printed, monkeypatch):
    """One action left when the post is chosen, none when the like would be made: no like."""
    ledger.earlier("LIKE", 49)
    model = _AnotherRunFilesDuringTheDecision(lambda: ledger.earlier("LIKE", 1))

    stats = _budget_run(agent_bridge, printed, monkeypatch, WARMUP, model=model)

    assert ledger.today()["total"] == WARMUP["maxActionsPerDay"]
    assert (stats["likes"], stats["comments"], stats["follows"]) == (0, 0, 0)
    assert stats["stop_reason"] == "daily_budget"


def test_the_agent_stops_at_the_session_cap_of_the_warmup(agent_bridge, ledger, printed, monkeypatch):
    stats = _budget_run(agent_bridge, printed, monkeypatch, {**WARMUP, "maxActionsPerSession": 4})

    assert ledger.today()["total"] == 4
    assert (stats["likes"], stats["comments"], stats["follows"]) == (2, 1, 1)
    assert stats["stop_reason"] == "session_action_cap"
    assert stats["stop_reason_params"] == {"count": 4, "limit": 4}


def test_the_extra_likes_on_a_profile_stay_under_the_day_budget(agent_bridge, ledger, printed, monkeypatch):
    """The likes asked on the author's profile are cut to what the day has left."""
    ledger.earlier("LIKE", 46)

    stats = _budget_run(agent_bridge, printed, monkeypatch, WARMUP, extra_likes=2)

    assert ledger.today()["total"] == WARMUP["maxActionsPerDay"]
    assert stats["stop_reason"] == "daily_budget"


def test_a_spent_follow_or_comment_quota_disables_that_gesture_only(agent_bridge, ledger, printed, monkeypatch):
    """The automation's rule: the day's follows and comments spent, the session goes on liking."""
    ledger.earlier("FOLLOW", WARMUP["maxFollowsPerDay"])
    ledger.earlier("COMMENT", WARMUP["maxCommentsPerDay"])

    stats = _budget_run(agent_bridge, printed, monkeypatch, WARMUP)

    today = ledger.today()
    assert (today["follows"], today["comments"]) == (WARMUP["maxFollowsPerDay"], WARMUP["maxCommentsPerDay"])
    assert stats["likes"] > 0 and (stats["comments"], stats["follows"]) == (0, 0)
    assert "stop_reason" not in stats


def test_without_caps_the_agent_keeps_its_own_quotas(agent_bridge, ledger, printed, monkeypatch):
    """Standalone, or a file without the ticket's caps: nothing of the warmup applies."""
    ledger.earlier("LIKE", 48)
    monkeypatch.setattr(urllib.request, "urlopen", _OpenRouter(engaged=20, extra_likes=0))
    data = _session()
    del data["warmupPolicy"]

    assert agent_bridge.TaktikAgentRun(data).run() == 0

    assert ledger.today()["total"] > WARMUP["maxActionsPerDay"]


def test_two_gestures_are_never_closer_than_the_warmup_gap(agent_bridge, ledger, printed, monkeypatch):
    """The automation's pace floor (`minActionGapSeconds`, 45 s on a cold account) between every two
    gestures of the session: the like, its comment, the follow, the like on the author's profile.
    The Agent chained them 1.5 to 6 s apart."""
    import taktik.core.social_media.instagram.workflows.agent.autopilot as autopilot
    from taktik.core.social_media.instagram.actions.core.base_business.stats_recording import StatsRecordingMixin

    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(autopilot.time, "sleep", lambda seconds: setattr(clock, "now", clock.now + seconds))
    gestures = []
    file_gesture = StatsRecordingMixin._record_action

    def filed_at(self, username, action_type, count=1, **kwargs):
        gestures.append((clock.now, action_type))
        return file_gesture(self, username, action_type, count, **kwargs)

    monkeypatch.setattr(StatsRecordingMixin, "_record_action", filed_at)

    _budget_run(agent_bridge, printed, monkeypatch, WARMUP, engaged=2, extra_likes=1)

    assert [kind for _, kind in gestures] == ["LIKE", "COMMENT", "FOLLOW", "LIKE"] * 2
    gaps = [later - earlier for (earlier, _), (later, _) in zip(gestures, gestures[1:])]
    assert min(gaps) >= WARMUP["minActionGapSeconds"], gaps


class _SyncHoldsTheBaseFromTheDecision(_OpenRouter):
    """The model, while the synchronisation takes the base during the first decision."""

    def __init__(self, sync):
        super().__init__(engaged=1, extra_likes=0)
        self._sync = sync

    def __call__(self, request, timeout=None):
        if not self._sync.taken and _FEED_POST in request.data.decode("utf-8"):
            self._sync.taken = self._sync.holds = True
        return super().__call__(request, timeout)


def test_a_base_busy_through_a_like_and_its_comment_does_not_end_the_session(agent_bridge, ledger, printed,
                                                                             monkeypatch):
    """One read of the day per gesture. The sync holding the base while the Agent likes a post and
    comments it costs two failed reads, under the three in a row that stop a session
    (`daily_budget_unreadable`). Two reads per gesture ended the session at its second gesture."""
    import taktik.core.database as database
    import taktik.core.social_media.instagram.actions.business.workflows.feed as feed
    import taktik.core.social_media.instagram.workflows.management.session.warmup_budget as warmup_budget

    sync = SimpleNamespace(taken=False, holds=False)

    class Ledger:
        """The day's totals, which a read cannot get while the sync holds the base."""

        def get_today_totals(self, account_id):
            if sync.holds:
                raise sqlite3.OperationalError("database is locked")
            return database.get_db_service().get_today_totals(account_id)

    class FeedTheSyncLeavesAfterTheComment(feed.FeedBusiness):
        def _comment_feed_post(self, author, config, comment_text=None):
            result = super()._comment_feed_post(author, config, comment_text=comment_text)
            sync.holds = False
            return result

    monkeypatch.setattr(warmup_budget, "get_db_service", Ledger)
    monkeypatch.setattr(feed, "FeedBusiness", FeedTheSyncLeavesAfterTheComment)

    stats = _budget_run(agent_bridge, printed, monkeypatch, WARMUP, model=_SyncHoldsTheBaseFromTheDecision(sync))

    assert (stats["likes"], stats["comments"], stats["follows"]) == (1, 1, 1)
    assert "stop_reason" not in stats


def test_every_line_helper_of_the_agent_is_declared():
    """What `AgentIpcMixin` can print, and what the workflow sends by name, is a declared line."""
    import ast
    import inspect

    from bridges.common.runtime.ipc_agent import AgentIpcMixin
    from taktik.core.social_media.instagram.workflows.agent import autopilot as instagram_feed_autopilot

    sent = set()
    for source in (inspect.getsource(AgentIpcMixin), inspect.getsource(instagram_feed_autopilot)):
        for node in ast.walk(ast.parse(source)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "send"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                sent.add(node.args[0].value)
    assert sent == {"agent_decision", "agent_status", "strategy_switch", "follow", "comment"}
    assert sent <= {event.type for event in AGENT.events}
