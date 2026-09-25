"""Step 1 of the one-photo spec: one dump answers exactly like `d.xpath()` does.

"Exactly" means the production path: uiautomator2's `d.xpath(selector)` on the same screen, and
for Instagram the `CloneAwareDeviceProxy` every Instagram bridge mounts, which rewrites
`@resource-id` equalities before uiautomator2 sees them. A photo that ignored that rewrite found
nothing where production found the bare ids of Instagram's Compose screens.
"""

import os
import threading
import time
from pathlib import Path

import pytest
from uiautomator2.xpath import XPathEntry, XPathError

from taktik.core.clone.device.proxy import CloneAwareDeviceProxy
from taktik.core.shared.device.snapshot import ScreenSnapshot, SnapshotSource, SnapshotUnavailable

IG = "com.instagram.android:id"

# The structure of a real dump (AOSP XML: every element is <node>, the widget type an attribute),
# with invented texts: this repository is public. The last row carries a BARE id, as Instagram's
# Compose screens (442+) expose them.
DUMP = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    '<node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.instagram.android" '
    'content-desc="" clickable="false" enabled="true" selected="false" checked="false" bounds="[0,0][1080,2400]">'
    f'<node index="0" text="alpha_one" resource-id="{IG}/follow_list_username" '
    'class="android.widget.TextView" content-desc="" clickable="true" enabled="true" selected="false" '
    'checked="false" bounds="[200,640][700,690]" />'
    f'<node index="1" text="Suivi(e)" resource-id="{IG}/follow_list_row_large_follow_button" '
    'class="android.widget.Button" content-desc="Alpha suivi(e)" clickable="true" enabled="true" '
    'selected="true" checked="false" focused="true" bounds="[760,630][1040,750]" />'
    f'<node index="2" text="beta_two" resource-id="{IG}/follow_list_username" '
    'class="android.widget.TextView" content-desc="" clickable="true" enabled="true" selected="false" '
    'checked="false" bounds="[200,820][700,870]" />'
    '<node index="3" text="gamma" resource-id="activity_feed_newsfeed_story_row" '
    'class="com.facebook.compose.view.Row$Inner" content-desc="" clickable="true" enabled="true" '
    'selected="false" checked="false" bounds="[0,900][1080,1000]" />'
    '</node></hierarchy>'
)

SELECTORS = [
    f'//*[@resource-id="{IG}/follow_list_username"]',
    f'//*[@resource-id="{IG}/activity_feed_newsfeed_story_row"]',  # bare id: the proxy's case
    '//android.widget.Button[contains(@text, "Suivi")]',
    '//android.widget.TextView',
    '//*[@class="android.widget.TextView"]',   # the raw-tree idiom: finds nothing in d.xpath()
    '//*[re:match(@text, "^beta")]',
    '//com.facebook.compose.view.Row.Inner',   # uiautomator2's tag for a class with a `$`
    '@' + IG + '/follow_list_username',         # uiautomator2 shorthands
    '^gam',
    '%suivi(e)%',
    'beta_two',
    '//*[@content-desc="nothing like this"]',
]


class _U2Device:
    """What uiautomator2's `d.xpath` needs: a dump and a wait timeout."""

    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


def _paths(elements):
    return [el.elem.getroottree().getpath(el.elem) for el in elements]


@pytest.mark.parametrize("selector", SELECTORS)
def test_the_photo_finds_what_the_instagram_production_path_finds(selector):
    proxy = CloneAwareDeviceProxy(_U2Device(DUMP), "com.instagram.android")
    expected = _paths(proxy.xpath(selector).all())
    photo = ScreenSnapshot(DUMP, rewrite=proxy.rewrite_xpath)
    assert _paths(photo.elements(selector)) == expected


@pytest.mark.parametrize("selector", SELECTORS)
def test_without_a_proxy_the_photo_finds_what_plain_uiautomator2_finds(selector):
    """TikTok's bridges mount no proxy: the plain `d.xpath()`."""
    assert _paths(ScreenSnapshot(DUMP).elements(selector)) == _paths(_U2Device(DUMP).xpath(selector).all())


