import subprocess

from taktik.core.social_media.tiktok.services.runtime.app_control import (
    force_stop_app_package,
    launch_app_non_blocking,
)


def completed() -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")


def test_launch_app_non_blocking_uses_monkey_launcher():
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return completed()

    assert launch_app_non_blocking("device-1", "com.tiktok", run=fake_run)

    assert calls[0][0] == [
        "adb",
        "-s",
        "device-1",
        "shell",
        "monkey",
        "-p",
        "com.tiktok",
        "-c",
        "android.intent.category.LAUNCHER",
        "1",
    ]
    assert calls[0][1]["timeout"] == 5


def test_launch_app_non_blocking_falls_back_to_am_start_when_monkey_fails():
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if len(calls) == 1:
            raise TimeoutError("monkey timeout")
        return completed()

    assert launch_app_non_blocking("device-1", "com.tiktok", run=fake_run)

    assert calls[1] == [
        "adb",
        "-s",
        "device-1",
        "shell",
        "am",
        "start",
        "-a",
        "android.intent.action.MAIN",
        "-c",
        "android.intent.category.LAUNCHER",
        "-p",
        "com.tiktok",
    ]


def test_launch_app_non_blocking_returns_false_when_both_launchers_fail():
    messages = []

    def fake_run(_command, **_kwargs):
        raise OSError("adb unavailable")

    assert not launch_app_non_blocking(
        "device-1",
        "com.tiktok",
        run=fake_run,
        log=lambda level, message: messages.append((level, message)),
    )
    assert messages == [("debug", "[launch] non-fatal launch error: adb unavailable")]


def test_force_stop_app_package_uses_am_force_stop():
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return completed()

    assert force_stop_app_package("device-1", "com.tiktok", run=fake_run)

    assert calls[0][0] == [
        "adb",
        "-s",
        "device-1",
        "shell",
        "am",
        "force-stop",
        "com.tiktok",
    ]
    assert calls[0][1]["timeout"] == 10
