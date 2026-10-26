"""A recording phone for the Instagram cold DM one-path tests.

The same cold DM payload goes through the desktop bridge (`cold_dm_bridge <config.json>`) and
through the CLI (`taktik workflows run instagram.engagement.coldDm`). The phone below answers the
selectors of the flow (profile, conversation, send button) from a small screen state, and
records every selector query that finds something and every gesture, the `sent_dms` rows and the
session the run opens and closes. The profile of a recipient is opened by the production profile
search, recorded as asked (`navigate_to_profile <handle> force_search=<flag>`): its own screens are
played in its own tests (`actions/atomic/navigation/test_profile_search_opens_only_the_asked_account.py`).
The way home between two recipients (`navigate_to_home`) and the production sending from a profile
(`MessagingBusiness.open_conversation_from_profile`, then `send_in_open_conversation`), the welcome
DM's too, are recorded the same way: their screens are played in their own tests.
Nothing here reaches adb, the network, the AI or the database.
"""
from __future__ import annotations

import io
import json
import re
import sys

import pytest

from one_path_seams import RigNetwork, give_the_cli_a_connected_phone, patch_seam, record_ip_rotations
DEVICE_ID = "emulator-5554"
INSTAGRAM = "com.instagram.android"
AI_KEY = "sk-or-v1-" + "d" * 48


def cold_dm_payload(**overrides) -> dict:
    """What the Cold DM page sends (Electron adds the OpenRouter key in AI mode)."""
    payload = {
        "deviceId": DEVICE_ID,
        "recipients": ["open_one", "closed_one"],
        "messages": ["Hello there"],
        "delayMin": 5,
        "delayMax": 6,
        "maxDmsPerSession": 5,
        "accountId": 7,
        "sessionId": "session-1",
        "messageMode": "manual",
        "skipPrivateAccounts": True,
        "skipVerifiedAccounts": False,
    }
    payload.update(overrides)
    return payload


def _key(selector: dict) -> tuple:
    """(kind, value) of a uiautomator2 selector, whatever form the device proxy gave it."""
    if "resourceIdMatches" in selector:
        match = re.search(r"([A-Za-z0-9_]+)\$?$", selector["resourceIdMatches"].rstrip("$"))
        return ("id", match.group(1) if match else selector["resourceIdMatches"])
    if "resourceId" in selector:
        return ("id", selector["resourceId"].split(":id/")[-1])
    for name, kind in (("text", "text"), ("textContains", "textContains"), ("description", "desc"),
                       ("descriptionContains", "descContains"), ("className", "class")):
        if name in selector:
            return (kind, selector[name])
    return ("other", json.dumps(selector, sort_keys=True))


# An xpath on an id alone, as written or as the clone proxy rewrites it.
_XPATH_ID = re.compile(
    r'^//\*\[(?:\(substring-after\(@resource-id,":id/"\)="(\w+)" or @resource-id="\1"\)'
    r'|@resource-id="[^"]*:id/(\w+)")\]$'
)


def _xpath_key(selector: str) -> tuple:
    """An xpath on an id alone asks what `d(resourceId=...)` asks; any other is its own query."""
    match = _XPATH_ID.match(selector)
    if match:
        return ("id", match.group(1) or match.group(2))
    return ("xpath", selector)


class _Element:
    def __init__(self, phone, key, index=0):
        self.phone = phone
        self.key = key
        self.index = index

    @property
    def exists(self):
        found = self.phone.exists(self.key)
        if found:
            self.phone.rig.calls.append(f"found {self.key[0]}:{self.key[1]}")
        return found

    @property
    def count(self):
        return self.phone.count(self.key)

    def __getitem__(self, index):
        return _Element(self.phone, self.key, index)

    def child(self, **selector):
        return _Element(self.phone, _key(selector), self.index)

    def get_text(self):
        return self.phone.text_of(self.key)

    @property
    def info(self):
        return self.phone.info_of(self.key)

    def click(self):
        self.phone.rig.calls.append(f"click {self.key[0]}:{self.key[1]}")
        self.phone.clicked(self.key)

    def set_text(self, text):
        self.phone.rig.calls.append(f"set_text {self.key[0]}:{self.key[1]} {text}")
        self.phone.typed(self.key, text)

    def send_keys(self, text):
        self.set_text(text)


