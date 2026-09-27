"""The notifications bridge reads the file the contract describes and prints the lines it declares.

As for the other Instagram bridges (`test_workflow_contract_instagram_bridges.py`): the whole bridge
runs, from its config file to its stdout, on the app's file, one run per command. The production
workflow reads a real activity screen (`ig410_en_notifications.xml`, anonymized); the suggestions
visit walks the real per-profile pipeline (`build_notifications_profile_pipeline`) on a real, empty
base. Only what the phone reads and moves, the notifications' own records and the AI's HTTP transport
answer here. The lines are printed by the production emitters (the workflow's narration, the batch,
the shared suggestions visit, the automation's per-profile pipeline and AI service, the command
results, the bridge's refusals), not written by the test.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from contract_probe import Recording
from ig_automation_probe import protect_hooks
from taktik.core.app.contract.instagram_notifications import (
    BATCH_VERBS,
    COMMANDS,
    INSTAGRAM_NOTIFICATIONS,
    NOTIFICATION_STEP_EVENT,
    NOTIFICATION_TYPES,
    RESULT_EVENT,
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


#: The suggestion rows at the bottom of the activity screen (their height), and the profile each one
#: opens: a public account, a second one, a private one, one whose handle cannot be read.
_SUGGESTION_ROWS = (
    (1500, "Name One", "suggested_one"),
    (1700, "Name Two", "suggested_two"),
    (1900, "Name Three", "suggested_private"),
    (2100, "Name Four", None),
)
#: The account on the phone.
_OWN = "acting"
#: The profile the phone shows.
_SHOWN = {"username": _OWN}


class _Phone:
    """A tap on a suggestion row opens its profile; the other taps land nowhere."""

    def long_click(self, x, y, duration=None):
        self.click(x, y)

    def click(self, x, y):
        for row_y, _label, username in _SUGGESTION_ROWS:
            if abs(y - row_y) < 50:
                _SHOWN["username"] = username

    def screenshot(self):
        from PIL import Image

        return Image.new("RGB", (8, 8))


def _workflow_class(screen):
    from taktik.core.social_media.instagram.workflows.management.notifications.notifications_workflow import (
        NotificationsEngagementWorkflow,
    )

    requests = [{"username": "user_20", "accept": (646, 486), "ignore": (908, 486)},
                {"username": "user_21", "accept": (646, 689), "ignore": (908, 689)}]
    suggestions = [{"label": label, "state": "follow", "follow_point": (900, y), "row_point": (400, y)}
                   for y, label, _username in _SUGGESTION_ROWS]

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

        def leave_suggestion_profile(self):
            return True

    return Scripted


def _script_the_profile_screen(monkeypatch) -> None:
    """What the phone reads on the profile it shows answers from a script; the per-profile pipeline
    around it is production's (`build_notifications_profile_pipeline`: extraction, filters, plan,
    follow, base), and so is the reading of our own profile before the feed."""
    from taktik.core.social_media.instagram.actions.atomic.detection.profile_extraction import (
        ProfileExtractionMixin,
    )
    from taktik.core.social_media.instagram.actions.atomic.detection.screen_detection import ScreenDetectionMixin
    from taktik.core.social_media.instagram.actions.atomic.interaction.profile_interaction import (
        ProfileInteractionMixin,
    )
    from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
    from taktik.core.social_media.instagram.actions.business.management.profile.extraction import ProfileExtraction
    from taktik.core.social_media.instagram.actions.core.base_business import interaction_engine
    from taktik.core.social_media.instagram.actions.core.base_business.modal_recovery import ModalRecoveryMixin
    from taktik.core.social_media.instagram.actions.core.base_business.popup_handling import PopupHandlingMixin

    shown = _SHOWN

    def own_profile(self, *args, **kwargs):
        shown["username"] = _OWN
        return True

    screen = {
        (ScreenDetectionMixin, "wait_for_profile_screen"): lambda self, timeout=8.0, interval=0.4: True,
        (ScreenDetectionMixin, "is_on_profile_screen"): lambda self, *args, **kwargs: True,
        (NavigationActions, "navigate_to_profile_tab"): own_profile,
        (ProfileExtractionMixin, "extract_own_avatar_from_tab"): lambda self, xml_content=None: None,
        (ProfileExtractionMixin, "get_username_from_profile"): lambda self: shown["username"],
        (ProfileExtractionMixin, "get_profile_flags_batch"): lambda self: {
            "is_private": shown["username"] == "suggested_private", "is_verified": False, "is_business": False},
        (ProfileExtractionMixin, "get_enriched_profile_data"): lambda self, **kwargs: {
            "username": shown["username"], "full_name": "A Name", "biography": "yoga", "bio_truncated": False},
        (ProfileExtractionMixin, "extract_profile_image"): lambda self, xml_content=None: "data:image/jpeg;base64,AAAA",
        (ProfileExtraction, "_get_followers_count_robust"): lambda self, swipe_up_if_needed=False: 120,
        (ProfileExtraction, "_get_following_count_robust"): lambda self, swipe_up_if_needed=False: 80,
        (ProfileExtraction, "_get_posts_count_robust"): lambda self, swipe_up_if_needed=False: 30,
        (ProfileInteractionMixin, "get_follow_button_state"): lambda self: "follow",
        (ProfileInteractionMixin, "follow_user"): lambda self, username: True,
        (ModalRecoveryMixin, "_recover_from_blocking_modal"): lambda self, username="", context="": None,
        (PopupHandlingMixin, "_handle_follow_suggestions_popup"): lambda self: False,
    }
    for (owner, name), answer in screen.items():
        monkeypatch.setattr(owner, name, answer)
    # After the follow, one look for "Try again later": the screen shows none.
    monkeypatch.setattr(interaction_engine, "look_for_action_block", lambda *args, **kwargs: False)


@pytest.fixture
def notifications_bridge(monkeypatch, tmp_path):
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
    _script_the_profile_screen(monkeypatch)
    monkeypatch.setitem(_SHOWN, "username", _OWN)
    # The AI hooks of a run with an `ai` block patch the interaction engine: put back afterwards.
    protect_hooks(monkeypatch)
    # A real, empty base for what the visit writes (profiles, filtered profiles, AI cache).
    import sqlite3

    import taktik.core.database as database

    database_file = tmp_path / "notifications.db"
    sqlite3.connect(database_file).close()
    monkeypatch.setenv("TAKTIK_DB_PATH", str(database_file))
    monkeypatch.setattr(database, "db_service", None)
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

    class Navigation:
        def __init__(self, device):
            pass

        def navigate_to_home(self):
            return None

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
    "scan": {"followSuggestions": len(_SUGGESTION_ROWS), "accountUsername": "acting"},
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


def _cli_scan_with_ai(bridge, monkeypatch) -> None:
    """A scan whose file carries an `ai` block, as the CLI may pass it (the app sends none): the real
    AI service qualifies the visited profiles, its HTTP transport answering from a script, the first
    call answered, the second refused."""
    from test_workflow_contract_bridges import assert_reads as assert_reads_up_to_json
    from test_workflow_contract_instagram_automation_lines import _MODEL_ANSWER, _openrouter

    monkeypatch.setattr("urllib.request.urlopen", _openrouter([_MODEL_ANSWER, "fail", "fail", "fail"]))
    data = app_file(INSTAGRAM_NOTIFICATIONS, command="scan", **_RUNS["scan"])
    data.update(ai={"enabled": True, "profileAnalysis": True, "openrouterApiKey": "sk-probe-key-long-enough"},
                language="fr")
    log: set = set()

    assert _run(bridge, data, log) == 0

    # Below `ai`, declared as an object read whole, what is read is the AI service's business.
    assert_reads_up_to_json(INSTAGRAM_NOTIFICATIONS, data, log)


def test_a_scan_that_visits_suggestions_prints_the_automation_s_lines(notifications_bridge, printed, monkeypatch):
    _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="scan", **_RUNS["scan"]), set())
    lines = printed()
    _cli_scan_with_ai(notifications_bridge, monkeypatch)
    with_ai = printed()

    check_lines(INSTAGRAM_NOTIFICATIONS, lines + with_ai)
    visited = [line["username"] for line in lines if line["type"] == "instagram_profile_visit"]
    assert visited == ["suggested_one", "suggested_two", "suggested_private"]
    assert {line["username"] for line in lines if line["type"] == "profile_captured"} == {_OWN, *visited}
    assert [line["username"] for line in lines if line["type"] == "active_account"] == [_OWN]
    actions = {(line["action"], line["username"]) for line in lines if line["type"] == "instagram_action"}
    assert ("private", "suggested_private") in actions and ("plan", "suggested_one") in actions
    # Without an `ai` block nothing is qualified; with one, each public profile is, and a refused call
    # is said.
    assert not any(line["type"].startswith("ai_") for line in lines)
    assert {line["type"] for line in with_ai} >= {"ai_profile_start", "ai_profile_done", "ai_error"}


def test_a_scan_without_suggestions_opens_no_profile(notifications_bridge, printed):
    """`followSuggestions` governs the visit: 0 (the default) opens no suggested profile."""
    _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="scan", accountUsername="acting"), set())
    lines = printed()

    check_lines(INSTAGRAM_NOTIFICATIONS, lines)
    assert not any(line["type"] in ("instagram_profile_visit", "instagram_action") for line in lines)
    assert lines[-1]["suggestions"]["stop_reason"] == "disabled"


def test_the_visit_opens_no_more_profiles_than_followsuggestions(notifications_bridge, printed):
    _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="scan", followSuggestions=2,
                                        accountUsername="acting"), set())
    lines = printed()

    visited = [line["username"] for line in lines if line["type"] == "instagram_profile_visit"]
    assert visited == ["suggested_one", "suggested_two"]
    assert lines[-1]["suggestions"]["visited"] == 2


def test_a_suggestion_visit_follows_the_account_it_qualified(notifications_bridge, printed):
    _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="scan", **_RUNS["scan"]), set())

    assert printed()[-1]["suggestions"]["follows"] >= 1


def test_every_declared_line_and_field_comes_out_of_a_real_run(notifications_bridge, printed, monkeypatch):
    seen: List[Dict[str, Any]] = []
    for command in COMMANDS:
        _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command=command, **_RUNS[command]), set())
        seen += printed()
    _cli_scan_with_ai(notifications_bridge, monkeypatch)
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
    # The automation's lines are that contract's, each field held by its own tests; this bridge prints
    # the part of them its run reaches.
    for event in (NOTIFICATION_STEP_EVENT, RESULT_EVENT):
        printed_fields = {key for line in seen if line["type"] == event.type for key in line} - {"type"}
        # `traceback` is a crash's: `test_a_crash_is_said_in_the_last_line`.
        assert printed_fields | {"traceback"} >= {item.key for item in event.fields}, event.type


def test_a_scan_reads_the_rows_of_the_screen(notifications_bridge, printed):
    _run(notifications_bridge, app_file(INSTAGRAM_NOTIFICATIONS, command="scan", **_RUNS["scan"]), set())

    result = printed()[-1]
    assert result["success"] is True and result["count"] == len(result["items"]) > 0
    assert {item["type"] for item in result["items"]} >= {"new_follower", "comment_mention"}
    visit = result["suggestions"]
    assert visit["visited"] == len(_SUGGESTION_ROWS) and visit["processed"] == 3
    assert [profile["status"] for profile in visit["profiles"]] == [
        "interacted", "interacted", "filtered_private", "no_username"]


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

