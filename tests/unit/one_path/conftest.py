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
        self.restart_ok = True
        #: The acting account the phone shows; None when its profile cannot be read.
        self.own_username = "acting_account"
        #: What each profile-visiting run returns, in order; missing fields keep their default.
        self.profile_runs: list[dict] = []
        #: What each follow-graph sync returns, and the rows it reports on the way.
        self.sync_runs: list[dict] = []
        self.sync_rows: list[dict] = [
            {"list_type": "following", "username": "fan_one", "display_name": "Fan One",
             "relationship": "Suivi(e)", "is_new": True},
        ]
        #: The inbox, the new-followers page and the Activity page, as the phone shows them.
        self.inbox_opens = True
        self.new_followers_page_opens = True
        self.new_follower_rows: list[dict] = []
        #: Display name -> the handle its profile shows (absent: unreadable).
        self.profile_handles: dict[str, str] = {}
        self.activity_opens = True
        self.activity_rows: list[dict] = []
        self.activity_fails = False
        self.hello_candidates: list[str] = []
        #: What each read of the suggestions block returns, in order; then nothing.
        self.suggestion_reads: list[list[dict]] = []
        #: The rows the run hands to the database, in order.
        self.db_writes: list[dict] = []
        #: What the CLI's handler returned, run by run.
        self.cli_results: list = []
        #: The DM inbox as the phone shows it: conversations (ConversationData fields), the sends
        #: that fail, the follow-backs that fail, and the three other inbox lists.
        self.dm_conversations: list[dict] = []
        self.dm_send_failures: set[str] = set()
        self.follow_back_failures: set[str] = set()
        self.unreplied_rows: list[dict] = []
        self.message_requests: list[dict] = []
        self.inbox_notifications: list[dict] = []
        #: The AI's engagement verdict per handle; absent: the classification carries none.
        self.verdicts: dict[str, dict] = {}
        #: What the database already knows: our own texts per partner, who already had a DM,
        #: whose thread holds a message of ours, and whether the duplicate guard can be asked.
        self.known_sent: dict[str, list[str]] = {}
        self.already_dmed: set[str] = set()
        self.threads_with_us: set[str] = set()
        self.guard_broken = False
        #: Welcome DMs that fail (privacy-blocked), and the outreach workflows built.
        self.welcome_send_failures: set[str] = set()
        self.outreaches: list = []
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
                return rig.restart_ok

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
                #: Post URL opens its link on this serial.
                self.device_id = device_id
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

        def classify_profile_niche(*, username, **kwargs):
            rig.calls.append(f"ai_classify {username}")
            classification = {"niche_category": "sport", "niche": "running"}
            if username in rig.verdicts:
                classification["engagement"] = dict(rig.verdicts[username])
            return {"classification": classification}

        def fake_build_ai_service(*, api_key, ipc=None, **kwargs):
            rig.ai_services.append({"api_key": api_key, "has_ipc": ipc is not None})
            return SimpleNamespace(name="fake-ai", classify_profile_niche=classify_profile_niche)

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

        class FakeScreenshot:
            def save(self, *_args, **_kwargs):
                return None

        def fake_screenshot(device, *args, **kwargs):
            rig.calls.append("screenshot")
            return FakeScreenshot()

        mp.setattr(ai_hooks, "shared_screenshot_pil", fake_screenshot)

        self._install_sync_fakes()
        self._install_inbox_fakes()
        self._install_dm_fakes()

    def _install_sync_fakes(self) -> None:
        rig = self
        mp = self.monkeypatch

        from taktik.core.social_media.tiktok.actions.business.workflows import (
            sync_lists as sync_lists_package,
        )
        from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists import (
            workflow as sync_lists_workflow,
        )
        from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists.models import (
            SyncListsStats,
        )

        class ScriptedSyncStats(SyncListsStats):
            def to_dict(self):
                return {**super().to_dict(), "elapsed_seconds": 0, "elapsed_formatted": "0m 0s"}

        class FakeSyncListsWorkflow:
            """Records its config and the account it runs as, reports each row of `rig.sync_rows`,
            returns the next outcome of `rig.sync_runs` (by default one new row)."""

            def __init__(self, device, config):
                rig.calls.append("workflow_built")
                self.device = device
                self.config = config
                self.on_row = None
                rig.workflows.append(self)

            def set_on_row_callback(self, callback):
                self.on_row = callback

            def run(self, bot_username=None):
                rig.calls.append(f"workflow_run as {bot_username}")
                for row in rig.sync_rows:
                    if self.on_row:
                        self.on_row(dict(row))
                outcome = {"rows_seen": 1, "new_count": 1, "following_seen": 1,
                           "completion_reason": "known_reached"}
                if rig.sync_runs:
                    outcome.update(rig.sync_runs.pop(0))
                return ScriptedSyncStats(**outcome)

        for module in (sync_lists_workflow, sync_lists_package):
            mp.setattr(module, "SyncListsWorkflow", FakeSyncListsWorkflow)

    def _install_inbox_fakes(self) -> None:
        rig = self
        mp = self.monkeypatch

        class FakeDMActions:
            def __init__(self, device):
                pass

            def navigate_to_inbox(self):
                rig.calls.append("open_inbox")
                return rig.inbox_opens

            def open_new_followers_page(self):
                rig.calls.append("open_new_followers")
                return rig.new_followers_page_opens

            def get_new_followers(self, max_items=50):
                rig.calls.append(f"list_new_followers {max_items}")
                return [dict(row) for row in rig.new_follower_rows]

            def open_new_follower_profile(self, shown):
                rig.calls.append(f"open_follower_profile {shown}")
                return rig.profile_handles.get(shown)

            def say_hello_candidates(self):
                rig.calls.append("hello_candidates")
                return list(rig.hello_candidates)

            def say_hello(self, name):
                rig.calls.append(f"say_hello {name}")
                return True

        mp.setattr("taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions.DMActions",
                   FakeDMActions)

        class FakeActivityActions:
            def __init__(self, device):
                pass

            def open_activity(self, expand=False):
                rig.calls.append(f"open_activity expand={expand}")
                return rig.activity_opens

            def read_activity(self, max_rows=30):
                rig.calls.append(f"read_activity {max_rows}")
                if rig.activity_fails:
                    raise RuntimeError("activity list vanished")
                return [SimpleNamespace(**row) for row in rig.activity_rows[:max_rows]]

            def read_suggested_accounts(self):
                rig.calls.append("read_suggestions")
                return rig.suggestion_reads.pop(0) if rig.suggestion_reads else []

            def _scroll_down(self, scale=1.0):
                rig.calls.append(f"scroll {scale}")

            def follow_suggested_account(self, name):
                rig.calls.append(f"follow_suggested {name}")
                return True

        mp.setattr(
            "taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions.ActivityActions",
            FakeActivityActions,
        )

        # The database, at the seams every notification writer goes through.
        from taktik.core.database import tiktok_account_identity
        from taktik.core.database.notifications import NotificationService

        def get_or_create_account(handle, is_bot=True):
            rig.db_writes.append({"account": handle})
            return 42, False

        fake_service = SimpleNamespace(local_db=SimpleNamespace(
            tiktok=SimpleNamespace(get_or_create_account=get_or_create_account)))
        mp.setattr(tiktok_account_identity, "configure_db_service", lambda *a, **k: None)
        mp.setattr(tiktok_account_identity, "get_db_service", lambda: fake_service)

        def record_notifications(*, platform, account_id, items):
            rig.db_writes.append({"platform": platform, "account_id": account_id,
                                  "items": [dict(item) for item in items]})
            return [True] * len(items)

        mp.setattr(NotificationService, "record_notifications", staticmethod(record_notifications))

    def _install_dm_fakes(self) -> None:
        rig = self
        mp = self.monkeypatch

        from taktik.core.social_media.tiktok.actions.business.workflows import dm as dm_package
        from taktik.core.social_media.tiktok.actions.business.workflows.dm import (
            agent_handler as dm_handler,
            inbox_agent_handler as inbox_handler,
            outreach as outreach_module,
            workflow as dm_workflow,
        )
        from taktik.core.social_media.tiktok.actions.business.workflows.dm.models import (
            ConversationData,
            DMStats,
        )

        class ScriptedDMStats(DMStats):
            """A fixed elapsed time, so a snapshot of `to_dict()` holds still."""

            def to_dict(self):
                return {**super().to_dict(), "elapsed_seconds": 0, "elapsed_formatted": "0m 0s"}

        class FakeDMWorkflow:
            """The DM workflow of every inbox flow: records its config and what it is asked, fires
            the callbacks the real one fires, answers from what `rig` says the phone shows."""

            def __init__(self, device, config=None):
                rig.calls.append("dm_workflow_built")
                self.device = device
                self.config = config
                self.stats = ScriptedDMStats()
                self.callbacks = {}
                rig.workflows.append(self)

            def _fire(self, name, *args):
                callback = self.callbacks.get(name)
                if callback is not None:
                    callback(*args)

            def set_on_conversation_callback(self, cb):
                self.callbacks["conversation"] = cb

            def set_on_message_sent_callback(self, cb):
                self.callbacks["message_sent"] = cb

            def set_on_stats_callback(self, cb):
                self.callbacks["stats"] = cb

            def set_on_progress_callback(self, cb):
                self.callbacks["progress"] = cb

            def set_on_new_follower_callback(self, cb):
                self.callbacks["new_follower"] = cb

            def set_on_follow_back_result_callback(self, cb):
                self.callbacks["follow_back_result"] = cb

            def set_on_unreplied_callback(self, cb):
                self.callbacks["unreplied"] = cb

            def set_on_message_request_callback(self, cb):
                self.callbacks["message_request"] = cb

            def set_on_request_result_callback(self, cb):
                self.callbacks["request_result"] = cb

            def set_on_notification_callback(self, cb):
                self.callbacks["notification"] = cb

            def stop(self):
                rig.calls.append("dm_workflow_stop")

            def get_stats(self):
                return self.stats

            def read_conversations(self):
                target = self.config.max_conversations
                rig.calls.append(f"read_conversations {target}")
                read = []
                for row in rig.dm_conversations[:target]:
                    self._fire("progress", len(read) + 1, target, row["name"])
                    conversation = ConversationData(**row)
                    self.stats.conversations_read += 1
                    self.stats.messages_read += len(conversation.messages)
                    read.append(conversation)
                    self._fire("conversation", conversation.to_dict())
                    self._fire("stats", self.stats.to_dict())
                return read

            def send_bulk_messages(self, messages):
                results = []
                for index, item in enumerate(messages):
                    conversation = item.get("conversation", "")
                    message = item.get("message", "")
                    if not conversation or not message:
                        results.append({"conversation": conversation, "success": False,
                                        "error": "Missing conversation or message"})
                        continue
                    self._fire("progress", index + 1, len(messages), conversation)
                    rig.calls.append(f"send_message {conversation} {message!r}")
                    sent = conversation not in rig.dm_send_failures
                    if sent:
                        self.stats.messages_sent += 1
                        self._fire("stats", self.stats.to_dict())
                        self._fire("message_sent", {"conversation": conversation, "message": message,
                                                    "success": True})
                    results.append({"conversation": conversation, "success": sent,
                                    "error": None if sent else "Failed to send"})
                return results

            def read_new_followers(self, max_items=50):
                rig.calls.append(f"read_new_followers {max_items}")
                followers = [dict(row) for row in rig.new_follower_rows][:max_items]
                for follower in followers:
                    self._fire("new_follower", follower)
                return followers

            def follow_back_users(self, usernames):
                rig.calls.append(f"follow_back {list(usernames)}")
                results = []
                for name in usernames:
                    result = {"username": name, "success": name not in rig.follow_back_failures}
                    results.append(result)
                    self._fire("follow_back_result", result)
                return results

            def read_unreplied_conversations(self, max_items=30, only_unreplied=True):
                rig.calls.append(f"read_unreplied {max_items} only_unreplied={only_unreplied}")
                rows = [dict(row) for row in rig.unreplied_rows
                        if row.get("unreplied") or not only_unreplied][:max_items]
                for row in rows:
                    self._fire("unreplied", row)
                return rows

            def read_message_requests(self, max_items=30):
                rig.calls.append(f"read_message_requests {max_items}")
                rows = [dict(row) for row in rig.message_requests][:max_items]
                for row in rows:
                    self._fire("message_request", row)
                return rows

            def process_message_requests(self, decisions):
                rig.calls.append(f"process_requests {json.dumps(decisions, sort_keys=True)}")
                results = []
                for decision in decisions:
                    result = {"username": decision.get("username", ""),
                              "action": decision.get("action", "accept"), "success": True,
                              "replied": bool((decision.get("message") or "").strip())}
                    results.append(result)
                    self._fire("request_result", result)
                return results

            def read_notifications(self, max_items=20):
                rig.calls.append(f"read_inbox_notifications {max_items}")
                rows = [dict(row) for row in rig.inbox_notifications][:max_items]
                for row in rows:
                    self._fire("notification", row)
                return rows

        for module in (dm_workflow, dm_package):
            mp.setattr(module, "DMWorkflow", FakeDMWorkflow)
        # A registrar may bind its default factory when it is defined.
        for fn in (dm_handler.register_tiktok_dm_handlers, dm_handler.build_tiktok_dm_handler,
                   inbox_handler.register_tiktok_inbox_handlers, inbox_handler.build_tiktok_inbox_handler):
            if "workflow_factory" in (fn.__kwdefaults__ or {}):
                mp.setitem(fn.__kwdefaults__, "workflow_factory", FakeDMWorkflow)

        class FakeOutreach:
            """The production DM path of the welcome pass: consults the duplicate checker it is
            given, reports through its notifier and records through its recorder, as the real one."""

            def __init__(self, device_id, *, notifier=None, duplicate_checker=None, sent_dm_recorder=None,
                         manager_factory=None, **_kwargs):
                rig.calls.append(f"outreach_built {device_id}")
                self.device_id = device_id
                self.notifier = notifier
                self.duplicate_checker = duplicate_checker
                self.sent_dm_recorder = sent_dm_recorder
                self.manager_factory = manager_factory
                rig.outreaches.append(self)

            def connect(self):
                manager = self.manager_factory(device_id=self.device_id) if self.manager_factory else None
                session = getattr(manager, "device_manager", None)
                rig.calls.append("outreach_connect" if session is not None else "outreach_connect (no session)")
                return session is not None

            def run(self, recipients, messages, delay_min=30, delay_max=60, max_dms=50, account_id=1,
                    session_id=None, message_provider=None):
                rig.calls.append(f"outreach_run {list(recipients)} {list(messages)} max={max_dms} "
                                 f"delays={delay_min}-{delay_max} account={account_id} session={session_id}")
                success = failed = 0
                for recipient in list(recipients)[:max_dms]:
                    if self.duplicate_checker and self.duplicate_checker(account_id, recipient, "tiktok"):
                        rig.calls.append(f"welcome_skip {recipient}")
                        continue
                    rig.calls.append(f"welcome_dm {recipient}")
                    if recipient in rig.welcome_send_failures:
                        failed += 1
                        outreach_module._notify(self.notifier, "dm_result", username=recipient, success=False,
                                                error="Privacy settings blocked")
                        self.sent_dm_recorder(account_id, recipient, "", False, "Privacy blocked", session_id,
                                              "tiktok")
                        continue
                    success += 1
                    outreach_module._notify(self.notifier, "dm_result", username=recipient, success=True,
                                            error=None)
                    self.sent_dm_recorder(account_id, recipient, messages[0], True, None, session_id, "tiktok")
                outreach_module._notify(self.notifier, "stats", stats={"sent": success, "success": success,
                                                                      "failed": failed})
                return {"success": True, "dms_sent": success, "dms_success": success, "dms_failed": failed}

        mp.setattr(outreach_module, "TikTokDMOutreachWorkflow", FakeOutreach)

    def install_dm_database(self) -> None:
        """The DM tables, at the seams every DM writer and the welcome guard go through."""
        rig = self
        mp = self.monkeypatch

        import sqlite3

        import taktik.core.database as database_package
        from taktik.core.database.messaging import DmConversationService, SentDMService
        from taktik.core.database.repositories.messaging import (
            DmMessageRepository,
            DmThreadRepository,
            SentDMRepository,
        )

        def known_sent_texts(platform, account_id, partner_username, limit=50):
            return list(rig.known_sent.get(partner_username.lower(), []))

        def record_conversation(**kwargs):
            rig.db_writes.append({"dm_conversation": kwargs})
            return "thread-1"

        def record_sent_message(**kwargs):
            rig.db_writes.append({"dm_sent_message": kwargs})
            return "thread-1"

        def record_sent_dm(account_id, recipient, message, success, error_message=None, session_id=None,
                           platform="instagram"):
            rig.db_writes.append({"sent_dm": {"account_id": account_id, "recipient": recipient,
                                              "message": message, "success": success,
                                              "error_message": error_message, "session_id": session_id,
                                              "platform": platform}})

        mp.setattr(DmConversationService, "known_sent_texts", staticmethod(known_sent_texts))
        mp.setattr(DmConversationService, "record_conversation", staticmethod(record_conversation))
        mp.setattr(DmConversationService, "record_sent_message", staticmethod(record_sent_message))
        mp.setattr(SentDMService, "record", staticmethod(record_sent_dm))

        def get_or_create_profile(data):
            rig.db_writes.append({"profile": data.get("username")})
            return 7, False

        fake_service = SimpleNamespace(get_or_create_profile=get_or_create_profile)
        modules = [database_package]
        try:
            from bridges.tiktok.workflows.engagement.runtime import dm_persistence

            modules.append(dm_persistence)
        except ImportError:
            pass
        for module in modules:
            mp.setattr(module, "get_db_service", lambda: fake_service)
            mp.setattr(module, "configure_db_service", lambda *a, **k: None)

        # The guard opens the database file itself: an empty one, whose repositories answer from
        # what `rig` says the database knows.
        database_file = self.tmp_path / "taktik.db"
        sqlite3.connect(database_file).close()
        mp.setenv("TAKTIK_DB_PATH", str(database_file))

        def check_already_sent(_self, account_id, recipient, platform="instagram"):
            if rig.guard_broken:
                raise sqlite3.OperationalError("no such table: sent_dms")
            return recipient.lower() in rig.already_dmed

        def find_sync_id_for_inbox(_self, platform, account_id, handle):
            return f"thread-{handle}" if handle.lower() in rig.threads_with_us else None

        mp.setattr(SentDMRepository, "check_already_sent", check_already_sent)
        mp.setattr(DmThreadRepository, "ensure_table", lambda _self: None)
        mp.setattr(DmThreadRepository, "find_sync_id_for_inbox", find_sync_id_for_inbox)
        mp.setattr(DmMessageRepository, "has_sent_message", lambda _self, platform, sync_id: True)

    def show_dm_inbox(self) -> None:
        """Two conversations: one with a handle, whose last bubble is ours but was not read as ours,
        and one with a display name."""
        self.dm_conversations = [
            {"name": "fan_one", "messages": [
                {"text": "salut", "type": "text", "is_sent": False},
                {"text": "Merci pour le suivi", "type": "text", "is_sent": False},
            ], "last_message": "Merci pour le suivi", "unread_count": 1},
            {"name": "Fan Two", "messages": [{"text": "coucou", "type": "text", "is_sent": False,
                                              "timestamp": "Hier"}], "unread_count": 0},
        ]
        self.known_sent = {"fan_one": ["Merci pour le suivi"]}

    def show_inbox_lists(self) -> None:
        """What the unreplied, requests and activity readers find."""
        self.unreplied_rows = [
            {"username": "fan_one", "preview": "salut", "unreplied": True},
            {"username": "Fan Two", "preview": "ok merci", "unreplied": False},
        ]
        self.message_requests = [
            {"username": "stranger_a", "preview": "hello", "timestamp": "2 j"},
            {"username": "Stranger B", "preview": "tu fais des collabs ?", "timestamp": "1 sem."},
        ]
        self.inbox_notifications = [
            {"title": "Activity", "preview": "fan_one a aimé ta vidéo", "category": "activity"},
            {"title": "System notifications", "preview": "Nouvelle fonctionnalité", "category": "system"},
        ]

    def show_welcome_verdicts(self) -> None:
        """Three new followers (as `show_notifications`) and what the AI says of the two it sees."""
        self.show_notifications()
        self.profile_handles = {"fan_one": "fan_one", "Fan Two": "fan_two"}
        self.verdicts = {
            "fan_one": {"relevant": True, "score": 0.9, "reason": "fits", "follow": True, "comment": False,
                        "like": True},
            "fan_two": {"relevant": True, "score": 0.8, "reason": "close niche", "follow": True,
                        "comment": False, "like": False},
        }

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

    def show_notifications(self) -> None:
        """Three new followers (a handle, a name that resolves, one that does not) and two
        Activity rows."""
        self.new_follower_rows = [
            {"username": "fan_one", "activity": "2 j", "can_follow_back": True},
            {"username": "Fan Two", "activity": "1 sem.", "can_follow_back": False},
            {"username": "Emile B", "activity": "3 sem.", "can_follow_back": True},
        ]
        self.profile_handles = {"Fan Two": "fan_two"}
        self.activity_rows = [
            {"kind": "like", "usernames": ["fan_one"], "others_count": 3, "age_label": "2 j",
             "post_count": 1},
            {"kind": "profile_view", "usernames": ["Nico Lito"], "others_count": 10,
             "age_label": "1 sem.", "post_count": 0},
        ]

    def forget_run(self) -> None:
        """Clear what a run recorded, before the same payload goes down the other path."""
        for recorded in (self.calls, self.events, self.workflows, self.ai_installs, self.ai_services,
                         self.db_writes, self.cli_results, self.outreaches):
            recorded.clear()

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


