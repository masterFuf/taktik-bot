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


def _run_one(selectors, xml, rewrite=None, device=None):
    device = device or _SnapshotDevice(xml)
    results = run_selector_tests(
        device, {"screen.probe": _SelectorEntry(list(selectors))}, _IPC(), xml=xml, rewrite=rewrite
    )
    return [item["found"] for item in results[0]["xpaths"]], results[0]["xpaths"]


# AOSP dump: the widget type is an attribute, as the phone sends it.
_AOSP_DUMP = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node class="android.widget.FrameLayout" resource-id="com.example.app:id/root" text="" content-desc="">
    <node class="android.widget.TextView" resource-id="com.example.app:id/title" text="Sample title" content-desc="" />
    <node class="android.view.View" resource-id="story_row" text="" content-desc="Sample row" />
  </node>
</hierarchy>"""


def test_class_tag_selectors_match_as_under_d_xpath():
    found, _ = _run_one(
        [
            '//android.widget.TextView[@text="Sample title"]',
            '//node[@class="android.widget.TextView"]',
        ],
        _AOSP_DUMP,
    )

    assert found == [True, False]


def test_uiautomator2_shorthands_are_evaluated_like_d_xpath():
    found, _ = _run_one(
        ["@com.example.app:id/title", "%ample tit%", "^Sample.*$", "@com.example.app:id/missing"],
        _AOSP_DUMP,
    )

    assert found == [True, True, True, False]


def test_instagram_rewrite_finds_a_bare_compose_id():
    from taktik.core.clone.device.proxy import CloneAwareDeviceProxy

    selector = '//*[@resource-id="com.instagram.android:id/story_row"]'
    proxy = CloneAwareDeviceProxy(_SnapshotDevice(_AOSP_DUMP), "com.instagram.android")

    plain, _ = _run_one([selector], _AOSP_DUMP)
    rewritten, details = _run_one([selector], _AOSP_DUMP, rewrite=proxy.rewrite_xpath)

    assert plain == [False]
    assert rewritten == [True]
    assert details[0]["xpath"] == selector


def test_an_invalid_xpath_is_reported_without_a_live_retry():
    device = _SnapshotDevice(_AOSP_DUMP)

    found, details = _run_one(['//*[@text="Sample title"'], _AOSP_DUMP, device=device)

    assert found == [False]
    assert details[0]["error"]
    assert details[0]["mode"] == "xml_snapshot"
    assert device.live_xpath_calls == 0


def test_a_given_dump_is_not_taken_again():
    device = _SnapshotDevice(_AOSP_DUMP)

    _run_one(['//android.widget.TextView'], _AOSP_DUMP, device=device)

    assert device.dump_calls == 0


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
