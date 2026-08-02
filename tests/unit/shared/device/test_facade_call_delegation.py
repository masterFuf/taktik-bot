"""The facade must be a drop-in replacement for a raw uiautomator2 device.

`__getattr__` already forwarded every attribute, but Python resolves ``obj(...)`` on the TYPE,
never through `__getattr__` — so ``facade(resourceId=...)`` used to raise while every other
access worked. That single gap is what kept the bridges on a raw device (50 call sites use the
selector-call idiom) while the workflows moved to the facade.
"""

from taktik.core.shared.device.facade import BaseDeviceFacade


class _Selection:
    """Stand-in for a uiautomator2 UiObject."""

    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs


class _RawDevice:
    def __init__(self):
        self.calls = []
        self.info = {"displayWidth": 1080}

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return _Selection(args, kwargs)

    def jsonrpc(self):
        """A member the facade does NOT wrap — so it can only arrive via `__getattr__`."""
        return "raw-rpc"


class _CloneProxy:
    """Mirrors the clone-aware proxy the Instagram bridge inserts: it rewrites the
    resource-id for the active clone package before reaching the real device."""

    def __init__(self, device, package):
        self._device = device
        self._package = package

    def __call__(self, *args, **kwargs):
        if "resourceId" in kwargs:
            kwargs["resourceId"] = kwargs["resourceId"].replace("com.instagram.android", self._package)
        return self._device(*args, **kwargs)


def test_selector_call_is_forwarded_with_its_arguments():
    raw = _RawDevice()
    facade = BaseDeviceFacade(raw)

    selection = facade(resourceId="com.instagram.android:id/message_input")

    assert isinstance(selection, _Selection)
    assert raw.calls == [((), {"resourceId": "com.instagram.android:id/message_input"})]


def test_positional_and_keyword_arguments_both_travel():
    raw = _RawDevice()
    facade = BaseDeviceFacade(raw)

    facade("android.widget.EditText", textContains="Message")

    assert raw.calls == [(("android.widget.EditText",), {"textContains": "Message"})]


def test_facade_call_matches_the_raw_device_call():
    """The whole point: a caller cannot tell the two apart."""
    raw = _RawDevice()
    facade = BaseDeviceFacade(raw)

    through_facade = facade(className="android.widget.EditText")
    through_raw = raw(className="android.widget.EditText")

    assert through_facade.kwargs == through_raw.kwargs


def test_attribute_forwarding_still_works():
    """`__call__` is an addition, not a replacement — the rest of the surface is untouched."""
    raw = _RawDevice()
    facade = BaseDeviceFacade(raw)

    assert facade.info == {"displayWidth": 1080}
    assert facade.jsonrpc() == "raw-rpc"


def test_wrapping_a_proxy_keeps_the_proxy_in_the_chain():
    """The Instagram bridge wraps its device in a clone-aware proxy before anything else sees
    it. The facade must wrap THAT, or clone resource-id rewriting is silently lost."""
    raw = _RawDevice()
    proxy = _CloneProxy(raw, "com.instagram.android.c1")
    facade = BaseDeviceFacade(proxy)

    facade(resourceId="com.instagram.android:id/message_input")

    assert raw.calls == [((), {"resourceId": "com.instagram.android.c1:id/message_input"})]