@pytest.fixture
def post_url_payload():
    return _post_url_payload


@pytest.fixture
def sync_payload():
    return _sync_payload


@pytest.fixture
def notifications_payload():
    return _notifications_payload


@pytest.fixture
def dm_read_payload():
    return _dm_read_payload


@pytest.fixture
def dm_send_payload():
    return _dm_send_payload


@pytest.fixture
def inbox_payload():
    return _inbox_payload


@pytest.fixture
def welcome_ai():
    """A fresh copy of `WELCOME_AI` per call."""
    return lambda: json.loads(json.dumps(WELCOME_AI))


def _dm_read_payload(**overrides) -> dict:
    """What TikTokDM.tsx sends to read the inbox, key for key, with its defaults."""
    payload = {
        "deviceId": DEVICE_ID, "workflowType": "dm_read", "maxConversations": 10, "skipNotifications": True,
        "skipGroups": False, "onlyUnread": False, "delayBetweenConversations": 1.0,
    }
    payload.update(overrides)
    return payload


def _dm_send_payload(**overrides) -> dict:
    """What TikTokDM.tsx sends to answer: one reply typed by hand, one AI reply as the model wrote
    it (trailing newline included), with the page's delays."""
    payload = {
        "deviceId": DEVICE_ID, "workflowType": "dm_send",
        "messages": [
            {"conversation": "fan_one", "message": "Merci beaucoup !"},
            {"conversation": "Fan Two", "message": "Avec plaisir, à bientôt\n"},
        ],
        "delayBetweenMessages": 1.0, "delayAfterSend": 0.5,
    }
    payload.update(overrides)
    return payload


