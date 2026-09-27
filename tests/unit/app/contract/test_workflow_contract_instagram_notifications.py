"""The notifications bridge reads the file the contract describes and prints the lines it declares.

As for the other Instagram bridges (`test_workflow_contract_instagram_bridges.py`): the whole bridge
runs, from its config file to its stdout, on the app's file, one run per command. The production
workflow reads a real activity screen (`ig410_en_notifications.xml`, anonymized); only what moves the
phone, the base and the per-profile pipeline of the suggestions visit answer here. The lines are
printed by the production emitters (the workflow's narration, the batch, the shared suggestions
visit, the command results, the bridge's refusals), not written by the test.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from contract_probe import Recording
from taktik.core.app.contract.instagram_notifications import (
    BATCH_VERBS,
    COMMANDS,
    INSTAGRAM_NOTIFICATIONS,
    NOTIFICATION_TYPES,
    ROW_COMMANDS,
)
from test_workflow_contract_bridges import check_lines
from test_workflow_contract_instagram_bridges import app_file, assert_reads, printed  # noqa: F401

_SCREEN = Path(__file__).resolve().parents[2] / "social_media" / "instagram" / "fixtures" / "ig410_en_notifications.xml"
_MODULE = "taktik.core.social_media.instagram.workflows.management.notifications"


# ------------------------------------------------------------------------------------ vocabulary


def test_the_declared_commands_are_the_ones_the_launcher_runs():
    from taktik.core.social_media.instagram.workflows.management.notifications import commands, payload

    assert COMMANDS == payload.NOTIFICATIONS_COMMANDS
    assert ROW_COMMANDS == payload.ROW_COMMANDS
    assert set(ROW_COMMANDS) == set(commands.ROW_ACTIONS)


def test_the_declared_families_are_the_classifier_s():
    from taktik.core.social_media.instagram.ui.selectors.surfaces.notifications import NOTIFICATION_SELECTORS

    assert NOTIFICATION_TYPES.values == (*NOTIFICATION_SELECTORS.classifier_fragments, "other")


def test_the_declared_batch_verbs_are_the_batch_s():
    from taktik.core.social_media.instagram.workflows.management.notifications import commands

    assert set(BATCH_VERBS) == set(commands._batch_verbs(SimpleNamespace(), SimpleNamespace(device=None)))


# ------------------------------------------------------------------------------------ the bridge


class _Composer:
    def get_text(self):
        return ""


class _Phone:
    """Taps land nowhere."""

    def long_click(self, x, y, duration=None):
        return None

    def click(self, x, y):
        return None


def _workflow_class(screen):
    from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
        NotificationsEngagementWorkflow,
    )

    requests = [{"username": "user_20", "accept": (646, 486), "ignore": (908, 486)},
                {"username": "user_21", "accept": (646, 689), "ignore": (908, 689)}]
    suggestions = [{"label": "Name One", "state": "follow", "follow_point": (900, 1500), "row_point": (400, 1500)},
                   {"label": "Name Two", "state": "follow", "follow_point": (900, 1700), "row_point": (400, 1700)}]

    class Scripted(NotificationsEngagementWorkflow):
        """The production workflow on a real activity screen; what moves the phone answers here."""

        #: Instagram refuses the next write ("Try again later").
        blocked = False

        def _optimize_locale(self):
            return None

        def ensure_notifications_screen(self):
            return True

        def ensure_follow_requests_screen(self):
            return True

        def _return_to_notifications(self):
            return None

        def _dump_root(self):
            return screen

        def _expand_one_more(self):
            return False

        def _resolve_emoji_text(self, parsed_text):
            return None

        def _scroll_down(self, times=1):
            return None

        def _human_scroll(self, direction):
            return False

        def _tap_show_more(self):
            return False

        def _element_exists(self, selectors):
            return True

        def _request_rows(self):
            return [dict(row) for row in requests]

        def _block_detector(self):
            return SimpleNamespace(is_action_blocked=lambda: True) if Scripted.blocked else None

        def _open_reply_thread(self, username):
            return True

        def _on_comment_thread(self):
            return True

        def _find_element(self, selectors):
            return _Composer()

        def _type_into(self, field, text):
            return True

        def refresh_notifications_screen(self):
            return True

        def reach_suggestions_zone(self, max_scrolls=60):
            return True

        def scan_suggestions(self, root=None):
            return [dict(row) for row in suggestions]

        def open_suggestion_profile(self, row, load_timeout_s=8.0):
            return True

        def leave_suggestion_profile(self):
            return True

    return Scripted


class _Pipeline:
    """The per-profile pipeline's answer: its own lines belong to the automation's contract."""

    def __init__(self):
        self.read = iter(("suggested_one", None))

    def read_username(self):
        return next(self.read, None)

    def process(self, username):
        from taktik.core.social_media.instagram.actions.core.base_business.profile_processing import (
            ProfileProcessingResult,
        )

        outcome = ProfileProcessingResult(ProfileProcessingResult.SUCCESS, username)
        outcome.interaction_result = {"follows": 1}
        return outcome


@pytest.fixture
def notifications_bridge(monkeypatch):
    import importlib

    import bridges.common.device.connection as connection
    import bridges.instagram.engagement.runtime.notifications.commands as bridge
    from taktik.core.shared.device.ui_dump import parse_ui_dump

    commands = importlib.import_module(f"{_MODULE}.commands")
    workflow_module = importlib.import_module(f"{_MODULE}.notifications_workflow")
    screen = parse_ui_dump(_SCREEN.read_text(encoding="utf-8"))

    class Runtime(bridge.NotificationsBridge):
        """The bridge's runtime, connected to a phone that answers nothing."""

        fail = False

        def connect(self):
            self.device = _Phone()
            return not Runtime.fail

        def restart_instagram(self):
            return None

        def stop(self):
            return True

    monkeypatch.setattr(connection, "ConnectionService", lambda device_id: SimpleNamespace())
    monkeypatch.setattr(bridge, "NotificationsBridge", Runtime)
    workflow = _workflow_class(screen)
    monkeypatch.setattr(commands, "NotificationsEngagementWorkflow", workflow)
    monkeypatch.setattr(commands, "build_notifications_profile_pipeline", lambda device, **kwargs: _Pipeline())
    monkeypatch.setattr(workflow_module, "ensure_taktik_keyboard", lambda device_id: None)
    monkeypatch.setattr(workflow_module, "tap_element_human", lambda device, element: True)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)

    @contextlib.contextmanager
    def session(account_id, source):
        yield 11

    for name, value in (("witness_for", None), ("build_known_checker", None), ("record_notification_action", None),
                        ("count_actions_today", 1), ("load_actioned_hashes", {"hash-done"}),
                        ("resolve_account_id", 7), ("record_welcome_dm", None), ("welcome_dm_skip_reason", None)):
        monkeypatch.setattr(commands, name, lambda *args, _value=value, **kwargs: _value)
    monkeypatch.setattr(commands, "record_scan_notifications",
                        lambda account, items: [index % 2 == 0 for index, _ in enumerate(items)])
    monkeypatch.setattr(commands, "batch_identity_hash",
                        lambda account, identity: f"hash-{identity['text']}" if identity else None)
    monkeypatch.setattr(commands, "suggestion_session", session)
    monkeypatch.setattr(commands, "send_welcome_dm",
                        lambda device, username, text: {"success": True, "message": f"welcome DM sent to @{username}"})
    monkeypatch.setattr(commands, "follow_actor", lambda device, username: {
        "success": True, "skipped": True, "reason": "following", "state": "following",
        "message": f"@{username} - already in a relationship"})
    monkeypatch.setattr(commands, "wait_before_next_off_screen_action", lambda *, is_last: None)

    class Profile:
        def __init__(self, device):
            pass

        def get_complete_profile_info(self, username=None, navigate_if_needed=True):
            return {"username": "acting", "followers_count": 12}

    class Navigation:
        def __init__(self, device):
            pass

        def navigate_to_home(self):
            return None

    monkeypatch.setattr("taktik.core.social_media.instagram.actions.business.management.profile.ProfileBusiness", Profile)
    monkeypatch.setattr("taktik.core.social_media.instagram.actions.atomic.navigation.NavigationActions", Navigation)
    monkeypatch.setattr(bridge, "Runtime", Runtime, raising=False)
    monkeypatch.setattr(bridge, "Workflow", workflow, raising=False)
    return bridge


