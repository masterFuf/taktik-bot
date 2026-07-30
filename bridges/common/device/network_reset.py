"""Network reset strategies for bridge device runtimes.

Each strategy only has to CHANGE THE RADIO STATE and report whether the commands took effect.
Deciding whether the public IP actually rotated is the orchestrator's job (`network.py`) — a
strategy that judged itself would report success on a carrier that hands the same IP back.
"""

import time

from loguru import logger

from bridges.common.device.network_probe import (
    is_airplane_mode_enabled,
    is_mobile_data_enabled,
    wait_for_internet,
)
from taktik.core.shared.device.adb import run_adb_shell

# Default radios list restored when a cell-only airplane cycle cannot read the original one.
_DEFAULT_AIRPLANE_RADIOS = "cell,bluetooth,wifi,nfc,wimax"


def _settle(seconds: float) -> None:
    time.sleep(max(0.0, seconds))


def reset_mobile_data(device_id: str, wait_seconds: float = 8.0) -> bool:
    """
    Toggle mobile data off/on to force a new carrier IP.

    Note for callers: on many carriers (Free among them) a data toggle hands the SAME IP back —
    the radio never detaches. This strategy is kept because it is the fastest and it does rotate on
    some carriers, but `airplane_cell` is the one that reliably detaches the cellular radio.
    """
    try:
        logger.info(f"Resetting mobile data on {device_id} to get a new IP")

        run_adb_shell(device_id, "svc data disable")
        _settle(wait_seconds)
        # The setting is the truth: `svc` prints nothing whether it worked or silently failed.
        if is_mobile_data_enabled(device_id) is True:
            logger.warning(f"Mobile data is still enabled on {device_id} after `svc data disable`")
            return False

        run_adb_shell(device_id, "svc data enable")
        # Wait for the radio to re-attach for real instead of sleeping a fixed few seconds: reading
        # the IP mid-attach is what made a failed rotation look like a successful one.
        if not wait_for_internet(device_id, timeout_seconds=30.0):
            logger.warning(f"{device_id} has no Internet after re-enabling mobile data")
            return False

        logger.info("Mobile data reset complete")
        return True
    except Exception as exc:
        logger.error(f"Network reset failed: {exc}")
        return False


def reset_airplane_mode(device_id: str, wait_seconds: float = 6.0) -> bool:
    """Toggle airplane mode on/off to force a full network reconnect.

    Detaches every radio, so it rotates the IP — but it also tears down a Wi-Fi hotspot. Never use
    it on a phone acting as a router for others; use `reset_airplane_cell` there.
    """
    try:
        logger.info(f"Toggling airplane mode on {device_id} to get a new IP")

        run_adb_shell(device_id, "cmd connectivity airplane-mode enable")
        _settle(wait_seconds)
        if is_airplane_mode_enabled(device_id) is False:
            logger.warning(f"Airplane mode did not turn on on {device_id}")
            return False

        run_adb_shell(device_id, "cmd connectivity airplane-mode disable")
        if not wait_for_internet(device_id, timeout_seconds=40.0):
            logger.warning(f"{device_id} has no Internet after leaving airplane mode")
            return False

        logger.info("Airplane mode reset complete")
        return True
    except Exception as exc:
        logger.error(f"Airplane mode reset failed: {exc}")
        return False


def reset_airplane_cell(device_id: str, wait_seconds: float = 6.0) -> bool:
    """
    Cycle airplane mode on the CELLULAR radio only — the reliable IP rotation.

    `airplane_mode_radios=cell` restricts what airplane mode touches, so cycling it detaches and
    re-attaches the cellular radio (new public IP) without touching Wi-Fi. Proven on device where a
    plain data toggle kept a sticky IP. `airplane_mode_radios` is a standard AOSP setting, so this
    works across carriers and OEMs, with no root and no UI. The original radios list is always
    restored so normal airplane behaviour returns even if the cycle fails.
    """
    original = run_adb_shell(device_id, "settings get global airplane_mode_radios").strip()
    restore = original if original and original != "null" else _DEFAULT_AIRPLANE_RADIOS
    try:
        logger.info(f"Rotating the cellular radio of {device_id} (cell-only airplane cycle)")
        run_adb_shell(device_id, "settings put global airplane_mode_radios cell")
        run_adb_shell(device_id, "cmd connectivity airplane-mode enable")
        _settle(wait_seconds)
        run_adb_shell(device_id, "cmd connectivity airplane-mode disable")
        if not wait_for_internet(device_id, timeout_seconds=40.0):
            logger.warning(f"{device_id} has no Internet after the cell-only airplane cycle")
            return False

        logger.info("Cell radio reset complete")
        return True
    except Exception as exc:
        logger.error(f"Cell-only airplane reset failed: {exc}")
        return False
    finally:
        run_adb_shell(device_id, f"settings put global airplane_mode_radios {restore}")


__all__ = ["reset_airplane_cell", "reset_airplane_mode", "reset_mobile_data"]
