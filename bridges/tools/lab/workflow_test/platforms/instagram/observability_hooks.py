"""Instagram action/stat hooks for compat workflow diagnostics."""

from collections.abc import Callable

from loguru import logger


def setup_instagram_action_hooks(
    ipc,
    heartbeat: Callable[[str], None],
    record_stats_snapshot: Callable[[dict], None],
) -> None:
    """Monkey-patch Instagram callbacks to route workflow events via compat IPC."""
    _patch_instagram_ipc_emitter(ipc, heartbeat)
    _patch_instagram_stats_callback(ipc)
    _patch_instagram_stats_snapshot(record_stats_snapshot)


def _patch_instagram_ipc_emitter(ipc, heartbeat: Callable[[str], None]) -> None:
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
            heartbeat(f"follow @{username}")

        @staticmethod
        def emit_like(username, likes_count=1, profile_data=None):
            ipc.send("action_event", action="like", username=username, success=True, data={"count": likes_count})
            heartbeat(f"like {likes_count}x @{username}")

        @staticmethod
        def emit_profile_visit(username):
            ipc.send("action_event", action="profile_visit", username=username, success=True, data={})
            heartbeat(f"visit @{username}")

        @staticmethod
        def emit_action(action_type, username, data=None):
            ipc.send("action_event", action=action_type, username=username, success=True, data=data or {})
            heartbeat(f"{action_type} @{username}")

        @staticmethod
        def emit_profile_captured(username, profile_data=None, profile_pic_base64=None):
            ipc.send(
                "action_event",
                action="profile_captured",
                username=username,
                success=True,
                data={"full_name": (profile_data or {}).get("full_name")},
            )
            heartbeat(f"profile @{username}")

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


def _patch_instagram_stats_snapshot(record_stats_snapshot: Callable[[dict], None]) -> None:
    try:
        from taktik.core.social_media.instagram.actions.core.stats import BaseStatsManager

        original_send = BaseStatsManager._send_stats_update

        def patched_send(self):
            original_send(self)
            try:
                record_stats_snapshot(self.get_summary())
            except Exception:
                pass

        BaseStatsManager._send_stats_update = patched_send
    except Exception:
        pass


__all__ = ["setup_instagram_action_hooks"]