class FakePhone:
    """Instagram as far as the cold DM flow looks at it."""

    def __init__(self, rig):
        from taktik.core.social_media.instagram.ui.selectors.surfaces.direct_messages import DM_SELECTORS
        from taktik.core.social_media.instagram.ui.selectors.surfaces.profile import PROFILE_SELECTORS

        self.rig = rig
        self.state = "home"
        self.user = None
        #: What the conversation composer holds: the typing reads it back before the send.
        self.composer = ""
        self.edit_text_class = DM_SELECTORS.edit_text_class_name
        suffix = lambda rid: rid.split(":id/")[-1]
        self.ids = {
            "private_state": suffix(PROFILE_SELECTORS.private_empty_state_resource_id),
            "message_button": suffix(PROFILE_SELECTORS.message_button_resource_id),
            "composer": suffix(DM_SELECTORS.composer_edittext_resource_id),
            "send": suffix(DM_SELECTORS.send_button_resource_ids[0]),
        }
        self.invite_text = DM_SELECTORS.invite_sent_text_contains[0]

    def __call__(self, **selector):
        return _Element(self, _key(selector))

    def xpath(self, selector):
        return _Element(self, _xpath_key(selector))

    # --- what the screen shows ------------------------------------------------------------------

    def _profile(self):
        return self.rig.profile(self.user) if self.user else {}

    def exists(self, key) -> bool:
        ids = self.ids
        if key == ("id", ids["private_state"]):
            return self.state == "profile" and self._profile().get("private", False)
        if key == ("id", ids["message_button"]):
            return self.state == "profile" and self._profile().get("message_button", True)
        if key == ("id", ids["composer"]):
            return self.state == "conversation" and not self._profile().get("invite_sent", False)
        if key == ("textContains", self.invite_text):
            return self.state == "conversation" and self._profile().get("invite_sent", False)
        if key == ("id", ids["send"]):
            return self.state == "conversation"
        return False

    def count(self, key) -> int:
        return 1 if self.exists(key) else 0

    def text_of(self, key) -> str:
        return self.user or ""

    def info_of(self, key) -> dict:
        """The focused field, as the typing reads it back: the open composer, nothing else."""
        focused = key in (("class", self.edit_text_class), ("other", json.dumps({"focused": True})))
        if focused and self.exists(("id", self.ids["composer"])):
            return {"text": self.composer, "focused": True, "className": self.edit_text_class}
        raise LookupError(f"no element {key}")

    # --- what a gesture does --------------------------------------------------------------------

    def clicked(self, key) -> None:
        ids = self.ids
        if key == ("id", ids["message_button"]):
            self.state = "conversation"
            self.composer = ""
        elif key == ("id", ids["send"]):
            self.rig.sent.append(self.user)
            self.composer = ""

    def typed(self, key, text) -> None:
        if key == ("id", self.ids["composer"]):
            self.composer = text

    def keyboard_typed(self, text) -> None:
        """The Taktik Keyboard types into the focused field: the composer when it is open."""
        if self.exists(("id", self.ids["composer"])):
            self.composer += text

    def keyboard_cleared(self) -> None:
        self.composer = ""

    def opened_by_the_profile_search(self, username: str) -> bool:
        """The production profile search reached `username`'s profile, or nobody's."""
        if not self.rig.profile(username).get("found", True):
            return False
        self.state = "profile"
        self.user = username
        return True

    def press(self, button):
        self.rig.calls.append(f"press {button}")
        back = {"conversation": "profile", "profile": "home"}
        if button == "back":
            self.state = back.get(self.state, "home")


