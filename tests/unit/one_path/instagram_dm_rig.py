"""A recording phone for the Instagram DM one-path tests.

The same DM command goes through the desktop bridge (`dm_bridge`) and through the CLI
(`taktik workflows run instagram.engagement.dm_read` / `dm_send`). The inbox rows, the header, the
conversation screen and the database are fakes; the orchestration of a read or a send, the inbox
reader's loop, the persistence of what was read and sent, and the way back to the inbox run for
real. The deep screen helpers (inbox tab, primary tab, message extraction, composer) are recorded
stand-ins: they are covered by their own tests. Nothing here reaches adb or the database.
"""
from __future__ import annotations

import io
import json
import re
import sys

DEVICE_ID = "emulator-5554"
INSTAGRAM = "com.instagram.android"
CLONE = "com.instagram.android.clone"
BOT = "alpha_bot"

# Where the moved modules live, before and after: the rig patches whichever exists.
_DM_MODULES = ("bridges.instagram.engagement.runtime.dm", "taktik.core.social_media.instagram.workflows.dm_inbox")


def dm_command(command: str, **fields) -> dict:
    """What the desktop asks the DM bridge for: a read, a read of the requests, or a send."""
    spec = {"command": command, "deviceId": DEVICE_ID}
    if command in ("read", "read_requests"):
        spec["limit"] = 5
    spec.update(fields)
    return spec


def _suffix(resource_id: str) -> str:
    return resource_id.split(":id/")[-1]


def _key(selector: dict) -> tuple:
    if "resourceIdMatches" in selector:
        match = re.search(r"([A-Za-z0-9_]+)\$?$", selector["resourceIdMatches"].rstrip("$"))
        return ("id", match.group(1) if match else selector["resourceIdMatches"])
    if "resourceId" in selector:
        return ("id", _suffix(selector["resourceId"]))
    for name, kind in (("text", "text"), ("description", "desc"), ("className", "class")):
        if name in selector:
            return (kind, selector[name])
    return ("other", json.dumps(selector, sort_keys=True))


class _Exists:
    """uiautomator2's `exists`: a truthy value that can also be called with a timeout."""

    def __init__(self, element):
        self.element = element

    def _value(self):
        found = self.element.phone.shows(self.element.key)
        if found:
            self.element.phone.rig.calls.append(f"found {self.element.key[0]}:{self.element.key[1]}")
        return found

    def __bool__(self):
        return self._value()

    def __call__(self, timeout=None):
        return self._value()


class _Element:
    def __init__(self, phone, key):
        self.phone = phone
        self.key = key

    @property
    def exists(self):
        return _Exists(self)

    def get_text(self):
        return self.phone.text_of(self.key)

    def click(self):
        self.phone.rig.calls.append(f"click {self.key[0]}:{self.key[1]}")
        self.phone.clicked(self.key)

    @property
    def info(self):
        return {"text": self.phone.text_of(self.key)}


class _Row:
    def __init__(self, phone, username, content_desc, top):
        self.phone = phone
        self.username = username
        self.info = {"contentDescription": content_desc, "bounds": {"top": top, "left": 0, "right": 1080,
                                                                     "bottom": top + 150}}

    def click(self):
        self.phone.rig.calls.append(f"click row {self.username}")
        self.phone.open(self.username)


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return list(self.rows)


