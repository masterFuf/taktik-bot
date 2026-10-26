"""An Instagram that fails to stop at the end of an automation run is said, never swallowed.

The bridge stops the app when its process ends (`InstagramDesktopRuntime.stop_app`). A failure there
went into an `except Exception: pass`: the run ended as finished and nothing told why Instagram was
still open on the phone.
"""
from __future__ import annotations

from loguru import logger

import bridges.instagram.automation.session as session


def _warnings_of(runtime) -> list[str]:
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), format="{level} {message}", level="WARNING")
    try:
        runtime.stop_app()
    finally:
        logger.remove(handler)
    return [line for line in seen if line.startswith("WARNING")]


class _App:
    def __init__(self, stop):
        self.stop = stop


def test_an_app_that_fails_to_stop_is_said_with_its_cause():
    runtime = session.InstagramDesktopRuntime(device_id="emulator-5554", network_reset={})

    def broken():
        raise OSError("adb gone")

    runtime.app_service = _App(broken)

    warnings = _warnings_of(runtime)

    assert [line for line in warnings if "emulator-5554" in line and "adb gone" in line], warnings


def test_an_app_the_phone_refuses_to_stop_is_said():
    runtime = session.InstagramDesktopRuntime(device_id="emulator-5554", network_reset={})
    runtime.app_service = _App(lambda: False)

    warnings = _warnings_of(runtime)

    assert [line for line in warnings if "emulator-5554" in line], warnings


def test_an_app_that_stops_says_nothing():
    runtime = session.InstagramDesktopRuntime(device_id="emulator-5554", network_reset={})
    runtime.app_service = _App(lambda: True)

    assert _warnings_of(runtime) == []