#: A batch that walks each verb and each guard: done, failed, skipped as already done, over its cap,
#: skipped by the verb itself.
_BATCH = [
    {"action": "follow_actor", "username": "engaged_one"},
    {"action": "welcome_dm", "username": "new_fan", "text": "Welcome!"},
    {"action": "like", "username": "user_3", "notif_type": "comment_mention", "notif_text": "fresh", "notif_time": "2h"},
    {"action": "like", "username": "user_4", "notif_type": "comment_mention", "notif_text": "done", "notif_time": "3h"},
    {"action": "reply", "username": "user_3", "text": "Thanks a lot"},
    {"action": "follow_back", "username": "user_9"},
    {"action": "accept", "username": "user_20"},
    {"action": "ignore", "username": "nobody_there"},
]

#: The choices the app's file is written for, command by command.
_RUNS = {
    "scan": {"followSuggestions": 2, "accountUsername": "acting"},
    "list_requests": {},
    "accept_all": {"accountUsername": "acting"},
    "reply": {"username": "user_3", "text": "Thanks", "accountUsername": "acting"},
    "batch": {"actions": _BATCH, "source": "autopilot", "followBackDailyCap": 1, "welcomeDmDailyCap": 5,
              "followActorDailyCap": 3, "accountUsername": "acting"},
    "accept": {"username": "user_20", "accountUsername": "acting"},
    "ignore": {"username": "user_21", "accountUsername": "acting"},
    "like": {"username": "user_3", "accountUsername": "acting"},
    "follow_back": {"username": "user_9", "accountUsername": "acting"},
}


