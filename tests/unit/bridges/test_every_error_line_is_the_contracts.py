"""The bot prints one form of the `error` line: the contract's (`shared.ERROR_EVENT`).

Its words in `error`, its code in `error_code` (a code of `contract/error_codes.py`), the traceback of
an exception in `traceback`. A second form, the words in `message` and nothing else, came out of the
launcher (no bridge named, a bridge it does not know, its manifest unreadable) and of the entry of the
publish bridges (`report_error_message`: no config file, a file that does not read, a config that is
not an object). The app read both, and a page that names a failure by its code had none to name.

Real processes: the launcher as the app runs it (`python bridges/launcher.py <bridge> <config>`), and
a copy of it beside a manifest that does not read, as a broken build would leave it.
"""

from __future__ import annotations

import shutil

import pytest

from taktik.core.contract.error_codes import BRIDGE_ERROR_PHRASES
from taktik.core.contract.shared import ERROR_EVENT
from unit.paths import CORE

#: The keys the contract declares for the line (`type` aside).
CONTRACT_KEYS = {"type"} | {field.key for field in ERROR_EVENT.fields}
PUBLISH_BRIDGES = ("publish_bridge", "tiktok_publish_bridge", "youtube_upload_bridge")


def _the_contracts_line(proc, errors, code: str) -> dict:
    """The one `error` line of `proc`, in the contract's form, with `code`; the process exited 1."""
    stderr = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 1, stderr[-3000:]
    [line] = errors
    assert set(line) <= CONTRACT_KEYS, line
    assert isinstance(line.get("error"), str) and line["error"], line
    assert line.get("error_code") == code and code in BRIDGE_ERROR_PHRASES, line
    return line


def test_the_launcher_named_no_bridge(run_launcher):
    proc, errors = run_launcher()

    line = _the_contracts_line(proc, errors, "UNKNOWN_BRIDGE")
    assert line["error"].startswith("Usage: ")


def test_the_launcher_does_not_know_the_bridge(run_launcher):
    proc, errors = run_launcher("gate_no_such_bridge")

    line = _the_contracts_line(proc, errors, "UNKNOWN_BRIDGE")
    assert "'gate_no_such_bridge'" in line["error"] and "tiktok_bridge" in line["error"]


def test_the_launchers_manifest_does_not_read(tmp_path, run_launcher):
    build = tmp_path / "build"
    build.mkdir()
    launcher = build / "launcher.py"
    shutil.copyfile(CORE / "bridges" / "launcher.py", launcher)
    (build / "bridges.manifest.json").write_text("{not json", encoding="utf-8")

    proc, errors = run_launcher("tiktok_bridge", launcher=launcher)

    line = _the_contracts_line(proc, errors, "BRIDGE_MANIFEST_UNREADABLE")
    assert line["error"].startswith("Bridge manifest unreadable: JSONDecodeError: "), line
    assert line.get("traceback", "").rstrip().splitlines()[-1].startswith("json.decoder.JSONDecodeError: "), line


@pytest.mark.parametrize("bridge", PUBLISH_BRIDGES)
def test_a_publish_bridge_without_its_config_file(run_launcher, bridge):
    proc, errors = run_launcher(bridge)

    line = _the_contracts_line(proc, errors, "MISSING_CONFIG")
    assert line["error"].startswith("Usage: "), line


@pytest.mark.parametrize("bridge", PUBLISH_BRIDGES)
def test_a_publish_bridge_whose_config_does_not_read(tmp_path, run_launcher, bridge):
    config = tmp_path / "config.json"
    config.write_text("{not json", encoding="utf-8")

    proc, errors = run_launcher(bridge, str(config))

    line = _the_contracts_line(proc, errors, "CONFIG_ERROR")
    assert line["error"].startswith("Failed to read config: "), line


@pytest.mark.parametrize("bridge", PUBLISH_BRIDGES)
def test_a_publish_bridge_whose_config_is_no_object(run_bridge_process, bridge):
    proc, errors = run_bridge_process(bridge, ["not", "an", "object"])

    line = _the_contracts_line(proc, errors, "CONFIG_ERROR")
    assert line["error"] == "Failed to load config: the config must be a JSON object", line
