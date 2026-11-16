"""The media proxy launches a mitmdump that runs, and says so when it does not.

`python -m mitmproxy.tools.main mitmdump` imported the module and exited 0 without a word (mitmproxy 11 and 12),
after more than the one second the launch used to wait: the capture "started" a dead process. The reader of its
output stopped at once too, before the manager was marked running. These tests run short real processes on a
free port: no network, no phone.
"""
import json
import socket
import subprocess
import sys
import threading

import pytest
from loguru import logger

from taktik.core.social_media.instagram.media.proxy import proxy_manager
from taktik.core.social_media.instagram.media.proxy.proxy_manager import ProxyManager, mitmdump_command


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def errors():
    lines: list[str] = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="ERROR")
    yield lines
    logger.remove(sink)


def _python_running(code: str) -> list[str]:
    """A stand-in for mitmdump: this interpreter running `code`, with mitmdump's arguments after it."""
    return [sys.executable, "-c", code]


def test_the_command_runs_mitmdump_of_this_interpreter():
    pytest.importorskip("mitmproxy")

    result = subprocess.run(mitmdump_command() + ["--version"], capture_output=True, text=True, timeout=60)

    assert result.returncode == 0, result.stderr
    assert "Mitmproxy:" in result.stdout


def test_the_frozen_engine_runs_the_mitmdump_of_the_path(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(proxy_manager.shutil, "which", lambda name: f"/opt/tools/{name}")

    assert mitmdump_command() == ["/opt/tools/mitmdump"]


def test_no_mitmdump_anywhere_is_a_failed_start_that_says_why(monkeypatch, errors):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(proxy_manager.shutil, "which", lambda name: None)

    assert ProxyManager(proxy_port=_free_port())._start_mitmproxy() is False
    assert any("mitmdump not found" in line for line in errors)


def test_a_mitmdump_that_dies_at_start_is_a_failed_start_with_its_exit_code_and_error(monkeypatch, errors):
    # Dies after 1.5 s: longer than the one second the launch used to wait, like the silent `-m` form.
    dying = "import sys, time; time.sleep(1.5); sys.stderr.write('Error: address already in use'); sys.exit(3)"
    monkeypatch.setattr(proxy_manager, "mitmdump_command", lambda: _python_running(dying))
    port = _free_port()

    assert ProxyManager(proxy_port=port)._start_mitmproxy() is False

    said = "\n".join(errors)
    assert "exit code 3" in said
    assert "Error: address already in use" in said
    assert f"-p {port}" in said


def test_a_taken_port_is_a_failed_start(errors):
    with socket.socket() as other:
        other.bind(("127.0.0.1", 0))
        other.listen()
        port = other.getsockname()[1]

        assert ProxyManager(proxy_port=port)._start_mitmproxy() is False

    assert any(f"port {port} is already taken" in line for line in errors)


def test_a_listening_mitmdump_is_started_and_its_first_lines_are_read(monkeypatch):
    # Writes an addon line before it opens its port, as the addon may, then serves until stopped.
    capture = json.dumps({"type": "cdn_capture", "image_type": "post", "size": 2048})
    listening = (
        "import socket, sys, time\n"
        f"print({capture!r}, flush=True)\n"
        "server = socket.socket()\n"
        "server.bind(('127.0.0.1', int(sys.argv[sys.argv.index('-p') + 1])))\n"
        "server.listen()\n"
        "time.sleep(60)\n"
    )
    monkeypatch.setattr(proxy_manager, "mitmdump_command", lambda: _python_running(listening))
    received: list[dict] = []
    got_one = threading.Event()

    def on_message(message: dict) -> None:
        received.append(message)
        got_one.set()

    manager = ProxyManager(proxy_port=_free_port(), on_message=on_message)
    try:
        assert manager.start() is True
        assert got_one.wait(timeout=10)
    finally:
        manager.stop()

    assert received == [{"type": "cdn_capture", "image_type": "post", "size": 2048}]