def _run(bridge, data: Dict[str, Any], log: set) -> int:
    return bridge.NotificationsCommand(Recording(data, log)).run()


@pytest.mark.parametrize("command", COMMANDS)
def test_the_notifications_bridge_follows_its_contract(notifications_bridge, printed, command):
    data = app_file(INSTAGRAM_NOTIFICATIONS, command=command, **_RUNS[command])
    log: set = set()

    assert _run(notifications_bridge, data, log) == 0

    assert_reads(INSTAGRAM_NOTIFICATIONS, data, log)
    lines = printed()
    check_lines(INSTAGRAM_NOTIFICATIONS, lines)
    assert lines[-1]["type"] == "result" and lines[-1]["command"] == command
    if command != "list_requests":
        assert any(line["type"] == "notification_step" for line in lines)


def test_every_declared_line_and_field_comes_out_of_a_real_run(notifications_bridge, printed, monkeypatch):
    seen: List[Dict[str, Any]] = []
    for command in COMMANDS:
        _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command=command, **_RUNS[command]), set())
        seen += printed()
    # Instagram refuses the like; a verb without its row is refused before the phone.
    monkeypatch.setattr(notifications_bridge.Workflow, "blocked", True)
    _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="accept", **_RUNS["accept"]), set())
    refused = app_file(INSTAGRAM_NOTIFICATIONS, command="like", accountUsername="acting")
    refused.pop("username")
    with pytest.raises(SystemExit):
        _run(notifications_bridge, refused, set())
    seen += printed()

    check_lines(INSTAGRAM_NOTIFICATIONS, seen)
    assert {line["type"] for line in seen} == {event.type for event in INSTAGRAM_NOTIFICATIONS.events}
    for event in INSTAGRAM_NOTIFICATIONS.events:
        printed_fields = {key for line in seen if line["type"] == event.type for key in line} - {"type"}
        # `traceback` is a crash's: `test_a_crash_is_said_in_the_last_line`.
        assert printed_fields | {"traceback"} >= {item.key for item in event.fields}, event.type


def test_a_scan_reads_the_rows_of_the_screen(notifications_bridge, printed):
    _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="scan", **_RUNS["scan"]), set())

    result = printed()[-1]
    assert result["success"] is True and result["count"] == len(result["items"]) > 0
    assert {item["type"] for item in result["items"]} >= {"new_follower", "comment_mention"}
    assert result["suggestions"]["follows"] == 1 and result["suggestions"]["profiles"][1]["username"] is None


@pytest.mark.parametrize("command", ("like", "reply", "accept", "ignore", "follow_back"))
def test_a_row_verb_without_its_row_is_refused_in_its_last_line(notifications_bridge, printed, command):
    data = app_file(INSTAGRAM_NOTIFICATIONS, command=command, accountUsername="acting")
    data.pop("username", None)

    with pytest.raises(SystemExit):
        _run(notifications_bridge, data, set())

    lines = printed()
    check_lines(INSTAGRAM_NOTIFICATIONS, lines)
    assert [line["type"] for line in lines] == ["result"]
    assert lines[0]["success"] is False and "username is required" in lines[0]["error"]


def test_a_phone_that_does_not_connect_is_said_in_the_last_line(notifications_bridge, printed, monkeypatch):
    monkeypatch.setattr(notifications_bridge.Runtime, "fail", True)

    with pytest.raises(SystemExit):
        _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="like", **_RUNS["like"]), set())

    lines = printed()
    check_lines(INSTAGRAM_NOTIFICATIONS, lines)
    assert [line["type"] for line in lines] == ["result"]
    assert lines[0]["error"] == "Failed to connect to device"


def test_a_crash_is_said_in_the_last_line(notifications_bridge, printed, monkeypatch):
    import importlib

    commands = importlib.import_module(f"{_MODULE}.commands")

    def broken(*args, **kwargs):
        raise RuntimeError("list broke")

    monkeypatch.setattr(commands, "cmd_list_requests", broken)

    with pytest.raises(SystemExit):
        _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="list_requests"), set())

    lines = printed()
    check_lines(INSTAGRAM_NOTIFICATIONS, lines)
    assert lines[-1]["type"] == "result" and lines[-1]["error"] == "list broke" and "traceback" in lines[-1]


def test_an_unreadable_file_is_said_in_a_result_line(printed, tmp_path, monkeypatch):
    import sys

    from bridges.instagram.engagement import notifications

    monkeypatch.setattr(sys, "argv", ["notifications_bridge", str(tmp_path / "missing.json")])
    with pytest.raises(SystemExit):
        notifications.main()

    lines = printed()
    check_lines(INSTAGRAM_NOTIFICATIONS, lines)
    assert [line["type"] for line in lines] == ["result"] and lines[0]["success"] is False
