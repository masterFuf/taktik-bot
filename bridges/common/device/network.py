"""Network reset facade for bridge device runtimes."""

import time
from dataclasses import dataclass
from typing import Literal

from loguru import logger

from bridges.common.device.network_probe import get_device_external_ip, read_public_ip
from bridges.common.device.network_reset import (
    reset_airplane_cell,
    reset_airplane_mode,
    reset_mobile_data,
)

#: How the rotation ended.
#:
#: - ``verified``     the public IP demonstrably changed;
#: - ``unchanged``    the SAME readable IP came back after every attempt — positive PROOF of failure;
#: - ``unverifiable`` no probe could read the IP, so nothing is known either way.
#:
#: These three must never be collapsed into a boolean. Blocking a run needs proof of failure
#: (``unchanged``), not absence of proof (``unverifiable``) — otherwise a phone whose shell has no
#: HTTP tool could never run at all.
NetworkResetVerdict = Literal["verified", "unchanged", "unverifiable"]

MAX_ROTATION_ATTEMPTS = 3
RETRY_COOLDOWN_SECONDS = 5.0

_STRATEGIES = {
    "data": reset_mobile_data,
    "airplane": reset_airplane_mode,
    "airplane_cell": reset_airplane_cell,
}


@dataclass(frozen=True)
class NetworkResetOutcome:
    """Result of a rotation request, detailed enough for the caller to explain a refusal."""

    verdict: NetworkResetVerdict
    method: str
    old_ip: str | None
    new_ip: str | None
    attempts: int
    #: True when the reset commands themselves ran through (radio state changed as asked).
    commands_ok: bool

    @property
    def ip_changed(self) -> bool:
        return self.verdict == "verified"

    @property
    def should_block_run(self) -> bool:
        """A rotation the user explicitly asked for that provably did not happen."""
        return self.verdict == "unchanged" or not self.commands_ok

    def describe(self) -> str:
        """Short human reason, for a bridge error message or a log line."""
        if self.verdict == "verified":
            return f"IP rotated {self.old_ip} -> {self.new_ip} ({self.method})"
        if self.verdict == "unchanged":
            return (
                f"the IP stayed at {self.old_ip} after {self.attempts} reset(s) using '{self.method}'"
                + (
                    " — a mobile data toggle does not rotate the IP on this carrier, try the"
                    " cell-airplane method"
                    if self.method == "data"
                    else " — this SIM appears to hand out a sticky/CGNAT IP"
                )
            )
        if not self.commands_ok:
            return f"the network reset commands did not take effect on the device ({self.method})"
        return f"the public IP could not be read, so the rotation could not be verified ({self.method})"


def perform_network_reset(device_id: str, method: str = "data", ipc=None) -> NetworkResetOutcome:
    """
    Rotate the device's public IP and VERIFY the result.

    Retries up to `MAX_ROTATION_ATTEMPTS` while the same readable IP keeps coming back: the point of
    the option the user ticked is a different IP, so reporting success without checking is the one
    thing this must not do.

    Args:
        device_id: ADB device serial.
        method: "data", "airplane" or "airplane_cell".
        ipc: Optional IPC instance to send status messages.

    Returns:
        The outcome. Callers that offered the option to the user must refuse to start the run when
        `should_block_run` is set.
    """
    strategy = _STRATEGIES.get(method)
    if strategy is None:
        logger.warning(f"Unknown network reset method '{method}', falling back to mobile data")
        method = "data"
        strategy = reset_mobile_data

    if ipc:
        ipc.status("resetting_network", "Reading current IP...")

    old_ip = read_public_ip(device_id)
    logger.info(f"Current IP: {old_ip or 'unreadable'}")

    commands_ok = False
    new_ip: str | None = None
    attempts = 0

    for attempt in range(1, MAX_ROTATION_ATTEMPTS + 1):
        attempts = attempt
        if ipc:
            suffix = f" (attempt {attempt}/{MAX_ROTATION_ATTEMPTS})" if attempt > 1 else ""
            ipc.status("resetting_network", f"Rotating IP via {method}{suffix}...")

        commands_ok = strategy(device_id)
        new_ip = read_public_ip(device_id)

        if not commands_ok:
            # The radio state did not change as asked — retrying the same command rarely helps.
            break
        if new_ip is None or old_ip is None or new_ip != old_ip:
            break

        logger.warning(f"IP unchanged ({new_ip}) after attempt {attempt}, retrying")
        if attempt < MAX_ROTATION_ATTEMPTS:
            time.sleep(RETRY_COOLDOWN_SECONDS)

    if old_ip and new_ip and old_ip == new_ip:
        verdict: NetworkResetVerdict = "unchanged"
    elif new_ip and (not old_ip or new_ip != old_ip):
        # A readable NEW ip is proof of rotation even when the old one was unreadable.
        verdict = "verified"
    else:
        verdict = "unverifiable"

    outcome = NetworkResetOutcome(
        verdict=verdict,
        method=method,
        old_ip=old_ip,
        new_ip=new_ip,
        attempts=attempts,
        commands_ok=commands_ok,
    )

    if verdict == "verified":
        logger.info(outcome.describe())
    else:
        logger.warning(outcome.describe())

    if ipc:
        if verdict == "verified":
            ipc.log("info", outcome.describe())
        else:
            ipc.log("warning" if verdict == "unverifiable" else "error", outcome.describe())

        # `old_ip`/`new_ip`/`method`/`success` keep their historical shape and meaning for the
        # existing Electron handler; `verdict`/`ip_changed`/`attempts`/`reason` are additive.
        ipc.send(
            "network_reset_complete",
            old_ip=old_ip or "unknown",
            new_ip=new_ip or "unknown",
            method=method,
            success=verdict != "unchanged" and commands_ok,
            ip_changed=outcome.ip_changed,
            verdict=verdict,
            attempts=attempts,
            reason=outcome.describe(),
        )

    return outcome


__all__ = [
    "MAX_ROTATION_ATTEMPTS",
    "NetworkResetOutcome",
    "NetworkResetVerdict",
    "get_device_external_ip",
    "perform_network_reset",
    "reset_airplane_cell",
    "reset_airplane_mode",
    "reset_mobile_data",
]
