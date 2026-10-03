"""The door to the phone's shell: every `adb shell` of the engine goes through here.

What the phone receives is not what the caller wrote. `adb shell a b c` joins its arguments with
spaces and sends ONE line, without quoting anything; the phone's shell (`sh`) then splits that line
again, expands `$`, runs `|`, `&`, `;` and `>`. So `["sh", "-c", "ping -c 3 1.1.1.1"]` reached the
phone as `sh -c ping -c 3 1.1.1.1` (ping with no argument: every network probe answered nothing for
months), and a password `Pa$$word` typed through `input text "..."` became `Pa<pid>word`.

The rule, one for the whole engine (and the app's door, `electron/utils/adb.ts`, applies the same):

* a LIST of words: each word reaches the phone as one word, whatever it holds (spaces, quotes,
  `$`, `&`). The door quotes them the POSIX way (`shlex.join`), as the phone's shell reads them;
* a STRING: the line itself, read by the phone's shell as written. Pipes, redirections and quotes
  are then the caller's; a value put into such a line by interpolation is the defect this door
  exists to remove (`python scripts/audits/audit_adb_calls.py` counts them, a count that only goes
  down).

`device_command_line` says which line the phone reads; `adb_shell_argv` which arguments adb is
launched with. Both are pure, so a test asserts what the phone RECEIVES, not the caller's intent.
"""

import shlex
import subprocess
import time
from typing import List, Optional, Sequence, Union

from loguru import logger

#: A command for the phone's shell: a list of words, or a line written for its shell.
DeviceCommand = Union[str, Sequence[str]]


def device_command_line(command: DeviceCommand) -> str:
    """The line the phone's shell reads for `command` (see the module's rule)."""
    if isinstance(command, str):
        return command
    return shlex.join(command)


def adb_shell_argv(device_id: Optional[str], command: DeviceCommand, adb_command: str = "adb") -> List[str]:
    """The arguments adb is launched with: the line goes as ONE argument, so adb has nothing to join.

    No serial (`None` or "") leaves `-s` out: adb then talks to the only phone connected.
    """
    serial = ["-s", device_id] if device_id else []
    return [adb_command, *serial, "shell", device_command_line(command)]


def run_adb_shell_process(
    device_id: Optional[str],
    command: DeviceCommand,
    *,
    adb_command: str = "adb",
    text: bool = True,
    timeout: int = 10,
    encoding: str | None = None,
    errors: str | None = None,
) -> subprocess.CompletedProcess:
    """
    Execute an ADB shell command and return the subprocess result.

    Use this when callers need return code or stderr, for example app lifecycle
    cleanup and package inspection.
    """
    kwargs = {
        "capture_output": True,
        "text": text,
        "timeout": timeout,
    }
    if encoding is not None:
        kwargs["encoding"] = encoding
    if errors is not None:
        kwargs["errors"] = errors

    # One adb round trip for the device io meter, with the gesture it makes (a force-stop, a key).
    from taktik.core.shared.telemetry.device_io import METER

    line = device_command_line(command)
    started_at = time.perf_counter()
    failed = False
    try:
        return subprocess.run(adb_shell_argv(device_id, line, adb_command), **kwargs)
    except BaseException:
        failed = True
        raise
    finally:
        METER.record_shell((time.perf_counter() - started_at) * 1000.0, failed, command=line)


def run_adb_shell(device_id: str, command: DeviceCommand) -> str:
    """
    Execute an ADB shell command using adbutils, with subprocess fallback.

    Args:
        device_id: ADB device serial/ID.
        command: words or a line for the phone's shell (the module's rule), without `adb shell`.

    Returns:
        Command output as string, or an empty string on error.
    """
    # One adb round trip for the device io meter (M1): typing, IME and app checks go this way.
    from taktik.core.shared.telemetry.device_io import METER

    line = device_command_line(command)
    started_at = time.perf_counter()
    try:
        return _run_adb_shell(device_id, line)
    finally:
        METER.record_shell((time.perf_counter() - started_at) * 1000.0, command=line)


def _run_adb_shell(device_id: str, line: str) -> str:
    try:
        from adbutils import adb

        device = adb.device(serial=device_id)
        # A string goes to the phone as it is (adbutils quotes only a list).
        return device.shell(line)
    except ImportError:
        try:
            result = subprocess.run(
                adb_shell_argv(device_id, line),
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception as exc:
            logger.debug(f"ADB subprocess error: {exc}")
            return ""
    except Exception as exc:
        logger.debug(f"ADB shell error: {exc}")
        return ""


__all__ = [
    "DeviceCommand",
    "adb_shell_argv",
    "device_command_line",
    "run_adb_shell",
    "run_adb_shell_process",
]