class FakePhone:
    """Instagram's DM inbox, as far as the DM commands look at it."""

    def __init__(self, rig):
        from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS

        self.rig = rig
        self.screen = "home"
        self.open_title = None
        self.ids = {
            "inbox_title": _suffix(DM_SELECTORS.inbox_title_resource_id),
            "inbox_list": _suffix(DM_SELECTORS.inbox_thread_list_resource_id),
            "header": _suffix(DM_SELECTORS.conversation_header_title_resource_id),
            "back": _suffix(DM_SELECTORS.conversation_back_button_resource_id),
            "probes": [_suffix(rid) for rid in DM_SELECTORS.instagram_open_probe_resource_ids],
        }

    def __call__(self, **selector):
        return _Element(self, _key(selector))

    def xpath(self, selector):
        if "row_inbox_container" in selector and self.screen == "inbox":
            return _Rows([_Row(self, *row, 300 + 200 * i) for i, row in enumerate(self.rig.rows)])
        return _Rows([])

    def press(self, button):
        self.rig.calls.append(f"press {button}")
        if button == "back" and self.screen == "conversation":
            self.screen = "inbox"

    # --- what the screen shows ------------------------------------------------------------------

    def shows(self, key) -> bool:
        kind, value = key
        ids = self.ids
        if key == ("id", ids["inbox_title"]):
            return self.screen == "inbox" and self.rig.header_readable
        if key == ("id", ids["inbox_list"]):
            return self.screen == "inbox"
        if key == ("id", ids["header"]):
            return self.screen == "conversation"
        if key == ("id", ids["back"]):
            return self.screen == "conversation"
        if kind == "id" and value in ids["probes"]:
            return self.screen in ("home", "inbox") and self.rig.instagram_open
        return False

    def text_of(self, key) -> str:
        if key == ("id", self.ids["inbox_title"]):
            return BOT
        if key == ("id", self.ids["header"]):
            return self.open_title or ""
        return ""

    # --- what a gesture does --------------------------------------------------------------------

    def clicked(self, key) -> None:
        if key == ("id", self.ids["back"]):
            self.screen = "inbox"

    def open(self, username) -> None:
        self.screen = "conversation"
        self.open_title = username


