"""A recording bridge for the Instagram notifications one-path tests.

The desktop starts `notifications_bridge` for nine commands (scan, list_requests, accept, ignore,
accept_all, reply, like, follow_back, batch). The bridge's device, the notifications workflow and
the database helpers are fakes that record what they are asked; the command code runs for real
(the bridge's entry, then `run_instagram_notifications` in the core): which command runs, with
which values, what is recorded, what is printed, the exit code. The workflow and the per-profile
pipeline are built by the core launcher now; their fakes keep the labels the sequence was frozen
with (`bridge build_workflow`, `bridge build_profile_pipeline`), so the snapshot is unchanged.
Nothing here reaches adb or the database.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys

DEVICE_ID = "emulator-5554"
CLONE = "com.instagram.android.clone"
BOT = "alpha_bot"

_COMMANDS = "bridges.instagram.engagement.runtime.notifications.commands"
_CORE_COMMANDS = "taktik.core.social_media.instagram.workflows.management.notifications.commands"


def notif_command(command: str, **fields) -> dict:
    """What the desktop asks the notifications bridge for, as its config file carries it."""
    spec = {"command": command, "deviceId": DEVICE_ID}
    spec.update(fields)
    return spec


def _legacy_argv(spec: dict) -> list[str]:
    """The positional arguments the desktop used to build for `spec`, flag for flag."""
    command = spec["command"]
    device_id = spec["deviceId"]
    if command == "scan":
        argv = ["scan", device_id, str(spec.get("scroll", 3))]
    elif command == "list_requests":
        argv = ["list_requests", device_id, str(spec.get("limit", 50))]
    elif command == "accept_all":
        argv = ["accept_all", device_id, str(spec.get("max", 50))]
    elif command == "reply":
        argv = ["reply", device_id, spec["username"], spec.get("text", "")]
    elif command == "batch":
        argv = ["batch", device_id, json.dumps(spec["actions"])]
    else:
        argv = [command, device_id, spec["username"]]
    if spec.get("accountUsername"):
        argv += ["--account", spec["accountUsername"]]
    if spec.get("source"):
        argv += ["--source", spec["source"]]
    for key, flag in (("followBackDailyCap", "--follow-back-daily-cap"),
                      ("welcomeDmDailyCap", "--welcome-dm-daily-cap"),
                      ("followActorDailyCap", "--follow-actor-daily-cap")):
        if spec.get(key) is not None:
            argv += [flag, str(spec[key])]
    if spec.get("packageName"):
        argv += ["--package", spec["packageName"]]
    if spec.get("followSuggestions"):
        argv += ["--follow-suggestions", str(spec["followSuggestions"])]
    if spec.get("ai") is not None:
        argv += ["--ai-config", json.dumps(spec["ai"])]
    if spec.get("language"):
        argv += ["--language", spec["language"]]
    return argv


class _Workflow:
    def __init__(self, rig):
        self.rig = rig
        self.profile_pipeline = None

    def _call(self, name, *args, **kwargs):
        self.rig.record("workflow", name, *args, **kwargs)
        if self.rig.raise_on == name:
            raise RuntimeError(f"{name} broke")
        return dict(self.rig.results.get(name, {"success": True}))

    def scan(self, *, max_scrolls, known_checker=None):
        self.rig.record("workflow", "scan", max_scrolls=max_scrolls, known_checker=known_checker)
        if self.rig.raise_on == "scan":
            raise RuntimeError("scan broke")
        return {"success": True, "count": len(self.rig.items), "by_type": {"like": len(self.rig.items)},
                "items": [dict(item) for item in self.rig.items], "requests": ["req_one"],
                "has_grouped_requests": False, "message": "read"}

    def list_requests(self, *, max_requests):
        return self._call("list_requests", max_requests=max_requests)

    def accept_request(self, username):
        return self._call("accept_request", username)

    def ignore_request(self, username):
        return self._call("ignore_request", username)

    def accept_all_requests(self, *, max_requests):
        return self._call("accept_all_requests", max_requests=max_requests)

    def reply_to_comment(self, username, text):
        return self._call("reply_to_comment", username, text)

    def like_comment(self, username):
        result = self._call("like_comment", username)
        if username in self.rig.block_after:
            from taktik.core.shared.diagnostics import run_halt

            run_halt.demander_arret("action_blocked", "Try again later")
        return result

    def follow_back(self, username):
        return self._call("follow_back", username)

    def visit_suggestions(self, *, max_profiles):
        self.rig.record("workflow", "visit_suggestions", max_profiles=max_profiles)
        return {"visited": 1, "processed": 1, "follows": 1, "filtered": 0, "errors": 0,
                "profiles": ["suggested_one"], "stop_reason": "budget"}


class _Bridge:
    def __init__(self, rig, device_id, package_name=None):
        self.rig = rig
        self.device_id = device_id
        self.device = "device"
        rig.record("bridge", "init", device_id, package_name=package_name)

    def connect(self):
        self.rig.record("bridge", "connect")
        return self.rig.connect_ok

    def restart_instagram(self):
        self.rig.record("bridge", "restart_instagram")

    def stop(self):
        self.rig.record("bridge", "stop")
        return True


class InstagramNotificationsRig:
    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        self.tmp_path = tmp_path
        self.calls: list = []
        self.stdout_lines: list = []
        self.connect_ok = True
        self.raise_on = None
        self.items = [{"type": "like", "actor": "fan_one", "text": "liked your post"},
                      {"type": "comment", "actor": "fan_two", "text": "nice"}]
        self.results: dict = {}
        #: Usernames whose like makes Instagram refuse actions.
        self.block_after: set = set()
        self.own_profile = {"username": BOT, "followers_count": 12}
        self._install()

    def record(self, *parts, **kwargs):
        entry = [str(part) for part in parts]
        if kwargs:
            entry.append(json.dumps(kwargs, sort_keys=True, default=str))
        self.calls.append(" ".join(entry))

    def _install(self):
        import importlib

        from taktik.core.shared.diagnostics import run_halt

        bridge_commands = importlib.import_module(_COMMANDS)
        commands = importlib.import_module(_CORE_COMMANDS)
        rig = self
        run_halt.reinitialiser()
        self.monkeypatch.setattr(run_halt, "_temoin", None)
        self.monkeypatch.setattr(run_halt, "_arret", None)

        self.monkeypatch.setattr(bridge_commands, "NotificationsBridge",
                                 lambda device_id, package_name=None: _Bridge(rig, device_id, package_name))

        def build_workflow(device, device_id, **_kwargs):
            rig.record("bridge", "build_workflow")
            return _Workflow(rig)

        def build_profile_pipeline(device, *, account_id, **kwargs):
            rig.record("bridge", "build_profile_pipeline", account_id=account_id, **kwargs)
            return "pipeline"

        self.monkeypatch.setattr(commands, "NotificationsEngagementWorkflow", build_workflow)
        self.monkeypatch.setattr(commands, "build_notifications_profile_pipeline", build_profile_pipeline)

        def recorder(name, value=None):
            def fn(*args, **kwargs):
                rig.record("db", name, *args, **kwargs)
                return value(*args, **kwargs) if callable(value) else value
            return fn

        def witness_for(platform, account, *, source_type=lambda: None, **_kwargs):
            rig.record("db", "witness_for", platform, account(), source_type=source_type())
            return "witness"

        self.monkeypatch.setattr(commands, "witness_for", witness_for)
        self.monkeypatch.setattr(commands, "build_known_checker", recorder("build_known_checker", "known"))
        self.monkeypatch.setattr(commands, "record_scan_notifications",
                                 recorder("record_scan_notifications",
                                          lambda account, items: [index == 0 for index, _ in enumerate(items)]))
        self.monkeypatch.setattr(commands, "record_notification_action", recorder("record_notification_action"))
        self.monkeypatch.setattr(commands, "count_actions_today", recorder("count_actions_today", 1))
        self.monkeypatch.setattr(commands, "load_actioned_hashes",
                                 recorder("load_actioned_hashes", lambda account, verb: {"hash-done"}))
        self.monkeypatch.setattr(commands, "batch_identity_hash",
                                 recorder("batch_identity_hash",
                                          lambda account, identity: (f"hash-{identity['text']}"
                                                                     if account and identity else None)))
        self.monkeypatch.setattr(commands, "resolve_account_id",
                                 recorder("resolve_account_id", lambda username: 7 if username else None))
        self.monkeypatch.setattr(commands, "record_welcome_dm", recorder("record_welcome_dm"))
        self.monkeypatch.setattr(commands, "welcome_dm_skip_reason",
                                 recorder("welcome_dm_skip_reason",
                                          lambda account_id, username: "already_dmed" if username == "old_friend" else None))
        self.monkeypatch.setattr(commands, "send_welcome_dm",
                                 lambda device, username, text: (rig.record("screen", "send_welcome_dm", username, text)
                                                                 or {"success": True}))
        self.monkeypatch.setattr(commands, "follow_actor",
                                 lambda device, username: (rig.record("screen", "follow_actor", username)
                                                           or {"success": True, "skipped": username == "already_followed"}))
        self.monkeypatch.setattr(commands, "wait_before_next_off_screen_action",
                                 lambda *, is_last: rig.record("pace", is_last=is_last))
        self.monkeypatch.setattr(commands, "install_notifications_ai_hooks",
                                 lambda *, ai_config, device, language, **_kwargs: (
                                     rig.record("ai", "install", ai=ai_config, language=language)
                                     or bool(ai_config)))

        @contextlib.contextmanager
        def session(account_id, source):
            rig.record("db", "suggestion_session", account_id, source=source)
            yield "session-1"

        self.monkeypatch.setattr(commands, "suggestion_session", session)

        class _Profile:
            def __init__(self, device):
                pass

            def get_complete_profile_info(self, username=None, navigate_if_needed=True):
                rig.record("screen", "own_profile")
                return dict(rig.own_profile) if rig.own_profile else None

        class _Navigation:
            def __init__(self, device):
                pass

            def navigate_to_home(self):
                rig.record("screen", "home")

        self.monkeypatch.setattr(
            "taktik.core.social_media.instagram.actions.business.management.profile.ProfileBusiness", _Profile)
        self.monkeypatch.setattr(
            "taktik.core.social_media.instagram.actions.atomic.navigation.NavigationActions", _Navigation)

    def _config_file_bridge(self) -> bool:
        import importlib

        return hasattr(importlib.import_module(_COMMANDS), "load_notifications_bridge_config")

    def bridge_argv(self, spec: dict) -> list[str]:
        """How the desktop starts the bridge for `spec`: a config file, or (before) positional args."""
        if self._config_file_bridge():
            config_path = self.tmp_path / "notifications_config.json"
            config_path.write_text(json.dumps(spec), encoding="utf-8")
            return ["notifications_bridge", str(config_path)]
        return ["notifications_bridge", *_legacy_argv(spec)]

    def run_bridge(self, spec: dict | None = None, argv: list[str] | None = None) -> int:
        """The desktop path, to its exit code."""
        self.monkeypatch.setattr(sys, "argv", argv if argv is not None else self.bridge_argv(spec))

        from bridges.instagram.engagement import notifications

        out = io.StringIO()
        self.monkeypatch.setattr(sys, "stdout", out)
        code = 0
        try:
            notifications.main()
        except SystemExit as exit_info:
            code = exit_info.code if isinstance(exit_info.code, int) else (0 if exit_info.code is None else 1)
        finally:
            self.monkeypatch.setattr(sys, "stdout", sys.__stdout__)
        for line in out.getvalue().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                self.stdout_lines.append(line)
                continue
            if isinstance(parsed, dict) and "traceback" in parsed:
                parsed["traceback"] = "<traceback>"
            self.stdout_lines.append(parsed)
        return code
