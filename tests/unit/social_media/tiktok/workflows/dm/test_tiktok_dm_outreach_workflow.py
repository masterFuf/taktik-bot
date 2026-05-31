from taktik.core.social_media.tiktok.actions.business.workflows.dm import TikTokDMOutreachWorkflow


class FakeDeviceManager:
    def __init__(self, device):
        self.device = device
        self.connected = False

    def connect(self):
        self.connected = True
        return True


class FakeManager:
    instances = []

    def __init__(self, device_id):
        self.device_id = device_id
        self.device_manager = FakeDeviceManager(object())
        self.stopped = 0
        self.launched = 0
        self.instances.append(self)

    def stop(self):
        self.stopped += 1

    def launch(self):
        self.launched += 1


class FakeNavigation:
    def __init__(self, device):
        self.device = device
        self.home_count = 0

    def navigate_to_user_profile(self, username):
        return True

    def navigate_to_home(self):
        self.home_count += 1
        return True


class FakeDMActions:
    def __init__(self, device):
        self.device = device
        self.sent_messages = []

    def is_in_conversation(self):
        return True

    def send_text_message(self, message):
        self.sent_messages.append(message)
        return True


class FakeBaseAction:
    def __init__(self, device):
        self.device = device

    def _find_and_click(self, selectors, timeout=5):
        return True

    def _element_exists(self, selectors, timeout=2):
        return False


class FakeNotifier:
    def __init__(self):
        self.calls = []

    def send(self, event_type, **payload):
        self.calls.append((event_type, payload))


class FakeRng:
    def choice(self, values):
        return values[0]

    def uniform(self, minimum, maximum):
        return minimum


def test_tiktok_dm_outreach_runs_with_injected_notifier_and_dedup():
    FakeManager.instances = []
    notifier = FakeNotifier()
    records = []
    duplicate_checks = []

    def duplicate_checker(account_id, recipient, platform):
        duplicate_checks.append((account_id, recipient, platform))
        return recipient == "already"

    workflow = TikTokDMOutreachWorkflow(
        "device-1",
        notifier=notifier,
        duplicate_checker=duplicate_checker,
        sent_dm_recorder=lambda *args: records.append(args),
        manager_factory=FakeManager,
        navigation_factory=FakeNavigation,
        dm_actions_factory=FakeDMActions,
        base_action_factory=FakeBaseAction,
        rng=FakeRng(),
        sleeper=lambda duration: None,
    )

    assert workflow.connect() is True
    result = workflow.run(
        ["already", "creator"],
        ["hello"],
        delay_min=1,
        delay_max=2,
        max_dms=5,
        account_id=7,
        session_id="session-1",
    )

    assert result["success"] is True
    assert result["dms_success"] == 1
    assert duplicate_checks == [(7, "already", "tiktok"), (7, "creator", "tiktok")]
    assert records == [(7, "creator", "hello", True, None, "session-1", "tiktok")]
    assert FakeManager.instances[0].stopped == 1
    assert FakeManager.instances[0].launched == 1
    assert ("status", {"status": "filtering", "message": "Skipped 1 already contacted"}) in notifier.calls
    assert (
        "dm_result",
        {"username": "creator", "success": True, "error": None},
    ) in notifier.calls
    assert (
        "stats",
        {"stats": {"sent": 1, "success": 1, "failed": 0, "privacy_blocked": 0, "not_found": 0}},
    ) in notifier.calls


def test_tiktok_dm_outreach_returns_success_when_every_recipient_is_duplicate():
    workflow = TikTokDMOutreachWorkflow(
        "device-1",
        duplicate_checker=lambda account_id, recipient, platform: True,
        manager_factory=FakeManager,
        sleeper=lambda duration: None,
    )

    result = workflow.run(["already"], ["hello"], account_id=7)

    assert result == {
        "success": True,
        "dms_sent": 0,
        "dms_success": 0,
        "dms_failed": 0,
        "error": "All recipients already received a DM",
    }
