from taktik.core.social_media.youtube.workflows.account.account_workflow import (
    YouTubeAccountWorkflow,
)


class FakeElement:
    def __init__(self, exists=False):
        self._exists = exists
        self.clicked = False

    def exists(self, timeout=0):
        return self._exists

    def click(self):
        self.clicked = True


class FakeDevice:
    def __init__(self):
        self.shell_calls = []
        self.query_calls = []

    def shell(self, command):
        self.shell_calls.append(command)
        if command.startswith("pm list packages"):
            return "package:com.google.android.youtube"
        if command.startswith("monkey -p"):
            return "Events injected: 1"
        if "mCurrentFocus" in command:
            return "mCurrentFocus=com.google.android.youtube/.Home"
        if "ACCOUNT_SYNC_SETTINGS" in command:
            return "Starting"
        return ""

    def dump_hierarchy(self, compressed=False):
        return "<hierarchy />"

    def __call__(self, *args, **kwargs):
        self.query_calls.append((args, kwargs))
        return FakeElement(False)


class FakeNotifier:
    def __init__(self):
        self.statuses = []
        self.logs = []

    def status(self, status, message):
        self.statuses.append((status, message))

    def log(self, level, message):
        self.logs.append((level, message))


class FakeGmailWorkflow:
    calls = []

    def __init__(self, device, device_id, notifier=None):
        self.device = device
        self.device_id = device_id
        self.notifier = notifier

    def ensure_account_added(self, email, password):
        self.calls.append((self.device, self.device_id, self.notifier, email, password))
        return {"success": True, "message": "ok"}


class FakeRepository:
    def __init__(self):
        self.upserts = []

    def upsert(self, email, device_id):
        self.upserts.append((email, device_id))
        return True


def test_youtube_account_login_ensures_google_account_and_persists():
    FakeGmailWorkflow.calls = []
    device = FakeDevice()
    notifier = FakeNotifier()
    repository = FakeRepository()
    workflow = YouTubeAccountWorkflow(
        device,
        "device-1",
        notifier=notifier,
        gmail_workflow_factory=FakeGmailWorkflow,
        account_repository=repository,
        sleeper=lambda _seconds: None,
    )

    result = workflow.login(email=" user@example.com ", password=" secret ")

    assert result["success"] is True
    assert result["workflow"] == "login"
    assert FakeGmailWorkflow.calls == [
        (device, "device-1", notifier, "user@example.com", "secret")
    ]
    assert repository.upserts == [("user@example.com", "device-1")]
    assert any(command.startswith("monkey -p com.google.android.youtube") for command in device.shell_calls)


def test_youtube_account_login_rejects_missing_email_without_device_effects():
    device = FakeDevice()
    repository = FakeRepository()
    workflow = YouTubeAccountWorkflow(
        device,
        "device-1",
        account_repository=repository,
        sleeper=lambda _seconds: None,
    )

    result = workflow.login(email="   ")

    assert result == {
        "success": False,
        "message": "email is required for YouTube login",
        "error_type": "validation",
    }
    assert device.shell_calls == []
    assert repository.upserts == []


def test_youtube_account_login_reports_missing_youtube():
    class MissingYouTubeDevice(FakeDevice):
        def shell(self, command):
            self.shell_calls.append(command)
            if command.startswith("pm list packages"):
                return ""
            return super().shell(command)

    workflow = YouTubeAccountWorkflow(
        MissingYouTubeDevice(),
        "device-1",
        account_repository=FakeRepository(),
        sleeper=lambda _seconds: None,
    )

    result = workflow.login(email="user@example.com")

    assert result["success"] is False
    assert result["error_type"] == "app_not_installed"


def test_youtube_account_logout_opens_android_account_settings():
    device = FakeDevice()
    workflow = YouTubeAccountWorkflow(device, "device-1", sleeper=lambda _seconds: None)

    result = workflow.logout(email="user@example.com")

    assert result == {
        "success": True,
        "workflow": "logout",
        "email": "user@example.com",
        "message": "Manage your account in Android Settings",
    }
    assert "am start -a android.settings.ACCOUNT_SYNC_SETTINGS" in device.shell_calls
