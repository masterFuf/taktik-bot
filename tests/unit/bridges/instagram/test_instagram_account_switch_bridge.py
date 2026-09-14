from bridges.instagram.account.runtime.bridge import AccountBridge


class _Workflow:
    instances = []

    def __init__(self, device, device_id, **kwargs):
        self.device = device
        self.device_id = device_id
        self.kwargs = kwargs
        self.calls = []
        self.instances.append(self)

    def execute(self, target):
        self.calls.append(("switch_account", target))
        return {
            "success": False,
            "message": "not verified",
            "error_type": "verification_failed",
            "switched_to": None,
            "relogin_required": False,
            "detected_accounts": ["previous", "target"],
            "requested_username": "target",
            "active_username": "previous",
            "already_active": False,
            "attempts": 2,
            "failure_stage": "verify",
            "failure_category": "switch_verification_failed",
            "state_known": True,
        }


def test_instagram_bridge_propagates_structured_switch_failure(monkeypatch):
    _Workflow.instances = []
    bridge = AccountBridge(
        {
            "workflowType": "switch_account",
            "deviceId": "device-1",
            "targetUsername": "@target",
        }
    )
    bridge._prepare_runtime_session = lambda: object()
    bridge._switch_workflow_factory = _Workflow
    events = []
    monkeypatch.setattr(
        "bridges.instagram.account.runtime.switch.send_message",
        lambda event, **payload: events.append((event, payload)),
    )

    assert bridge.run() == 1
    assert _Workflow.instances[0].calls == [("switch_account", "@target")]
    event, payload = events[-1]
    assert event == "account_result"
    assert payload["error_type"] == "verification_failed"
    assert payload["active_username"] == "previous"
    assert payload["attempts"] == 2
    assert payload["failure_stage"] == "verify"
    assert payload["state_known"] is True
