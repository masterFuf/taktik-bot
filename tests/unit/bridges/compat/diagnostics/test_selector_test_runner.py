from dataclasses import dataclass

from bridges.compat.diagnostics.runtime.selector_test.runner import run_selector_tests


@dataclass
class _SelectorEntry:
    xpaths: list[str]
    source: str = "python"


class _IPC:
    def __init__(self):
        self.messages = []

    def send(self, event_type, **payload):
        self.messages.append((event_type, payload))


class _LiveSelector:
    def __init__(self, found: bool):
        self.exists = found


class _SnapshotDevice:
    def __init__(self, xml: str):
        self.xml = xml
        self.dump_calls = 0
        self.live_xpath_calls = 0

    def dump_hierarchy(self, compressed=False):
        self.dump_calls += 1
        return self.xml

    def xpath(self, _xpath):
        self.live_xpath_calls += 1
        raise AssertionError("Live XPath should not be called when snapshot evaluation works")


class _LiveFallbackDevice:
    def __init__(self):
        self.dump_calls = 0
        self.live_xpath_calls = 0

    def dump_hierarchy(self, compressed=False):
        self.dump_calls += 1
        raise RuntimeError("dump unavailable")

    def xpath(self, xpath):
        self.live_xpath_calls += 1
        return _LiveSelector(xpath == '//*[@resource-id="com.instagram.android:id/feed_tab"]')


def test_selector_tests_evaluate_xpaths_on_one_xml_snapshot():
    device = _SnapshotDevice(
        """
        <hierarchy>
          <node resource-id="com.instagram.android:id/feed_tab" selected="true" />
        </hierarchy>
        """
    )

    results = run_selector_tests(
        device,
        {
            "navigation.feed_tab": _SelectorEntry(
                [
                    '//*[@resource-id="com.instagram.android:id/feed_tab"]',
                    '//*[@resource-id="com.instagram.android:id/profile_tab"]',
                ]
            )
        },
        _IPC(),
    )

    xpaths = results[0]["xpaths"]
    assert device.dump_calls == 1
    assert device.live_xpath_calls == 0
    assert results[0]["has_match"] is True
    assert [item["found"] for item in xpaths] == [True, False]
    assert {item["mode"] for item in xpaths} == {"xml_snapshot"}


def test_selector_tests_fall_back_to_live_xpath_when_snapshot_unavailable():
    device = _LiveFallbackDevice()

    results = run_selector_tests(
        device,
        {
            "navigation.feed_tab": _SelectorEntry(
                [
                    '//*[@resource-id="com.instagram.android:id/feed_tab"]',
                    '//*[@resource-id="com.instagram.android:id/profile_tab"]',
                ]
            )
        },
        _IPC(),
    )

    assert device.dump_calls == 1
    assert device.live_xpath_calls == 2
    assert results[0]["has_match"] is True
    assert [item["found"] for item in results[0]["xpaths"]] == [True, False]
    assert {item["mode"] for item in results[0]["xpaths"]} == {"live_device"}
