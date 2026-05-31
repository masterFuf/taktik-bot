from taktik.core.social_media.tiktok.services.profile.username import (
    UNKNOWN_USERNAME,
    clean_profile_username,
    get_current_profile_username,
    username_from_content_description,
)
from taktik.core.social_media.tiktok.ui.selectors import PROFILE_SELECTORS


class _FakeElement:
    def __init__(self, *, exists=False, text="", content_description=""):
        self.exists = exists
        self.text = text
        self.info = {"contentDescription": content_description}

    def get_text(self):
        return self.text


class _FakeXPathResult:
    def __init__(self, element):
        self._element = element

    @property
    def exists(self):
        return self._element.exists

    @property
    def info(self):
        return self._element.info

    def get_text(self):
        return self._element.get_text()


class _FakeDevice:
    def __init__(self, elements_by_selector):
        self.elements_by_selector = elements_by_selector
        self.selectors = []

    def xpath(self, selector):
        self.selectors.append(selector)
        element = self.elements_by_selector.get(selector, _FakeElement())
        return _FakeXPathResult(element)


def test_clean_profile_username_strips_at_sign():
    assert clean_profile_username(" @Creator ") == "Creator"


def test_username_from_content_description_extracts_first_mention():
    assert username_from_content_description("Open @creator profile") == "creator"


def test_get_current_profile_username_prefers_profile_username_selector():
    selector = PROFILE_SELECTORS.username[0]
    device = _FakeDevice({selector: _FakeElement(exists=True, text="@Creator")})

    assert get_current_profile_username(device) == "Creator"
    assert device.selectors == [selector]


def test_get_current_profile_username_uses_content_description_fallback():
    selector = PROFILE_SELECTORS.username_content_description[0]
    device = _FakeDevice(
        {selector: _FakeElement(exists=True, content_description="Open @fallback profile")}
    )

    assert get_current_profile_username(device) == "fallback"
    assert device.selectors == PROFILE_SELECTORS.username + [selector]


def test_get_current_profile_username_returns_unknown_when_not_found():
    device = _FakeDevice({})

    assert get_current_profile_username(device) == UNKNOWN_USERNAME
