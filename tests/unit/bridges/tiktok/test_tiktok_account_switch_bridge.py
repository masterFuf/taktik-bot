from bridges.tiktok.account.runtime.bridge import TikTokAccountBridge


class _Workflow:
    instances = []

    def __init__(self, device, device_id, *, android_user_id=None, notifier=None, **_kwargs):
        self.device = device
        self.device_id = device_id
        self.android_user_id = android_user_id
        self.notifier = notifier
        self.calls = []
        self.instances.append(self)

    def switch_account(self, target):
        self.calls.append(("switch_account", target))
        return {"success": True, "active_username": target, "already_active": False}

    def list_accounts(self):
        self.calls.append(("list_accounts",))
        return {"success": True, "active_username": "one", "accounts": ["one", "two"]}


def _bridge(config):
    bridge = TikTokAccountBridge(config)
    bridge._prepare_device = lambda: object()
    bridge._switch_workflow_factory = _Workflow
    return bridge


def test_bridge_dispatches_switch_account_with_external_payload_fields(monkeypatch):
    _Workflow.instances = []
    events = []
    monkeypatch.setattr(
        "bridges.tiktok.account.runtime.account_switch.send_message",
        lambda event, **payload: events.append((event, payload)),
    )
    bridge = _bridge({
        "workflowType": "switch_account",
        "deviceId": "R9HN70LZYEJ",
        "targetUsername": "@toki6913",
        "androidUserId": 0,
    })

    assert bridge.run() == 0
    workflow = _Workflow.instances[0]
    assert workflow.device_id == "R9HN70LZYEJ"
    assert workflow.android_user_id == 0
    assert workflow.calls == [("switch_account", "@toki6913")]
    assert events[-1][0] == "account_result"
    assert events[-1][1]["active_username"] == "@toki6913"


def test_bridge_dispatches_list_accounts_without_a_target(monkeypatch):
    _Workflow.instances = []
    events = []
    monkeypatch.setattr(
        "bridges.tiktok.account.runtime.account_switch.send_message",
        lambda event, **payload: events.append((event, payload)),
    )
    bridge = _bridge({"workflowType": "list_accounts", "deviceId": "device-1"})

    assert bridge.run() == 0
    assert _Workflow.instances[0].calls == [("list_accounts",)]
    assert events[-1][1]["accounts"] == ["one", "two"]


def test_account_bridge_refuses_a_different_android_user_before_launching(monkeypatch):
    bridge = TikTokAccountBridge({
        "workflowType": "list_accounts",
        "deviceId": "device-1",
        "androidUserId": 10,
    })
    device = type("Device", (), {"shell": lambda self, command: "0"})()
    bridge._setup_database = lambda: True
    bridge._connect_device = lambda: device
    bridge._launch_tiktok = lambda: (_ for _ in ()).throw(AssertionError("must not launch wrong user"))
    errors = []
    monkeypatch.setattr(
        "bridges.tiktok.account.runtime.account_session.send_error",
        errors.append,
    )

    assert bridge._prepare_device() is None
    assert errors == ["androidUserId 10 is not the active Android user (current: 0)"]
