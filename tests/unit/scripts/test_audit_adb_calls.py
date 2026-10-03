"""The adb-call ratchet counts adb launched by hand and lines built by interpolation, nothing else."""

import sys

import pytest
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/audits"))

import audit_adb_calls as audit  # noqa: E402


def _kinds(source: str):
    return [finding.kind for finding in audit.scan_source(source)]


@pytest.mark.parametrize("source", [
    # The TikTok deep link before the door: the link cut at its `&` on the phone.
    'subprocess.run(base + ["shell", "am", "start", "-d", url])\nbase = ["adb"] + ["-s", serial]',
    'subprocess.run(["adb", "-s", serial, "shell", "pm", "list", "packages"])',
    "cmd = ('adb.exe', 'devices')",
    'run(["adb", "-s", d, "shell", "monkey", "-p", pkg], capture_output=True)',
])
def test_adb_launched_by_hand_is_counted(source):
    assert _kinds(source) == [audit.ARGV]


@pytest.mark.parametrize("source", [
    # The login's rescue before the door: the `$` of a password expanded by the phone's shell.
    "self._run_adb_shell(serial, f'input text \"{safe_text}\"')",
    "run_adb_shell(device_id, f'ime set {ime}')",
    "run_adb_shell_process(device_id, 'pm path ' + package)",
    "self.device.shell('dumpsys account | grep -i ' + name)",
    "device.shell(f'am start -d \"{url}\" {pkg}')",
    "d.shell2('getprop %s' % key)",
    "device.shell('pm list packages {}'.format(pkg))",
    "run_adb_shell(device_id, command=f'getprop {prop}')",
])
def test_a_line_built_by_interpolation_is_counted(source):
    assert _kinds(source) == [audit.INTERPOLATED]


@pytest.mark.parametrize("source", [
    'self._run_adb_shell(serial, ["input", "text", text])',
    'run_adb_shell_process(serial, ["am", "start", "-d", url])',
    "run_adb_shell(device_id, 'dumpsys input_method')",
    "self.device.shell(['am', 'start', '-n', component])",
    "self.device.shell('dumpsys window windows | grep mCurrentFocus')",
    "device.shell(f'getprop ro.build.version.sdk')",
    'names = ["shell", "adb"]',
    "ADB = frozenset({'adb', 'adb.exe'})",
    "subprocess.run(['python', 'x.py'])",
    "run_adb_shell(line)",
])
def test_the_door_with_words_or_a_constant_line_is_not_counted(source):
    assert _kinds(source) == []


def test_the_door_itself_is_not_scanned():
    assert audit.DOOR not in audit.scan_repository()
    assert (CORE / audit.DOOR).is_file()
