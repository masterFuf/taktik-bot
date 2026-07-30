"""Network inspection helpers for bridge device runtimes."""

import re
import time

from loguru import logger

from taktik.core.shared.device.adb import run_adb_shell, run_adb_shell_process

_IPV4_RE = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_TRACE_IP_RE = re.compile(r"(?:^|[\r\n])ip=(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")

# Public-IP probes, in the order that actually works on the fleet.
#
# Field finding (Samsung SM-A105FN, Android 11): these phones ship NEITHER `curl` NOR `toybox wget`.
# The only HTTP-capable tool is `toybox nc`, which does resolve DNS. Cloudflare's 1.1.1.1 answers a
# 301 to HTTPS on port 80, so it is useless here; the services below serve the caller IP in CLEAR
# text on port 80. Phones that DO ship curl (some Pixels) are covered by the HTTPS attempts after.
# The same cascade already runs on the Electron side — keep the two in step.
_IP_PROBE_COMMANDS = (
    "printf 'GET /ip HTTP/1.1\\r\\nHost: ifconfig.me\\r\\nConnection: close\\r\\n\\r\\n'"
    " | toybox nc -w 8 ifconfig.me 80 2>/dev/null",
    "printf 'GET / HTTP/1.1\\r\\nHost: icanhazip.com\\r\\nConnection: close\\r\\n\\r\\n'"
    " | toybox nc -w 8 icanhazip.com 80 2>/dev/null",
    "printf 'GET / HTTP/1.1\\r\\nHost: api.ipify.org\\r\\nConnection: close\\r\\n\\r\\n'"
    " | toybox nc -w 8 api.ipify.org 80 2>/dev/null",
    "curl -s --max-time 8 https://1.1.1.1/cdn-cgi/trace 2>/dev/null",
    "curl -s --max-time 8 https://api.ipify.org 2>/dev/null",
    "wget -qO- --timeout=8 https://api.ipify.org 2>/dev/null",
)


def _shell(device_id: str, command: str, timeout: int = 15) -> str:
    """
    Run a shell command that may contain pipes, quotes or redirections.

    `run_adb_shell` splits the command on whitespace in its subprocess fallback, which shreds a
    `printf ... | toybox nc ...` pipeline. Going through `sh -c` keeps the command as one argument
    so the DEVICE shell parses it, whichever transport adb uses.
    """
    try:
        result = run_adb_shell_process(device_id, ["sh", "-c", command], timeout=timeout)
        return f"{result.stdout or ''}\n{result.stderr or ''}".strip()
    except Exception as exc:
        logger.debug(f"ADB shell command failed on {device_id}: {exc}")
        return ""


def _is_private_or_reserved(value: str) -> bool:
    """True for addresses that cannot be a public egress IP (LAN, loopback, probe target)."""
    return (
        value.startswith("10.")
        or value.startswith("127.")
        or value.startswith("192.168.")
        or bool(re.match(r"^172\.(1[6-9]|2\d|3[01])\.", value))
        or value in {"1.1.1.1", "0.0.0.0", "255.255.255.255"}
    )


def _extract_public_ip(output: str) -> str | None:
    """Pull a public IPv4 out of a probe response (`ip=<addr>` trace line, or a bare address)."""
    if not output:
        return None
    trace = _TRACE_IP_RE.search(output)
    if trace and not _is_private_or_reserved(trace.group(1)):
        return trace.group(1)
    for candidate in _IPV4_RE.findall(output):
        if not _is_private_or_reserved(candidate):
            return candidate
    return None


def read_public_ip(device_id: str, attempts: int = 2) -> str | None:
    """
    Read the device's public egress IP, or None when no probe could answer.

    None means "unreadable", NOT "unchanged" — the caller must keep the two apart, because
    refusing to run on an unreadable IP would block every phone whose shell has no HTTP tool.
    """
    for attempt in range(max(1, attempts)):
        for command in _IP_PROBE_COMMANDS:
            ip = _extract_public_ip(_shell(device_id, command))
            if ip:
                return ip
        if attempt == 0:
            logger.debug(f"No public IP probe answered on {device_id}, retrying once")
    return None


def get_device_external_ip(device_id: str) -> str:
    """Public IP of the device, or the literal "unknown" (legacy string contract)."""
    return read_public_ip(device_id) or "unknown"


def wait_for_internet(device_id: str, timeout_seconds: float = 30.0) -> bool:
    """
    Block until the device can actually reach the Internet again, or the timeout expires.

    Both signals are required: a default route (the radio re-attached) AND a ping that comes back
    (the route carries traffic). A reset that only waits a fixed number of seconds reads the IP
    while the modem is still attaching — which is exactly how a rotation gets misreported.
    """
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    while True:
        route = _shell(device_id, "ip route get 1.1.1.1", timeout=12)
        has_route = bool(re.search(r"\bdev\s+\S+", route))
        if has_route:
            ping = _shell(device_id, "ping -c 1 -W 2 1.1.1.1", timeout=12)
            if re.search(r"time[=<][\d.]+\s*ms", ping, re.IGNORECASE) or "1 received" in ping:
                return True
        if time.monotonic() >= deadline:
            logger.warning(f"{device_id} did not recover Internet access within {timeout_seconds}s")
            return False
        time.sleep(3)


def _read_global_flag(device_id: str, key: str) -> bool | None:
    """Read a `settings global` boolean; None when the value is absent or unparsable."""
    raw = run_adb_shell(device_id, f"settings get global {key}").strip()
    if raw == "1":
        return True
    if raw == "0":
        return False
    return None


def is_mobile_data_enabled(device_id: str) -> bool | None:
    """State of mobile data, read from the setting rather than guessed from `svc` output.

    `svc data disable/enable` prints nothing on success AND nothing when it silently fails, so
    scanning its output for the word "error" proves nothing. This is the actual state.
    """
    return _read_global_flag(device_id, "mobile_data")


def is_airplane_mode_enabled(device_id: str) -> bool | None:
    """State of airplane mode, read from the setting (same reasoning as mobile data)."""
    return _read_global_flag(device_id, "airplane_mode_on")


__all__ = [
    "get_device_external_ip",
    "is_airplane_mode_enabled",
    "is_mobile_data_enabled",
    "read_public_ip",
    "wait_for_internet",
]