#: The `ai` block of a welcome pass: AI on, a key, the new-followers block with a text to send.
WELCOME_AI = {
    "enabled": True, "openrouterApiKey": "test-openrouter-key", "accountNiche": "sport",
    "newFollowers": {"enabled": True, "followBack": True, "welcomeDm": True, "minScore": 0.6,
                     "messages": ["Bienvenue !"], "maxDms": 5, "delayMin": 30, "delayMax": 70},
}


def _inbox_payload(workflow_type: str, mode: str = "scrape", **overrides) -> dict:
    """What the four inbox pages send (TikTokNewFollowers, TikTokUnreplied, TikTokRequests,
    TikTokActivity), key for key, with their defaults."""
    payload = {"deviceId": DEVICE_ID, "workflowType": workflow_type}
    if workflow_type == "new_followers" and mode == "follow_back":
        payload.update({"mode": "follow_back", "usernames": ["fan_one", "Fan Two"]})
    elif workflow_type == "new_followers":
        payload.update({"mode": "scrape", "maxItems": 30})
    elif workflow_type == "dm_unreplied":
        payload.update({"maxItems": 30, "onlyUnreplied": True})
    elif workflow_type == "dm_requests" and mode == "execute":
        payload.update({"mode": "execute", "decisions": [
            {"username": "stranger_a", "action": "accept", "message": "Oui, écris-moi"},
            {"username": "Stranger B", "action": "decline"},
        ]})
    elif workflow_type == "dm_requests":
        payload.update({"mode": "scrape", "maxItems": 30})
    elif workflow_type == "dm_activity":
        payload.update({"maxItems": 20})
    payload.update(overrides)
    return payload


