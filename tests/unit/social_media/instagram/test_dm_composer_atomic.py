"""One place knows how to talk to a DM composer.

Four implementations used to: the messaging workflow, the DM reply actions, the DM outreach
actions and the engagement bridge. Each located the field its own way, so a change to the
Instagram composer repaired one of the four. These tests pin the union they collapsed into.
"""

import pytest

from taktik.core.social_media.instagram.actions.atomic.text import dm_composer


class _Element:
    def __init__(self, name):
        self.name = name
        self.info = {"bounds": {"left": 0, "top": 0, "right": 100, "bottom": 40}}
        self.clicked = False
        self.text_set = None

    def click(self):
        self.clicked = True

    def set_text(self, value):
        self.text_set = value


class _XPathSelector:
    def __init__(self, element):
        self._element = element

    @property
    def exists(self):
        return self._element is not None

    def get(self, timeout=None):
        return self._element


class _Device:
    """Answers to whichever lookup strategy the caller reaches for, and records them."""

    def __init__(self, *, xpath_hit=None, resource_hit=None, class_hit=None, text_hit=None, serial="PHONE-1"):
        self.serial = serial
        self.tried = []
        self._xpath_hit = xpath_hit
        self._resource_hit = resource_hit
        self._class_hit = class_hit
        self._text_hit = text_hit

    def xpath(self, selector):
        self.tried.append(("xpath", selector))
        return _XPathSelector(self._xpath_hit)

    def __call__(self, **kwargs):
        self.tried.append(("select", kwargs))
        if "resourceId" in kwargs:
            return _XPathSelectorAsObject(self._resource_hit)
        if "className" in kwargs:
            return _XPathSelectorAsObject(self._class_hit)
        if "textContains" in kwargs:
            return _XPathSelectorAsObject(self._text_hit)
        return _XPathSelectorAsObject(None)


class _XPathSelectorAsObject:
    """uiautomator2 UiObject stand-in: truthy `exists`, and it IS the element."""

    def __init__(self, element):
        self._element = element
        self.info = getattr(element, "info", None)

    @property
    def exists(self):
        return self._element is not None

    def click(self):
        self._element.click()

    def set_text(self, value):
        self._element.set_text(value)


# ── Locating the composer ────────────────────────────────────────────────────

def test_the_xpath_catalogue_wins_when_it_matches():
    element = _Element("composer")
    device = _Device(xpath_hit=element)

    assert dm_composer.find_message_input(device) is element
    assert device.tried[0][0] == "xpath"


def test_it_falls_back_to_resource_ids_then_class_then_hint():
    """The bridge's four-strategy lookup, which the other three callers did not have."""
    element = _Element("by-hint")
    device = _Device(text_hit=element)

    found = dm_composer.find_message_input(device)

    assert found is not None
    strategies = [kind for kind, _ in device.tried]
    assert "xpath" in strategies and "select" in strategies


def test_missing_composer_returns_none_rather_than_raising():
    assert dm_composer.find_message_input(_Device()) is None


# ── Naming the device ────────────────────────────────────────────────────────

def test_the_device_id_is_derived_from_the_device():
    assert dm_composer.resolve_device_id(_Device(serial="PIXEL-4A")) == "PIXEL-4A"


def test_an_explicit_device_id_wins():
    assert dm_composer.resolve_device_id(_Device(serial="PIXEL-4A"), "PIXEL-6A") == "PIXEL-6A"


def test_an_unnameable_device_raises_instead_of_guessing():
    """The three call sites defaulted to 'emulator-5554'. On a multi-device rig that types the
    message into a phone that is not the one running the session, and nothing raises."""

    class _Anonymous:
        pass

    with pytest.raises(ValueError, match="device id"):
        dm_composer.resolve_device_id(_Anonymous())


# ── Typing ───────────────────────────────────────────────────────────────────

def test_typing_falls_back_to_set_text_when_the_keyboard_fails(monkeypatch):
    monkeypatch.setattr(dm_composer, "type_text_human", lambda *a, **k: False)
    monkeypatch.setattr(dm_composer, "tap_element_human", lambda *a, **k: True)
    element = _Element("composer")

    ok = dm_composer.type_message(_Device(xpath_hit=element), "PHONE-1", "bonjour", element=element)

    assert ok is True
    assert element.text_set == "bonjour"


def test_typing_reports_failure_when_every_path_fails(monkeypatch):
    monkeypatch.setattr(dm_composer, "type_text_human", lambda *a, **k: False)
    monkeypatch.setattr(dm_composer, "tap_element_human", lambda *a, **k: True)

    class _Hostile(_Element):
        def set_text(self, value):
            raise RuntimeError("no")

        def send_keys(self, value):
            raise RuntimeError("no")

    assert dm_composer.type_message(_Device(), "PHONE-1", "x", element=_Hostile("c")) is False


def test_empty_message_is_a_no_op():
    assert dm_composer.type_message(_Device(), "PHONE-1", "") is True
