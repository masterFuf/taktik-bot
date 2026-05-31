"""ADB app lifecycle helpers for TikTok package variants."""

from __future__ import annotations

import subprocess
import time
from typing import Callable


LogFn = Callable[[str, str], None]
RunFn = Callable[..., subprocess.CompletedProcess]
SleepFn = Callable[[float], None]

TIKTOK_SPLASH_ACTIVITY = "com.ss.android.ugc.aweme.splash.SplashActivity"


def launch_app_non_blocking(
    device_id: str,
    package_name: str,
    *,
    run: RunFn = subprocess.run,
    log: LogFn | None = None,
) -> bool:
    """Launch a TikTok package without waiting for an activity to become ready."""
    try:
        run(
            [
                "adb",
                "-s",
                device_id,
                "shell",
                "monkey",
                "-p",
                package_name,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return True
    except Exception:
        return _launch_app_with_am_start(device_id, package_name, run=run, log=log)


def force_stop_app_package(
    device_id: str,
    package_name: str,
    *,
    run: RunFn = subprocess.run,
    log: LogFn | None = None,
) -> bool:
    """Force-stop an Android package; errors stay non-fatal for cleanup paths."""
    try:
        run(
            ["adb", "-s", device_id, "shell", "am", "force-stop", package_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return True
    except Exception as exc:
        _debug(log, f"[force-stop] non-fatal error: {exc}")
        return False


def restart_tiktok_package(
    device,
    device_id: str,
    package_name: str,
    *,
    sleep: SleepFn = time.sleep,
    log: LogFn | None = None,
) -> bool:
    """Force-stop and relaunch a TikTok package through the shared runtime path."""
    try:
        device.app_start(package_name, TIKTOK_SPLASH_ACTIVITY, stop=True)
        return True
    except Exception as exc:
        _debug(log, f"[launch] app_start failed ({exc}), falling back to ADB monkey")
        force_stop_app_package(device_id, package_name, log=log)
        sleep(0.5)
        return launch_app_non_blocking(device_id, package_name, log=log)


def _launch_app_with_am_start(
    device_id: str,
    package_name: str,
    *,
    run: RunFn,
    log: LogFn | None,
) -> bool:
    try:
        run(
            [
                "adb",
                "-s",
                device_id,
                "shell",
                "am",
                "start",
                "-a",
                "android.intent.action.MAIN",
                "-c",
                "android.intent.category.LAUNCHER",
                "-p",
                package_name,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return True
    except Exception as exc:
        _debug(log, f"[launch] non-fatal launch error: {exc}")
        return False


def _debug(log: LogFn | None, message: str) -> None:
    if log:
        log("debug", message)