def _post_url_payload(**overrides) -> dict:
    """What TikTokPostUrl.tsx sends, key for key, AI off, "1 %" of likes."""
    payload = {
        "deviceId": DEVICE_ID, "allowRouterDevice": False, "workflowType": "post_url",
        "postUrl": "https://www.tiktok.com/@creator/video/1", "maxCommenters": 12, "maxProfiles": 5,
        "maxVideos": 5, "maxLikesPerSession": 30, "maxFollowsPerSession": 10, "postsPerProfile": 1,
        "minWatchTime": 2, "maxWatchTime": 6, "likeProbability": 1, "followProbability": 5,
        "favoriteProbability": 0, "pauseAfterActions": 8, "pauseDurationMin": 20,
        "pauseDurationMax": 40, "requiredHashtags": [], "excludedHashtags": [], "minLikes": None,
        "maxLikes": None, "skipAlreadyLiked": True,
    }
    payload.update(overrides)
    return payload


_SYNC_WORKFLOW_BY_LIST = {"following": "sync_following", "followers": "sync_followers", "both": "sync_lists"}


def _sync_payload(list_type: str = "following", **overrides) -> dict:
    """What TikTokSync.tsx sends, key for key, with its defaults."""
    payload = {
        "deviceId": DEVICE_ID, "allowRouterDevice": False,
        "workflowType": _SYNC_WORKFLOW_BY_LIST[list_type], "listType": list_type, "incremental": True,
        "maxScrolls": 60, "resolveMissingHandles": False, "maxResolutions": 50, "minDelay": 0.6,
        "maxDelay": 1.4,
    }
    payload.update(overrides)
    return payload


def _notifications_payload(**overrides) -> dict:
    """What TikTokNotifications.tsx sends, key for key, with its defaults."""
    payload = {
        "deviceId": DEVICE_ID, "workflowType": "notifications", "scanNewFollowers": True,
        "maxFollowerResolutions": 10, "readActivity": True, "maxActivityRows": 30, "maxHellos": 0,
        "maxSuggestedFollows": 0,
    }
    payload.update(overrides)
    return payload


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