def test_the_proxy_rewrite_is_what_reaches_the_bare_ids():
    selector = SELECTORS[1]
    assert ScreenSnapshot(DUMP).elements(selector) == []
    rewritten = ScreenSnapshot(DUMP, rewrite=CloneAwareDeviceProxy(_U2Device(DUMP), "x").rewrite_xpath)
    assert [node.text for node in rewritten.find(selector)] == ["gamma"]


def test_nodes_carry_what_the_bot_reads_and_taps():
    button = ScreenSnapshot(DUMP).first('//android.widget.Button')
    assert (button.text, button.content_desc, button.class_name) == ("Suivi(e)", "Alpha suivi(e)", "android.widget.Button")
    assert button.bounds == (760, 630, 1040, 750)
    assert button.clickable and button.enabled and button.selected and button.focused
    assert not button.checked and not button.scrollable


def test_a_list_of_selectors_answers_with_the_first_that_finds():
    photo = ScreenSnapshot(DUMP)
    found = photo.find(['//*[@text="absent"]', f'//*[@resource-id="{IG}/follow_list_username"]'])
    assert [node.text for node in found] == ["alpha_one", "beta_two"]
    assert photo.exists(['//*[@text="absent"]', '//android.widget.Button'])
    assert not photo.exists(['//*[@text="absent"]'])


def test_the_raw_call_raises_on_an_invalid_selector():
    with pytest.raises(XPathError):
        ScreenSnapshot(DUMP).elements('//*[')


def test_a_list_goes_on_past_an_invalid_selector_like_the_production_loops():
    """`facade.xpath()` logs an invalid selector and returns None; the loops go on to the next
    one. A real list starts with one (`post/detail.py`): raising there dropped the whole list."""
    photo = ScreenSnapshot(DUMP)
    assert [node.text for node in photo.find(['//*[', '//android.widget.Button'])] == ["Suivi(e)"]
    assert photo.exists(["//*[matches(@text, 'x')]", '//android.widget.Button'])
    assert not photo.exists(['//*['])


@pytest.mark.parametrize("xml", [None, "", "<hierarchy><node", '<?xml version="1.0"?><hierarchy rotation="0" />'])
def test_a_failed_dump_is_not_an_empty_screen(xml):
    """An empty photo answered "absent" to everything: a popup "gone" while the server restarted."""
    with pytest.raises(SnapshotUnavailable):
        ScreenSnapshot(xml)


def test_each_photo_is_new_unless_the_caller_accepts_an_older_one():
    dumps = []
    source = SnapshotSource(lambda: dumps.append(1) or DUMP)
    first = source.snapshot()
    assert source.snapshot() is not first and len(dumps) == 2
    kept = source.snapshot(max_age_s=60)
    assert kept is not first and len(dumps) == 2
    source.invalidate()
    assert source.snapshot(max_age_s=60) is not kept and len(dumps) == 3


def test_a_photo_asked_before_an_invalidation_is_never_kept():
    source = SnapshotSource(lambda: DUMP)

    def dump_while_a_gesture_happens():
        source.invalidate()  # the gesture lands while the dump is on its way
        return DUMP

    source._dump = dump_while_a_gesture_happens
    stale = source.snapshot()
    source._dump = lambda: DUMP
    assert source.snapshot(max_age_s=60) is not stale


def test_the_age_counts_from_when_the_dump_was_asked():
    def slow_dump():
        time.sleep(0.12)
        return DUMP

    # Windows' monotonic clock ticks every ~16 ms: the margin covers one tick.
    assert SnapshotSource(slow_dump).snapshot().age_ms >= 100


def test_waiting_takes_new_photos_until_the_screen_answers():
    screens = iter([DUMP.replace("Suivi(e)", "Suivre"), None, DUMP])
    source = SnapshotSource(lambda: next(screens))
    photo = source.wait_for(lambda s: s.exists('//*[@text="Suivi(e)"]'), timeout=5, poll_ms=1)
    assert photo is not None and photo.first('//android.widget.Button').text == "Suivi(e)"


