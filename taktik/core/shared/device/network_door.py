"""The network door of a run: a phone without network does not start its run.

Without a route to the Internet, a run reads the phone's cache and records empty profiles as
measures (Pixel 3, 2026-09-28). The door measures the phone's network once its host has prepared
the phone (the connection, the desktop's IP rotation) and before the app starts, and refuses the run
when ping answers « Network is unreachable ».

The door is opened by the core, not by a host: the Instagram launchers (automation, cold DM, scraping,
a DM read, notifications, the Taktik Agent) open it once their host hands them the phone, the TikTok
session start (`start_tiktok_session`) and the TikTok DM outreach launcher before TikTok is touched. The desktop bridges and the CLI cross the same call, so
both refuse a phone without network, with the same motive. Each host only says it its way: the
bridges as an `error` line (`NETWORK_UNREACHABLE`), the CLI on its console.

In Symfony terms: a voter the core consults before the run, not a listener of one host. The measure
itself is the probe's (`network_probe.measure_network_baseline`); this module decides.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from taktik.core.shared.device.network_probe import measure_network_baseline

#: The moment of a run the measure is the baseline of: the network the run starts on.
SESSION_BASELINE = "session_baseline"
#: The measure the desktop's IP rotation takes first: a phone without network has no IP to rotate.
BEFORE_IP_ROTATION = "before_ip_rotation"


class NetworkUnreachableError(RuntimeError):
    """The phone has no route to the Internet: the run did not start.

    `error_code` is the motive the desktop translates (`contract/error_codes.py`); the message names
    it too, so a host that prints the exception (the CLI) says the same motive.
    """

    error_code = "NETWORK_UNREACHABLE"

    def __init__(self, device_id: str):
        self.device_id = device_id
        super().__init__(
            f"{self.error_code}: the phone {device_id} has no network (ping: network is unreachable)"
        )


def open_network_door(device_id: Optional[str], *, moment: str = SESSION_BASELINE) -> Optional[dict]:
    """Measure the phone's network and refuse a phone with no route at all.

    Returns the measure (latency, packet loss), or None when it could not be read: an unreadable
    measure never blocks a run, since a phone whose shell has no ping would never run at all. Raises
    `NetworkUnreachableError` when ping says the phone has no route.

    A readable measure travels as the step `network_probe` (`action` is `moment`) and in the run's
    log: the question « was the network slow? » has a measured answer, kept with the run.
    """
    if not device_id:
        logger.warning("Network door: no device serial, the phone's network was not measured")
        return None
    try:
        baseline = measure_network_baseline(device_id)
    except Exception as exc:  # noqa: BLE001 - a diagnostic that fails never ends a run
        logger.warning(f"Network door: the measure failed on {device_id}, the run goes on: {exc}")
        return None
    if not baseline:
        logger.debug(f"Network door: the measure is unreadable on {device_id}, the run goes on")
        return None
    if baseline.get("unreachable"):
        logger.warning(f"Network door: {device_id} has no route to the Internet, the run does not start")
        raise NetworkUnreachableError(device_id)

    logger.info(
        f"Network baseline: {baseline['rtt_ms']} ms avg, "
        f"{baseline['packet_loss_pct']}% packet loss ({baseline['received']}/3 replies)"
    )
    from taktik.core.shared.telemetry import emit_step

    emit_step(
        "network_probe",
        action=moment,
        target=device_id,
        rtt_ms=baseline["rtt_ms"],
        packet_loss_pct=baseline["packet_loss_pct"],
        replies=baseline["received"],
    )
    return baseline


__all__ = [
    "BEFORE_IP_ROTATION",
    "NetworkUnreachableError",
    "SESSION_BASELINE",
    "open_network_door",
]
