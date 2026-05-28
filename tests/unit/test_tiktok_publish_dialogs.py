from taktik.core.social_media.tiktok.services import publish_dialogs
from taktik.core.social_media.tiktok.services.publish_dialogs import (
    dismiss_post_popups,
    handle_permission_dialog,
    handle_publish_confirmation_dialog,
)


class FakeElement:
    def __init__(self, exists: bool):
        self.exists = exists
        self.clicked = False

    def wait(self, timeout: float = 0) -> bool:
        return self.exists

    def click(self) -> None:
        self.clicked = True


class FakeDevice:
    def __init__(self, matches: dict[str, FakeElement]):
        self.matches = matches

    def xpath(self, xpath: str) -> FakeElement:
        return self.matches.get(xpath, FakeElement(False))


class FakePermissionHandler:
    deny_result = False
    grant_result = 0

    def __init__(self, _device, _device_id):
        pass

    def deny_contacts_if_present(self, wait: float = 0) -> bool:
        return self.deny_result

    def grant(self, rounds: int = 0, per_round_wait: float = 0) -> int:
        return self.grant_result


def test_handle_permission_dialog_denies_contacts(monkeypatch):
    FakePermissionHandler.deny_result = True
    FakePermissionHandler.grant_result = 0
    monkeypatch.setattr(publish_dialogs, "PermissionHandler", FakePermissionHandler)

    assert handle_permission_dialog(object(), "device-1")


def test_handle_permission_dialog_grants_media(monkeypatch):
    FakePermissionHandler.deny_result = False
    FakePermissionHandler.grant_result = 2
    monkeypatch.setattr(publish_dialogs, "PermissionHandler", FakePermissionHandler)

    assert handle_permission_dialog(object(), "device-1")


def test_dismiss_post_popups_clicks_gdpr_first():
    gdpr_xpath = publish_dialogs.POPUP_SELECTORS.gdpr_got_it_button[0]
    gdpr = FakeElement(True)
    device = FakeDevice({gdpr_xpath: gdpr})

    assert dismiss_post_popups(device, sleep=lambda _seconds: None)
    assert gdpr.clicked


def test_handle_publish_confirmation_dialog_clicks_confirm_button():
    dialog = FakeElement(True)
    button = FakeElement(True)
    device = FakeDevice({
        publish_dialogs.PUBLISH_SELECTORS.publish_confirm_dialog[0]: dialog,
        publish_dialogs.PUBLISH_SELECTORS.publish_confirm_btn[0]: button,
    })

    assert handle_publish_confirmation_dialog(device)
    assert button.clicked
