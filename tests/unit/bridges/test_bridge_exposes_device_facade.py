"""A bridge exposes a DeviceFacade, not a raw uiautomator2 device.

The bridges stayed on the raw device because the facade was not callable, so the 50 sites
written as `self.device(resourceId=...)` would have broken. Now that it is, `self.device` can
carry the facade — and the mixins keep working untouched, which is what these tests pin.

The ordering matters as much as the wrap: `_after_connect` may swap the device for the clone
rewriting proxy, so the facade has to be applied AFTER it, or the proxy silently drops out and
cloned accounts start looking for resource-ids under the official package name.
"""

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.facade import BaseDeviceFacade

from bridges.common.runtime.platform_bridge import PlatformBridgeBase


class _RawDevice:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(kwargs)
        return ("selection", kwargs)


def _bridge() -> PlatformBridgeBase:
    bridge = PlatformBridgeBase.__new__(PlatformBridgeBase)
    bridge.PLATFORM = "instagram"
    return bridge


def test_raw_device_is_wrapped_in_a_facade():
    raw = _RawDevice()

    wrapped = _bridge()._wrap_in_facade(raw)

    assert isinstance(wrapped, BaseDeviceFacade)
    assert wrapped.device is raw


def test_the_selector_idiom_still_works_through_the_facade():
    """The 50 bridge call sites are written this way; none of them changed."""
    raw = _RawDevice()

    wrapped = _bridge()._wrap_in_facade(raw)
    wrapped(resourceId="com.instagram.android:id/message_input")

    assert raw.calls == [{"resourceId": "com.instagram.android:id/message_input"}]


def test_wrapping_is_idempotent():
    """`connect()` wraps once; a second pass must not stack facades."""
    facade = BaseDeviceFacade(_RawDevice())

    assert _bridge()._wrap_in_facade(facade) is facade


def test_none_stays_none():
    assert _bridge()._wrap_in_facade(None) is None


def test_the_clone_proxy_survives_the_wrap():
    """Regression guard for cloned accounts: the facade must wrap the PROXY, and the proxy
    must keep rewriting the package prefix underneath it."""
    raw = _RawDevice()
    proxy = CloneAwareDeviceProxy(raw, "com.taktik.ig1")

    wrapped = _bridge()._wrap_in_facade(proxy)
    wrapped(resourceId="com.instagram.android:id/search_tab")

    assert wrapped.device is proxy
    assert raw.calls == [{"resourceId": "com.taktik.ig1:id/search_tab"}]


def test_facade_capabilities_become_reachable_from_a_bridge():
    """The point of the lot: what the workflows already had is now available here."""
    wrapped = _bridge()._wrap_in_facade(_RawDevice())

    for capability in ("human_tap", "xpath", "get_xml_dump"):
        assert hasattr(wrapped, capability), capability
