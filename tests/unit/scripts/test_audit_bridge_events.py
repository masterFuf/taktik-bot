"""The bridge events census sees every type the bot writes on stdout, and only those.

The app gate `npm run bridge:events` compares this census with what the app reads; a type the
census misses is a type the gate cannot hold.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import audit_bridge_events as audit  # noqa: E402


def _types(source: str) -> tuple[set[str], list[str]]:
    emitted, unresolved = audit.scan_source(source, "x.py")
    return set(emitted), unresolved


@pytest.mark.parametrize("source, expected", [
    ('ipc.send("post_captured", url=u)', {"post_captured"}),
    ('self.ipc.send("comment", username=a)', {"comment"}),
    ('send_message("debug_result", **result)', {"debug_result"}),
    ('notify(notifier, "unfollow_stats", stats=s)', {"unfollow_stats"}),
    ('_emit(notifier, "send", "notifications_result", success=True)', {"notifications_result"}),
    ('_emit(notifier, "dm_progress", 1, 2)', set()),
    ('print(json.dumps({"type": "sync_step", "step": "following"}), flush=True)', {"sync_step"}),
    ('emit({"type": "account_detected", "account_username": a})', {"account_detected"}),
    ('def f():\n    msg = {"type": "session_stop"}\n    print(json.dumps(msg))', {"session_stop"}),
    ('items.append({"type": "sticker", "text": t})', set()),
    ('def f():\n    return {"type": "feed", "limit": 3}', set()),
    ('content = [{"type": "text", "text": prompt}]', set()),
    ('EVENT = "new_follower"\ndef f(ipc):\n    ipc.send(EVENT)', {"new_follower"}),
])
def test_emitted_types(source, expected):
    types, unresolved = _types(source)
    assert types == expected
    assert unresolved == []


def test_a_type_read_from_a_table_of_callbacks():
    source = (
        "def attach(workflow, notifier):\n"
        "    forwarded = (\n"
        "        ('set_on_new_follower_callback', 'new_follower', 'follower'),\n"
        "        ('set_on_request_result_callback', 'request_result', 'result'),\n"
        "    )\n"
        "    for setter_name, event_type, argument in forwarded:\n"
        "        getattr(workflow, setter_name)(\n"
        "            lambda item, event_type=event_type, argument=argument: notify(notifier, event_type, **{argument: item})\n"
        "        )\n"
    )
    assert _types(source) == ({"new_follower", "request_result"}, [])


def test_a_forwarder_passes_its_parameter_on():
    source = "class IPC:\n    def send(self, msg_type, **kw):\n        message = {'type': msg_type, **kw}\n        os.write(1, message)\n"
    assert _types(source) == (set(), [])


def test_a_type_it_cannot_read_is_reported():
    types, unresolved = _types("def run(ipc, kind):\n    ipc.send(kind)\n")
    assert types == set()
    assert unresolved == ["x.py:2: kind"]


def test_the_bot_tree_is_fully_readable():
    emitted, unresolved = audit.scan()
    assert unresolved == []
    for known in ("notifications_result", "ai_spend", "profile_captured", "session_stop", "debug_result", "agent_status"):
        assert known in emitted
    for retired in ("activity_row", "hello_sent", "suggested_followed", "cdn_captured", "session_closed"):
        assert retired not in emitted
