from taktik.core.shared.device.facade import BaseDeviceFacade


class _Rpc:
    def __init__(self):
        self.calls = []

    def dumpWindowHierarchy(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return "<hierarchy/>"


class _Device:
    settings = {"max_depth": 73}

    def __init__(self):
        self.jsonrpc = _Rpc()
        self.regular_calls = 0

    def dump_hierarchy(self):
        self.regular_calls += 1
        return "<regular/>"


class _UiautomatorSettings:
    """Matches uiautomator2's one-argument Settings.get contract."""

    def get(self, key):
        assert key == "max_depth"
        return 61


class _RealisticDevice(_Device):
    settings = _UiautomatorSettings()


def test_optional_dump_timeout_is_forwarded_to_jsonrpc():
    raw = _Device()
    facade = BaseDeviceFacade(raw)

    assert facade.get_xml_dump(timeout_seconds=4.0) == "<hierarchy/>"
    assert raw.jsonrpc.calls == [((False, 73), {"http_timeout": 4.0})]
    assert raw.regular_calls == 0


def test_optional_dump_timeout_supports_uiautomator_settings_contract():
    raw = _RealisticDevice()
    facade = BaseDeviceFacade(raw)

    assert facade.get_xml_dump(timeout_seconds=0.01) == "<hierarchy/>"
    assert raw.jsonrpc.calls == [((False, 61), {"http_timeout": 0.1})]


def test_default_dump_path_remains_unchanged():
    raw = _Device()
    facade = BaseDeviceFacade(raw)

    assert facade.get_xml_dump() == "<regular/>"
    assert raw.regular_calls == 1
    assert raw.jsonrpc.calls == []