class InstagramDmRig:
    DEVICE_ID = DEVICE_ID

    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        self.tmp_path = tmp_path
        self.calls: list[str] = []
        self.stdout_lines: list = []
        self.db: list[dict] = []
        self.cli_results: list = []
        # (username, content-desc of its inbox row): answered, up to date, to open.
        self.rows = [
            ("bob", "bob, Sent 2m"),
            ("carol", "carol, See you at the tasting tomorrow · 3m"),
            ("dave", "dave, Is the shop open on sunday · 1m"),
        ]
        self.messages = {"dave": [{"text": "Is the shop open on sunday", "is_sent": False, "type": "text",
                                   "timestamp": "Jun 12"}]}
        self.answer_states = {"carol": {"has_sent": False, "received_texts": ["See you at the tasting tomorrow"],
                                        "recent_texts": ["See you at the tasting tomorrow"],
                                        "last_direction": "received"}}
        self.known_threads = {"dave": 7}
        self.header_readable = True
        self.instagram_open = True
        self.inbox_ok = True
        self.requests_ok = True
        self.visible_after = 0
        self.send_ok = True
        self.connect_ok = True
        self.raise_on_inbox = False
        self.open_attempts = 0
        self._install()

    def _install(self) -> None:
        rig = self
        mp = self.monkeypatch

        import signal
        import time

        mp.setattr(time, "sleep", lambda *_a, **_k: None)
        mp.setattr(signal, "signal", lambda signum, handler: None)

        self.phone = FakePhone(self)

        class FakeDeviceManager:
            def __init__(self):
                self.device = rig.phone
                self.device_id = DEVICE_ID

            def connect(self, device_id=None):
                return True

            def is_app_installed(self, package):
                rig.calls.append(f"is_installed {package}")
                return True

            def launch_app(self, package, activity=None, stop_first=False):
                rig.calls.append(f"launch {package}")
                rig.phone.screen = "home"
                return True

            def stop_app(self, package):
                rig.calls.append(f"stop {package}")
                return True

        self.device_manager = FakeDeviceManager()

        class FakeConnection:
            def __init__(self, device_id=None):
                self.device_id = device_id
                self.device_manager = None
                self._device = None

            @property
            def device(self):
                return self._device

            @property
            def screen_size(self):
                return (1080, 2340)

            def connect(self):
                rig.calls.append("connect")
                if not rig.connect_ok:
                    return False
                self.device_manager = rig.device_manager
                self._device = rig.phone
                return True

        mp.setattr("bridges.common.device.connection.ConnectionService", FakeConnection)

        from bridges.common.device import app_manager

        mp.setattr(app_manager, "get_installed_app_version", lambda device_id, package, platform: "410.0.0.53.71")
        from taktik.core.compat.selectors import setup as compat_setup

        mp.setattr(compat_setup, "apply_version_overrides",
                   lambda platform, version: rig.calls.append(f"version_overrides {version}") or 0)
        mp.setattr("taktik.core.clone.set_active_package", lambda package: rig.calls.append(f"active_package {package}"))
        # The app language read at the start of a run, recorded instead of applied.
        from taktik.core.social_media.instagram.workflows.core import runtime_setup

        mp.setattr(runtime_setup, "detect_and_optimize",
                   lambda device, *a, **k: rig.calls.append("detect_language") or "en")

        # The deep screen helpers of the DM runtime: recorded stand-ins.
        from bridges.instagram.engagement.runtime.dm.bridge import DMBridge

        def navigate(_self):
            rig.calls.append("navigate_to_dm_inbox")
            if rig.raise_on_inbox:
                raise RuntimeError("inbox exploded")
            if rig.inbox_ok:
                rig.phone.screen = "inbox"
            return rig.inbox_ok

        def open_requests(_self):
            rig.calls.append("open_requests_folder")
            return rig.requests_ok

        def open_conversation(_self, username):
            rig.open_attempts += 1
            rig.calls.append(f"open_conversation {username}")
            if rig.open_attempts > rig.visible_after and username != "nobody":
                rig.phone.open(username)
                return True
            return False

        def send_message(_self, message):
            rig.calls.append(f"send_message {message}")
            return rig.send_ok

        def recorder(name, result=None):
            def method(_self, *args, **kwargs):
                detail = " ".join([str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())])
                rig.calls.append(f"{name} {detail}".strip())
                return result
            return method

        def go_back(_self, *args, **kwargs):
            rig.calls.append("go_back_from_conversation")
            rig.phone.screen = "inbox"

        def collect(_self):
            rig.calls.append("collect_messages")
            return list(rig.messages.get(rig.phone.open_title, []))

        mp.setattr(DMBridge, "navigate_to_dm_inbox", navigate)
        mp.setattr(DMBridge, "open_requests_folder", open_requests)
        mp.setattr(DMBridge, "open_conversation", open_conversation)
        mp.setattr(DMBridge, "send_message", send_message)
        mp.setattr(DMBridge, "_ensure_primary_tab", recorder("ensure_primary_tab"))
        mp.setattr(DMBridge, "_scroll_to_top_of_inbox", recorder("scroll_to_top_of_inbox"))
        mp.setattr(DMBridge, "_reset_inbox_to_top", recorder("reset_inbox_to_top"))
        mp.setattr(DMBridge, "_return_to_inbox_if_needed", recorder("return_to_inbox_if_needed"))
        mp.setattr(DMBridge, "_resolve_thread_username", lambda _self, info, username: username)
        mp.setattr(DMBridge, "_detect_conversation_reply_state", recorder("detect_reply_state", (False, True)))
        mp.setattr(DMBridge, "_collect_messages", collect)
        mp.setattr(DMBridge, "_go_back_from_conversation", go_back)
        mp.setattr(DMBridge, "_is_accounts_to_follow_visible", lambda _self: True)

        def tap(device, element, **_kwargs):
            rig.calls.append(f"tap row {getattr(element, 'username', '?')}")
            if isinstance(element, _Row):
                rig.phone.open(element.username)
            return True

        for package in _DM_MODULES:
            try:
                mp.setattr(f"{package}.reader.tap_element_human", tap)
            except (ImportError, AttributeError):
                pass

        # The database under the persistence module.
        from taktik.core.database.messaging import DmConversationService

        empty_state = {"has_sent": False, "received_texts": [], "recent_texts": [], "last_direction": None}
        mp.setattr(DmConversationService, "lookup_account_id",
                   staticmethod(lambda platform, partner: rig.known_threads.get(partner)))
        mp.setattr(DmConversationService, "thread_answer_state",
                   staticmethod(lambda platform, account_id, username: rig.answer_states.get(username, empty_state)))
        mp.setattr(DmConversationService, "last_known_message", staticmethod(lambda *a, **k: None))
        mp.setattr(DmConversationService, "mark_thread_answered",
                   staticmethod(lambda platform, account_id, username: rig.db.append(
                       {"write": "answered", "account_id": account_id, "partner": username})))
        mp.setattr(DmConversationService, "record_conversation",
                   staticmethod(lambda **kw: rig.db.append({"write": "conversation", **kw})))
        mp.setattr(DmConversationService, "record_sent_message",
                   staticmethod(lambda **kw: rig.db.append({"write": "sent", **kw})))

        class FakeDb:
            def get_or_create_account(self, username, is_bot=False):
                rig.calls.append(f"db_account {username}")
                return 7, False

            def get_or_create_profile(self, data):
                return 100 + len(data["username"]), False

        for package in _DM_MODULES:
            try:
                mp.setattr(f"{package}.persistence.get_db_service", lambda: FakeDb())
                mp.setattr(f"{package}.persistence.configure_db_service", lambda *a, **k: None)
            except (ImportError, AttributeError):
                pass

        # The fallback identity read: a visit to our own profile.
        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions
        from taktik.core.social_media.instagram.actions.business.management.profile import ProfileBusiness

        mp.setattr(NavigationActions, "__init__", lambda _self, *a, **k: None)
        mp.setattr(NavigationActions, "navigate_to_profile_tab",
                   lambda _self, *a, **k: rig.calls.append("navigate_to_profile_tab") or True)
        mp.setattr(ProfileBusiness, "__init__", lambda _self, *a, **k: None)
        mp.setattr(ProfileBusiness, "get_complete_profile_info",
                   lambda _self, *a, **k: rig.calls.append("read_own_profile") or {"username": BOT})

    # ------------------------------------------------------------------ paths

    @staticmethod
    def _config_file_bridge() -> bool:
        from bridges.instagram.engagement.runtime.dm import commands

        return hasattr(commands, "load_dm_bridge_config")

    def bridge_argv(self, spec: dict) -> list[str]:
        """How the desktop starts the bridge for `spec`: a config file, or (before) positional args."""
        if self._config_file_bridge():
            config_path = self.tmp_path / "dm_config.json"
            config_path.write_text(json.dumps(spec), encoding="utf-8")
            return ["dm_bridge", str(config_path)]
        command = spec["command"]
        if command == "send":
            argv = ["dm_bridge", "send", spec["deviceId"], spec["username"], spec["message"]]
        else:
            argv = ["dm_bridge", command, spec["deviceId"], str(spec["limit"])]
        if spec.get("packageName"):
            argv += ["--package", spec["packageName"]]
        return argv

    def run_bridge(self, spec: dict | None = None, argv: list[str] | None = None) -> int:
        """The desktop path, to its exit code."""
        self.monkeypatch.setattr(sys, "argv", argv if argv is not None else self.bridge_argv(spec))

        from bridges.instagram.engagement import dm

        out = io.StringIO()
        self.monkeypatch.setattr(sys, "stdout", out)
        code = 0
        try:
            dm.main()
        except SystemExit as exit_info:
            code = exit_info.code if isinstance(exit_info.code, int) else (0 if exit_info.code is None else 1)
        finally:
            self.monkeypatch.setattr(sys, "stdout", sys.__stdout__)
        for line in out.getvalue().splitlines():
            line = line.strip()
            if line:
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    self.stdout_lines.append(line)
                    continue
                if isinstance(parsed, dict) and "traceback" in parsed:
                    parsed["traceback"] = "<traceback>"
                self.stdout_lines.append(parsed)
        return code

    def run_cli(self, workflow_id: str, payload: dict, env: dict | None = None):
        """The standalone path: `taktik workflows run <workflow_id>`."""
        from click.testing import CliRunner

        from taktik.cli.commands import workflow_cmds

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
        for bucket in (self.calls, self.stdout_lines, self.db, self.cli_results):
            bucket.clear()
        self.phone.screen = "home"
        self.phone.open_title = None
        self.open_attempts = 0


__all__ = ["BOT", "CLONE", "DEVICE_ID", "INSTAGRAM", "InstagramDmRig", "dm_command"]
