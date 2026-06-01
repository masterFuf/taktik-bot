"""Observability hooks for compat workflow diagnostics."""

from loguru import logger


_active_watchdog = None
_active_tracer = None
_last_stats: dict | None = None

_SCREEN_PATTERNS = [
    ("Recovered to followers list", "followers_list"),
    ("Followers list opened", "followers_list"),
    ("followers list", "followers_list"),
    ("Following list opened", "following_list"),
    ("following list", "following_list"),
    ("clickable followers found", "followers_list"),
    ("Detecting Followers list", "followers_list"),
    ("Post view detected", "post_view"),
    ("First post opened", "post_view"),
    ("post opened", "post_view"),
    ("Reel post", "post_view"),
    ("Post liked", "post_view"),
    ("Navigating to next post", "post_view"),
    ("Clicking Like button", "post_view"),
    ("Detecting Liked button", "post_view"),
    ("Detecting Post screen", "post_view"),
    ("Story viewer", "story_viewer"),
    ("story viewer", "story_viewer"),
    ("Profile screen detected", "target_profile"),
    ("Profile extracted", "target_profile"),
    ("Batch profile flags", "target_profile"),
    ("Batch text:", "target_profile"),
    ("Complete profile data", "target_profile"),
    ("Profile image extracted", "target_profile"),
    ("Clicking on @", "navigating_to_profile"),
    ("Confirmed: on own profile", "own_profile"),
    ("own profile", "own_profile"),
    ("Home screen", "home"),
    ("Search screen", "search"),
    ("Recovery - clicking back", "navigating_back"),
    ("Comment button clicked", "comment_input"),
    ("Comment field", "comment_input"),
    ("Attempting to comment", "post_view"),
]


def set_active_watchdog(watchdog) -> None:
    global _active_watchdog
    _active_watchdog = watchdog


def clear_active_watchdog() -> None:
    set_active_watchdog(None)


def set_active_tracer(tracer) -> None:
    global _active_tracer
    _active_tracer = tracer


def get_last_stats() -> dict | None:
    return _last_stats


def setup_log_sink(ipc) -> None:
    """Add a loguru sink that streams every log line to the renderer via IPC."""

    def ipc_sink(message):
        record = message.record
        msg_text = str(message).rstrip()
        ipc.send(
            "log",
            level=record["level"].name.lower(),
            text=msg_text,
            module=record.get("name", ""),
            function=record.get("function", ""),
            ts=record["time"].strftime("%H:%M:%S.%f")[:-3],
        )
        if _active_watchdog and record["level"].name.upper() in ("INFO", "SUCCESS", "WARNING"):
            _active_watchdog.heartbeat(msg_text[:80])
        if _active_tracer:
            screen = _infer_screen_from_log(msg_text)
            if screen:
                _active_tracer.set_screen(screen)

    logger.add(ipc_sink, level="DEBUG", format="{message}")


def setup_action_hooks(ipc) -> None:
    """Monkey-patch IPCEmitter and stats callbacks to route events via compat IPC."""
    _patch_instagram_ipc_emitter(ipc)
    _patch_instagram_stats_callback(ipc)
    _patch_instagram_stats_snapshot()


def _infer_screen_from_log(text: str) -> str | None:
    for pattern, screen in _SCREEN_PATTERNS:
        if pattern in text:
            return screen
    return None


def _heartbeat(message: str) -> None:
    if _active_watchdog:
        _active_watchdog.heartbeat(message)


def _patch_instagram_ipc_emitter(ipc) -> None:
    try:
        from taktik.core.social_media.instagram.actions.core.ipc.emitter import IPCEmitter

        @staticmethod
        def emit_follow(username, success=True, profile_data=None):
            ipc.send(
                "action_event",
                action="follow",
                username=username,
                success=success,
                data={"followers": (profile_data or {}).get("followers_count")},
            )
            _heartbeat(f"follow @{username}")

        @staticmethod
        def emit_like(username, likes_count=1, profile_data=None):
            ipc.send("action_event", action="like", username=username, success=True, data={"count": likes_count})
            _heartbeat(f"like {likes_count}x @{username}")

        @staticmethod
        def emit_profile_visit(username):
            ipc.send("action_event", action="profile_visit", username=username, success=True, data={})
            _heartbeat(f"visit @{username}")

        @staticmethod
        def emit_action(action_type, username, data=None):
            ipc.send("action_event", action=action_type, username=username, success=True, data=data or {})
            _heartbeat(f"{action_type} @{username}")

        @staticmethod
        def emit_profile_captured(username, profile_data=None, profile_pic_base64=None):
            ipc.send(
                "action_event",
                action="profile_captured",
                username=username,
                success=True,
                data={"full_name": (profile_data or {}).get("full_name")},
            )
            _heartbeat(f"profile @{username}")

        IPCEmitter.emit_follow = emit_follow
        IPCEmitter.emit_like = emit_like
        IPCEmitter.emit_profile_visit = emit_profile_visit
        IPCEmitter.emit_action = emit_action
        IPCEmitter.emit_profile_captured = emit_profile_captured

        logger.info("[WorkflowTest] IPCEmitter patched for compat action events")
    except Exception as exc:
        logger.warning(f"[WorkflowTest] Could not patch IPCEmitter: {exc}")


def _patch_instagram_stats_callback(ipc) -> None:
    try:
        from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager

        original_init = BaseStatsManager.__init__

        def patched_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)

            def on_stats(stats_dict):
                ipc.send("instagram_stats", stats=stats_dict)

            self.set_on_stats_callback(on_stats)

        BaseStatsManager.__init__ = patched_init
        logger.info("[WorkflowTest] BaseStatsManager patched for compat stats")
    except Exception as exc:
        logger.warning(f"[WorkflowTest] Could not patch BaseStatsManager: {exc}")


def _patch_instagram_stats_snapshot() -> None:
    try:
        from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager

        original_send = BaseStatsManager._send_stats_update

        def patched_send(self):
            original_send(self)
            global _last_stats
            try:
                _last_stats = self.get_summary()
            except Exception:
                pass

        BaseStatsManager._send_stats_update = patched_send
    except Exception:
        pass


__all__ = [
    "clear_active_watchdog",
    "get_last_stats",
    "set_active_tracer",
    "set_active_watchdog",
    "setup_action_hooks",
    "setup_log_sink",
]

