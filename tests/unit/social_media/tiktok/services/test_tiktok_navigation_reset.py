from taktik.core.social_media.tiktok.services.navigation_reset import return_to_tiktok_home
from taktik.core.social_media.tiktok.ui.selectors import NAVIGATION_SELECTORS


class _FakeXPath:
    def __init__(self, selector, device):
        self.selector = selector
        self.device = device

    def click_exists(self, timeout):
        self.device.click_timeouts.append(timeout)
        return self.selector == self.device.success_selector


class _FakeDevice:
    def __init__(self, success_selector=None):
        self.success_selector = success_selector
        self.presses = []
        self.selectors = []
        self.click_timeouts = []

    def press(self, key):
        self.presses.append(key)

    def xpath(self, selector):
        self.selectors.append(selector)
        return _FakeXPath(selector, self)


def test_return_to_tiktok_home_uses_centralized_home_selectors(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.social_media.tiktok.services.navigation_reset.time.sleep",
        lambda _seconds: None,
    )
    device = _FakeDevice(success_selector=NAVIGATION_SELECTORS.home_tab[0])

    assert return_to_tiktok_home(device)

    assert device.presses == ["back", "back", "back"]
    assert device.selectors == [NAVIGATION_SELECTORS.home_tab[0]]
    assert device.click_timeouts == [2.0]


def test_return_to_tiktok_home_returns_false_when_home_tab_is_not_found(monkeypatch):
    monkeypatch.setattr(
        "taktik.core.social_media.tiktok.services.navigation_reset.time.sleep",
        lambda _seconds: None,
    )
    device = _FakeDevice(success_selector=None)

    assert not return_to_tiktok_home(device, back_presses=1)

    assert device.presses == ["back"]
    assert device.selectors == NAVIGATION_SELECTORS.home_tab
