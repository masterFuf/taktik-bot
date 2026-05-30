from taktik.core.social_media.tiktok.workflows.management.login.login_workflow import TikTokLoginWorkflow
from taktik.core.social_media.tiktok.workflows.management.logout.logout_workflow import TikTokLogoutWorkflow
from taktik.core.social_media.tiktok.workflows.management.signup.signup_workflow import TikTokSignupWorkflow


class _FakeNotifier:
    def __init__(self):
        self.calls = []

    def status(self, *args, **kwargs):
        self.calls.append(("status", args, kwargs))

    def log(self, *args, **kwargs):
        self.calls.append(("log", args, kwargs))


def test_tiktok_login_workflow_uses_injected_notifier():
    notifier = _FakeNotifier()
    workflow = TikTokLoginWorkflow(device=object(), device_id="device-1", notifier=notifier)

    result = workflow.execute(username="creator", password="secret")

    assert result["error_type"] == "not_implemented"
    assert notifier.calls[0][0] == "status"
    assert notifier.calls[1][0] == "log"


def test_tiktok_logout_workflow_uses_injected_notifier():
    notifier = _FakeNotifier()
    workflow = TikTokLogoutWorkflow(device=object(), device_id="device-1", notifier=notifier)
    workflow._click_selector = lambda *args, **kwargs: False

    result = workflow.execute()

    assert result["error_type"] == "profile_tab_not_found"
    assert notifier.calls[0][0] == "status"
    assert notifier.calls[-1][0] == "log"


def test_tiktok_signup_workflow_uses_injected_notifier():
    notifier = _FakeNotifier()
    workflow = TikTokSignupWorkflow(device=object(), device_id="device-1", notifier=notifier)
    workflow._detect_screen = lambda: "birthday_gate"
    workflow._click_selector = lambda *args, **kwargs: False

    result = workflow.execute(method="email", email="test@example.com")

    assert result["error_type"] == "birthday_gate_inscription_not_found"
    assert notifier.calls[0][0] == "status"
    assert any(call[0] == "log" for call in notifier.calls)