def test_waiting_gives_up_at_the_timeout():
    source = SnapshotSource(lambda: DUMP)
    assert source.wait_for(lambda s: s.exists('//*[@text="never"]'), timeout=0, poll_ms=1) is None


def test_photos_can_be_taken_from_several_threads():
    source = SnapshotSource(lambda: DUMP)
    errors = []

    def take():
        try:
            for _ in range(20):
                source.snapshot(max_age_s=0.01)
                source.invalidate()
        except Exception as exc:  # pragma: no cover - reported below
            errors.append(exc)

    threads = [threading.Thread(target=take) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []


def test_every_question_asked_of_a_photo_is_observed():
    """The Lab traces wrap `device.xpath()`, which a photo never calls: they are told instead."""
    seen = []
    photo = ScreenSnapshot(DUMP, observer=lambda sel, found, ms: seen.append((sel, found, ms >= 0)))
    assert [node.text for node in photo.find(['//*[', '//*[@text="absent"]', '//android.widget.Button'])] == ["Suivi(e)"]
    assert photo.exists('//android.widget.Button')  # asked again: answered from the photo, told again
    assert seen == [('//*[', False, True), ('//*[@text="absent"]', False, True),
                    ('//android.widget.Button', True, True), ('//android.widget.Button', True, True)]


def test_an_observer_that_fails_changes_no_answer():
    def broken(*_args):
        raise RuntimeError("observer down")

    photo = ScreenSnapshot(DUMP, observer=broken)
    assert photo.exists('//android.widget.Button') and not photo.exists('//*[@text="absent"]')


def test_a_source_tells_its_observers_of_every_photo_it_takes():
    seen = []
    source = SnapshotSource(lambda: DUMP)
    source.snapshot().exists('//*[@text="before"]')  # no observer yet
    source.observe(lambda sel, found, _ms: seen.append((sel, found)))
    source.snapshot().exists('//android.widget.Button')
    source.wait_for(lambda photo: photo.exists('//*[@text="Suivi(e)"]'), timeout=1, poll_ms=1)
    assert seen == [('//android.widget.Button', True), ('//*[@text="Suivi(e)"]', True)]


def test_a_facade_on_a_mock_device_still_takes_real_photos():
    """The facade forwards unknown attributes to its device: a mock answered the photo source
    itself, and every test built on it would have passed without a dump."""
    from unittest.mock import MagicMock

    from taktik.core.shared.device.facade import BaseDeviceFacade

    device = MagicMock()
    device.dump_hierarchy.return_value = DUMP
    facade = BaseDeviceFacade(device)
    facade.get_xml_dump = lambda *a, **k: DUMP
    photo = facade.snapshot()
    assert isinstance(photo, ScreenSnapshot)
    assert photo.first('//android.widget.Button').text == "Suivi(e)"


def test_the_shared_facade_uses_the_device_rewrite():
    from taktik.core.shared.device.facade import BaseDeviceFacade

    device = _U2Device(DUMP)
    facade = BaseDeviceFacade(CloneAwareDeviceProxy(device, "com.instagram.android"))
    assert [node.text for node in facade.snapshot().find(SELECTORS[1])] == ["gamma"]
    assert BaseDeviceFacade(device).snapshot().find(SELECTORS[1]) == []


CORPUS = Path(os.environ.get("TAKTIK_DEBUG_UI") or Path(__file__).resolve().parents[4] / "debug_ui")


@pytest.mark.skipif(not CORPUS.is_dir(), reason="no captured dumps here (they never enter the repository)")
def test_equality_on_a_sample_of_real_dumps():
    """A sample; the whole corpus is `scripts/check_snapshot_equality.py`."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_snapshot_equality", Path(__file__).resolve().parents[4] / "scripts" / "check_snapshot_equality.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    selectors = check.catalogue_selectors()[0][::10]
    for dump in sorted(CORPUS.rglob("*.xml"))[::200]:
        dump_check = check.DumpCheck(dump.read_text(encoding="utf-8", errors="replace"))
        for selector in selectors:
            for rewrite in (True, False):
                assert dump_check.compare(selector, rewrite) != "different", (dump.name, selector, rewrite)