class InstagramColdDmRig:
    DEVICE_ID = DEVICE_ID

    def __init__(self, monkeypatch, tmp_path):
        self.monkeypatch = monkeypatch
        self.tmp_path = tmp_path
        self.calls: list[str] = []
        self.events: list[tuple[str, dict]] = []
        self.stdout_lines: list = []
        self.sent: list[str] = []
        self.typed: list[str] = []
        self.db: list[dict] = []
        #: The run's session, as the database service is asked to open and close it.
        self.sessions: list[dict] = []
        self.ai_calls: list[dict] = []
        self.cli_results: list = []
        #: username -> what its profile shows; absent fields take the defaults of `profile`.
        self.users: dict[str, dict] = {"closed_one": {"private": True, "message_button": False}}
        self.already_dmed: set[str] = set()
        self.connect_ok = True
        self._install()

    def profile(self, username: str) -> dict:
        return {"found": True, "private": False, "verified": False, "message_button": True,
                **self.users.get(username, {})}

    def _install(self) -> None:
        rig = self
        mp = self.monkeypatch

        import signal
        import time

        mp.setattr(time, "sleep", lambda *_a, **_k: None)
        mp.setattr(signal, "signal", lambda signum, handler: None)

        from bridges.common import ipc as ipc_module

        def _send(_self, msg_type, **kwargs):
            if msg_type != "step_metric":
                rig.events.append((msg_type, kwargs))

        mp.setattr(ipc_module.IPC, "send", _send)

        self.network = RigNetwork(mp)
        record_ip_rotations(mp, rig.calls)

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
                rig.phone.state = "home"
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

        patch_seam(mp, "taktik.core.shared.device.connection", "ConnectionService", FakeConnection)

        from taktik.core.shared.device import app_manager

        mp.setattr(app_manager, "get_installed_app_version", lambda device_id, package, platform: "410.0.0.53.71")
        from taktik.core.compat.selectors import setup as compat_setup

        patch_seam(mp, compat_setup.__name__, "apply_version_overrides",
                   lambda platform, version: rig.calls.append(f"version_overrides {version}") or 0,
                   copies=False)
        patch_seam(mp, "taktik.core.clone", "set_active_package",
                   lambda package: rig.calls.append(f"active_package {package}"))
        patch_seam(mp, "taktik.core.social_media.instagram.ui.language", "detect_and_optimize",
                   lambda device, *a, **k: rig.calls.append("detect_language") or "en")

        from taktik.core.social_media.instagram.actions.atomic.detection import DetectionActions
        from taktik.core.social_media.instagram.actions.atomic.navigation import NavigationActions

        def fake_navigate_to_profile(_self, username, deep_link_usage_percentage=0, force_search=False):
            rig.calls.append(f"navigate_to_profile {username} force_search={force_search}")
            return rig.phone.opened_by_the_profile_search(username)

        mp.setattr(NavigationActions, "navigate_to_profile", fake_navigate_to_profile)

        def fake_navigate_to_home(_self):
            rig.calls.append("navigate_to_home")
            rig.phone.state = "home"
            return True

        mp.setattr(NavigationActions, "navigate_to_home", fake_navigate_to_home)

        from taktik.core.social_media.instagram.workflows.dm.messaging import (
            INVITE_ALREADY_SENT,
            MessagingBusiness,
        )

        def fake_open_conversation(_self, username=None):
            rig.calls.append(f"open_conversation_from_profile {username}")
            if rig.phone.state != "profile" or not rig.profile(rig.phone.user).get("message_button", True):
                return False
            rig.phone.state = "conversation"
            return True

        def fake_send_in_open_conversation(_self, message, typos=True):
            rig.calls.append(f"send_in_open_conversation {message} typos={typos}")
            if rig.profile(rig.phone.user).get("invite_sent", False):
                return INVITE_ALREADY_SENT
            rig.typed.append(message)
            rig.sent.append(rig.phone.user)
            from taktik.core.social_media.instagram.workflows.dm.reply_check import ReplyOutcome

            return ReplyOutcome.SENT

        mp.setattr(MessagingBusiness, "open_conversation_from_profile", fake_open_conversation)
        mp.setattr(MessagingBusiness, "send_in_open_conversation", fake_send_in_open_conversation)

        def fake_is_verified(_self, *a, **k):
            rig.calls.append("read_verified")
            return rig.profile(rig.phone.user).get("verified", False)

        mp.setattr(DetectionActions, "is_verified_account", fake_is_verified)

        def fake_wait_for_profile(_self, *a, **k):
            rig.calls.append("read_profile_screen")
            return rig.phone.state == "profile"

        mp.setattr(DetectionActions, "wait_for_profile_screen", fake_wait_for_profile)

        from taktik.core.shared.input import keyboard as keyboard_module

        mp.setattr(keyboard_module, "is_taktik_keyboard_active", lambda device_id: True)

        def fake_type(device_id, text, **_kwargs):
            rig.calls.append(f"type {text}")
            rig.typed.append(text)
            return True

        mp.setattr(keyboard_module, "type_with_taktik_keyboard", fake_type)

        # The typing of the send path: the Taktik Keyboard is switched before the tap, types into
        # the focused composer, and the composer is read back before the send.
        from taktik.core.shared.input import taktik_keyboard as shared_keyboard

        def fake_shared_type(device_id, text, *_args, **_kwargs):
            rig.calls.append(f"type {text}")
            rig.typed.append(text)
            rig.phone.keyboard_typed(text)
            return True

        def fake_clear(device_id):
            rig.calls.append("clear_field")
            rig.phone.keyboard_cleared()
            return True

        patch_seam(mp, shared_keyboard.__name__, "is_taktik_keyboard_active", lambda device_id: True)
        patch_seam(mp, shared_keyboard.__name__, "type_with_taktik_keyboard", fake_shared_type)
        patch_seam(mp, shared_keyboard.__name__, "clear_text_with_taktik_keyboard", fake_clear)

        from taktik.core.database.messaging import SentDMService

        def fake_check(account_id, recipient, platform="instagram"):
            rig.calls.append(f"db_check {account_id} {recipient} {platform}")
            return recipient in rig.already_dmed

        def fake_record(account_id, recipient, message, success, error_message=None, session_id=None,
                        platform="instagram"):
            rig.db.append({"account_id": account_id, "recipient": recipient, "message": message,
                           "success": success, "error": error_message, "session_id": session_id,
                           "platform": platform})

        mp.setattr(SentDMService, "check_already_sent", staticmethod(fake_check))
        mp.setattr(SentDMService, "record", staticmethod(fake_record))

        class FakeSessionDatabase:
            """The two session calls of the run; any other use of the base is a failure."""

            def create_session(self, account_id, session_name, target_type, target, config_used=None,
                               workflow_type=None):
                rig.sessions.append({"op": "create", "account_id": account_id, "name": session_name,
                                     "target_type": target_type, "target": target,
                                     "workflow_type": workflow_type,
                                     "config_keys": sorted(config_used or {})})
                return 41

            def finalize_session(self, session_id, status, duration_seconds=None, error_message=None,
                                 posts_engaged=None, stop_reason=None):
                rig.sessions.append({"op": "finalize", "session_id": session_id, "status": status,
                                     "duration_is_int": isinstance(duration_seconds, int),
                                     "error": error_message,
                                     "stop_reason": getattr(stop_reason, "code", stop_reason)})
                return True

        patch_seam(mp, "taktik.core.database.local.service", "get_local_database", lambda: FakeSessionDatabase())

        class FakeAI:
            model_generation = "fake-generation"

            def __init__(self, api_key, ipc):
                self.api_key = api_key
                self.ipc = ipc

            def text_completion(self, system_prompt, user_prompt, **kwargs):
                rig.ai_calls.append({"key": self.api_key, "ipc": self.ipc is not None,
                                     "label": kwargs.get("label")})
                return {"success": True, "text": f'"AI note for {kwargs.get("label", "").split("@")[-1]}"'}

        def fake_build_ai_service(*, api_key, ipc=None, **_kwargs):
            return FakeAI(api_key, ipc)

        patch_seam(mp, "taktik.core.ai.factory", "build_ai_service", fake_build_ai_service)

    # ------------------------------------------------------------------ paths

    def run_bridge(self, payload, argv: list[str] | None = None) -> int:
        """The desktop path: `cold_dm_bridge <config.json>`, to its exit code."""
        if argv is None:
            config_path = self.tmp_path / "cold_dm_config.json"
            config_path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
            argv = ["cold_dm_bridge", str(config_path)]
        self.monkeypatch.setattr(sys, "argv", argv)

        from bridges.instagram.cold_dm import cold_dm_bridge as cold_dm

        out = io.StringIO()
        self.monkeypatch.setattr(sys, "stdout", out)
        code = 0
        try:
            cold_dm.main()
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
            # Step telemetry is timestamped, and reaches stdout only when the global sink was wired
            # by a bridge IPC module imported earlier in the session: left out, as from `events`.
            if isinstance(parsed, dict) and parsed.get("type") == "step_metric":
                continue
            self.stdout_lines.append(parsed)
        return code

    def run_cli(self, payload: dict, env: dict | None = None, workflow_id: str = "instagram.engagement.coldDm"):
        """The standalone path: `taktik workflows run instagram.engagement.coldDm`."""
        from click.testing import CliRunner

        from taktik.cli.commands import workflows as workflow_cmds

        give_the_cli_a_connected_phone(self.monkeypatch, self.device_manager, DEVICE_ID)
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
        for bucket in (self.calls, self.events, self.stdout_lines, self.sent, self.typed, self.db, self.sessions,
                       self.ai_calls):
            bucket.clear()
        self.phone.state = "home"
        self.phone.user = None
        self.phone.composer = ""


__all__ = ["AI_KEY", "DEVICE_ID", "INSTAGRAM", "InstagramColdDmRig", "cold_dm_payload"]
