import json
import queue

from bridges.instagram.automation.runtime.decision_client import (
    DesktopProfileDecisionClient,
)


class _BlockingInput:
    def __init__(self):
        self.lines = queue.Queue()

    def readline(self):
        return self.lines.get(timeout=2)


class _ReplyingIpc:
    def __init__(self, input_stream):
        self.input_stream = input_stream
        self.messages = []

    def send(self, msg_type, **payload):
        self.messages.append((msg_type, payload))
        response = {
            "type": "agent_profile_decision_response",
            "requestId": payload["requestId"],
            "ok": True,
            "plan": {"likes": 1},
        }
        self.input_stream.lines.put((json.dumps(response) + "\n").encode())


def test_decision_client_matches_response_to_request():
    input_stream = _BlockingInput()
    ipc = _ReplyingIpc(input_stream)
    client = DesktopProfileDecisionClient(
        ipc=ipc,
        input_stream=input_stream,
        timeout_seconds=0.5,
    )

    response = client.request_plan({"username": "alice"})

    assert response["ok"] is True
    assert response["plan"]["likes"] == 1
    assert ipc.messages[0][0] == "agent_profile_decision_request"
    assert ipc.messages[0][1]["username"] == "alice"
    input_stream.lines.put(b"")


def test_decision_client_converts_send_failure_to_closed_response():
    class _FailingIpc:
        def send(self, *_args, **_kwargs):
            raise BrokenPipeError("closed")

    input_stream = _BlockingInput()
    client = DesktopProfileDecisionClient(
        ipc=_FailingIpc(),
        input_stream=input_stream,
        timeout_seconds=0.1,
    )

    response = client.request_plan({"username": "alice"})

    assert response == {
        "ok": False,
        "error": "desktop decision request could not be sent",
    }
    input_stream.lines.put(b"")
