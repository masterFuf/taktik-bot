"""The door to the phone's shell (`taktik.core.shared.device.adb`): what the phone RECEIVES.

`adb shell` joins its arguments with spaces and the phone's shell splits the line again, so these
tests replay that trip (`unit.android_shell.adb_line` and `phone_words`) on the arguments adb is
really launched with, never on the caller's intent: the class of defect they guard is invisible
to a test that only looks at what the caller passed.
"""

import subprocess
import sys
import types

import pytest

from taktik.core.shared.device import adb, network_probe
from unit.android_shell import ShellWouldRewrite, adb_line, phone_words

# Words that the phone's shell would rewrite if they were not quoted: a password, a link with a
# query, a file name, a double space, a hash, a quote of each kind, a backslash, an empty word.
TRICKY_WORDS = [
    "Pa$$word",
    "it's",
    'pa"ss',
    "back\\slash",
    "a  b",
    "https://www.tiktok.com/@creator/video/7412345678901234567?is_from_webapp=1&sender_device=pc",
    "2026-06-11-010830653 (1).mp4",
    "#hashtag",
    "~home",
    "*.jpg",
    "`id`",
    "$(reboot)",
    "",
    "é ü 日本",
]


class Recorder:
    """Stands for `subprocess.run`: keeps the arguments adb is launched with."""

    def __init__(self, stdout=""):
        self.argv = []
        self.stdout = stdout

    def __call__(self, argv, **kwargs):
        self.argv.append(list(argv))
        return subprocess.CompletedProcess(argv, 0, self.stdout, "")


@pytest.fixture
def adb_run(monkeypatch):
    recorder = Recorder()
    monkeypatch.setattr(adb.subprocess, "run", recorder)
    return recorder


@pytest.mark.parametrize("word", TRICKY_WORDS)
def test_a_list_reaches_the_phone_word_for_word(word):
    words = ["input", "text", word]
    assert phone_words(adb.device_command_line(words)) == words


def test_a_string_is_the_line_itself():
    line = "dumpsys activity activities | grep -m1 mResumedActivity"
    assert adb.device_command_line(line) == line


def test_adb_gets_the_line_as_one_argument_so_it_has_nothing_to_join():
    argv = adb.adb_shell_argv("SERIAL", ["sh", "-c", "ping -c 3 1.1.1.1"])
    assert argv[:4] == ["adb", "-s", "SERIAL", "shell"]
    assert len(argv) == 5
    assert phone_words(adb_line(argv)) == ["sh", "-c", "ping -c 3 1.1.1.1"]


def test_no_serial_talks_to_the_only_phone():
    assert adb.adb_shell_argv("", ["getprop"]) == ["adb", "shell", "getprop"]
    assert adb.adb_shell_argv(None, ["getprop"]) == ["adb", "shell", "getprop"]


def test_run_adb_shell_process_launches_adb_with_the_quoted_line(adb_run):
    adb.run_adb_shell_process("SERIAL", ["am", "start", "-d", TRICKY_WORDS[5]])
    (argv,) = adb_run.argv
    assert phone_words(adb_line(argv)) == ["am", "start", "-d", TRICKY_WORDS[5]]


def test_the_fallback_without_adbutils_keeps_the_line_whole(monkeypatch, adb_run):
    """Without adbutils the line went through `str.split()`: its double spaces were lost."""
    monkeypatch.setitem(sys.modules, "adbutils", None)
    adb.run_adb_shell("SERIAL", "input text 'a  b'")
    (argv,) = adb_run.argv
    assert adb_line(argv) == "input text 'a  b'"


def test_adbutils_receives_the_line_of_a_list(monkeypatch):
    received = []

    class Device:
        def shell(self, line):
            received.append(line)
            return "ok"

    fake = types.SimpleNamespace(adb=types.SimpleNamespace(device=lambda serial: Device()))
    monkeypatch.setitem(sys.modules, "adbutils", fake)
    assert adb.run_adb_shell("SERIAL", ["input", "text", "Pa$$word"]) == "ok"
    assert phone_words(received[0]) == ["input", "text", "Pa$$word"]


def test_the_network_probe_pipeline_reaches_the_phone_shell_whole(adb_run):
    """`sh -c <pipeline>`: three words. Unquoted, the phone ran `sh -c printf` and nothing else."""
    pipeline = network_probe._IP_PROBE_COMMANDS[0]
    network_probe._shell("SERIAL", pipeline)
    (argv,) = adb_run.argv
    assert phone_words(adb_line(argv)) == ["sh", "-c", pipeline]


def test_the_reader_refuses_a_line_the_shell_would_rewrite():
    """The fake phone is strict: an unquoted `&`, a `$` in double quotes, an unquoted `|`."""
    for line in ('input text "Pa$$word"', "am start -d https://x/?a=1&b=2 pkg", "dumpsys package x | grep v"):
        with pytest.raises(ShellWouldRewrite):
            phone_words(line)
    assert phone_words("""input text "it\\'s" """) == ["input", "text", "it\\'s"]
