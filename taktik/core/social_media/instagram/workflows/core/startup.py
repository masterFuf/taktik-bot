"""Instagram session start, shared by the desktop bridge and the CLI.

A clean restart (force-stop, then launch) before the run, so the account is detected from the home
feed and not from wherever a previous session left Instagram. It used to live in the bridge only:
the workflow config tells the automation that the host restarted the app, and from the CLI no host
did, so a terminal run started on whatever screen was open.

The caller brings the app to restart (`is_installed()`, `restart()`: the bridges' `AppService`) and
an optional health check of the device agent. Events go through an injected notifier shaped like
the bridge IPC (`status`, `error`, `log`); without one they go to the log. This module never opens
a device connection of its own.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from loguru import logger

HealthCheck = Callable[[], Mapping[str, Any]]


class LoggingSessionNotifier:
    """Fallback notifier: the start's events go to the log."""

    def status(self, status: str, message: str = "") -> None:
        logger.info(f"[{status}] {message}")

    def error(self, error: str, error_code: Optional[str] = None, **_extra: Any) -> None:
        logger.error(f"{error} ({error_code})" if error_code else error)

    def log(self, level: str, message: str) -> None:
        getattr(logger, level if level in ("info", "warning", "error", "debug", "success") else "info")(message)


def start_instagram_session(
    app: Any,
    *,
    notifier: Any = None,
    health_check: Optional[HealthCheck] = None,
) -> bool:
    """Restart Instagram on `app` for a clean, consistent initial state. False: the run must not start.

    The automation honours `skip_initial_restart=True` in its config (it does not restart again)
    but still dismisses any post-restart popup.
    """
    notifier = notifier if notifier is not None else LoggingSessionNotifier()
    try:
        notifier.status("launching", "Restarting Instagram...")

        if health_check is not None:
            atx_result = health_check()
            if not atx_result["atx_healthy"]:
                error_detail = atx_result.get("error", "Unknown")
                if atx_result.get("repaired"):
                    notifier.status("atx_repaired", "UIAutomator2 agent repaired successfully")
                else:
                    logger.warning(f"ATX repair failed: {error_detail} - continuing anyway")
                    notifier.log(
                        "warning",
                        f"ATX repair failed ({error_detail}) but continuing - workflow may still work",
                    )

        if not app.is_installed():
            notifier.error("Instagram is not installed on this device", error_code="INSTAGRAM_NOT_INSTALLED")
            return False

        if not app.restart():
            notifier.error("Failed to launch Instagram", error_code="INSTAGRAM_LAUNCH_FAILED")
            return False

        notifier.status("instagram_ready", "Instagram launched successfully")
        return True

    except Exception as e:
        error_msg = str(e)
        if "uiautomator" in error_msg.lower() or "atx" in error_msg.lower():
            notifier.error(f"UIAutomator2 connection failed: {error_msg}", error_code="ATX_AGENT_FAILED")
        else:
            notifier.error(f"Failed to launch Instagram: {error_msg}", error_code="INSTAGRAM_LAUNCH_FAILED")
        logger.exception("Instagram launch failed")
        return False


__all__ = ["LoggingSessionNotifier", "start_instagram_session"]
