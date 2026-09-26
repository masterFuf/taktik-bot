"""`taktik management dm` runs the desktop's DM runtime.

`dm inbox` and `read-all` read the inbox with readers of their own and kept nothing; `dm send` went
through `DMOutreachWorkflow` (a profile visit, then the Message button) and recorded nothing. They
now go through the DM handlers, so a CLI read and reply are the desktop's: clean restart, account
from the inbox header, conversations and replies saved.
"""
import pytest
from click.testing import CliRunner

from instagram_dm_rig import DEVICE_ID, INSTAGRAM


@pytest.fixture(autouse=True)
def no_phone(monkeypatch):
    """No way out to a phone: no process, no socket (adb server), no uiautomator2 connection."""
    import socket
    import subprocess

    def refuse(*_a, **_k):
        raise RuntimeError("no phone in tests")

    for name in ("run", "Popen", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr("uiautomator2.connect", refuse)


@pytest.fixture
def management(igd_rig, monkeypatch):
    from taktik.cli.commands import management_cmds

    class _Instagram:
        def __init__(self, *a, **k):
            pass

        def __getattr__(self, name):
            return lambda *a, **k: igd_rig.calls.append(f"instagram_manager {name}") or True

    monkeypatch.setattr(management_cmds, "InstagramManager", _Instagram)

    class _Manager:
        device = igd_rig.phone

        def __init__(self, *a, **k):
            self.device_id = DEVICE_ID
            igd_rig.device_manager.device = igd_rig.phone

        @staticmethod
        def list_devices():
            return [{"id": DEVICE_ID, "status": "device"}]

        def connect(self, device_id=None):
            return True

        def __getattr__(self, name):
            return getattr(igd_rig.device_manager, name)

    monkeypatch.setattr(management_cmds, "DeviceManager", _Manager)
    return management_cmds.management


def test_dm_inbox_reads_like_the_desktop_and_keeps_what_it_read(igd_rig, management):
    result = CliRunner().invoke(management, ["dm", "inbox", "-d", DEVICE_ID, "--limit", "5"])

    assert result.exit_code == 0, result.output
    assert igd_rig.calls.index(f"stop {INSTAGRAM}") < igd_rig.calls.index("navigate_to_dm_inbox")
    assert [row["partner_username"] for row in igd_rig.db if row["write"] == "conversation"] == ["dave"]
    assert "dave" in result.output


def test_dm_send_replies_in_the_conversation_and_records_it(igd_rig, management):
    igd_rig.phone.screen = "inbox"
    result = CliRunner().invoke(management, ["dm", "send", "-d", DEVICE_ID, "--to", "dave", "-m", "Yes"])

    assert result.exit_code == 0, result.output
    assert "open_conversation dave" in igd_rig.calls and "send_message Yes" in igd_rig.calls
    assert [row["write"] for row in igd_rig.db] == ["sent"]


def test_dm_send_to_a_conversation_it_cannot_find_says_so(igd_rig, management):
    igd_rig.phone.screen = "inbox"
    result = CliRunner().invoke(management, ["dm", "send", "-d", DEVICE_ID, "--to", "nobody", "-m", "Hi"])

    assert result.exit_code == 1
    assert "Cannot find conversation with nobody" in result.output
