"""Step 1 of the one-photo spec: one parsed dump answers like `d.xpath()` does."""

import os
from pathlib import Path

import pytest
from uiautomator2.xpath import PageSource, strict_xpath

from taktik.core.shared.device.snapshot import ScreenSnapshot, SnapshotSource

# The structure of a real dump (AOSP XML: every element is <node>, the widget type an attribute),
# with invented texts: this repository is public.
DUMP = (
    '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
    '<node index="0" text="" resource-id="" class="android.widget.FrameLayout" content-desc="" '
    'clickable="false" enabled="true" selected="false" checked="false" bounds="[0,0][1080,2400]">'
    '<node index="0" text="alpha_one" resource-id="com.instagram.android:id/follow_list_username" '
    'class="android.widget.TextView" content-desc="" clickable="true" enabled="true" selected="false" '
    'checked="false" bounds="[200,640][700,690]" />'
    '<node index="1" text="Suivi(e)" resource-id="com.instagram.android:id/follow_list_row_large_follow_button" '
    'class="android.widget.Button" content-desc="Alpha suivi(e)" clickable="true" enabled="true" '
    'selected="true" checked="false" bounds="[760,630][1040,750]" />'
    '<node index="2" text="beta_two" resource-id="com.instagram.android:id/follow_list_username" '
    'class="android.widget.TextView" content-desc="" clickable="true" enabled="true" selected="false" '
    'checked="false" bounds="[200,820][700,870]" />'
    '</node></hierarchy>'
)

SELECTORS = [
    '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
    '//android.widget.Button[contains(@text, "Suivi")]',
    '//android.widget.TextView',
    '//*[@class="android.widget.TextView"]',   # the raw-tree idiom: finds nothing in d.xpath()
    '//*[re:match(@text, "^beta")]',
    '//*[@content-desc="nothing like this"]',
]


def _paths(root, elements):
    tree = root.getroottree()
    return [tree.getpath(el) for el in elements]


@pytest.mark.parametrize("selector", SELECTORS)
def test_the_photo_finds_exactly_what_uiautomator2_finds(selector):
    snap = ScreenSnapshot(DUMP)
    source = PageSource.parse(DUMP)
    expected = _paths(source.root, [el.elem for el in source.find_elements(strict_xpath(selector))])
    assert _paths(snap._root, snap.elements(selector)) == expected


def test_nodes_carry_what_the_bot_reads_and_taps():
    button = ScreenSnapshot(DUMP).first('//android.widget.Button')
    assert (button.text, button.content_desc, button.class_name) == ("Suivi(e)", "Alpha suivi(e)", "android.widget.Button")
    assert button.bounds == (760, 630, 1040, 750)
    assert button.clickable and button.enabled and button.selected and not button.checked


def test_a_list_of_selectors_answers_with_the_first_that_finds():
    snap = ScreenSnapshot(DUMP)
    found = snap.find(['//*[@text="absent"]', '//*[@resource-id="com.instagram.android:id/follow_list_username"]'])
    assert [node.text for node in found] == ["alpha_one", "beta_two"]
    assert snap.exists(['//*[@text="absent"]', '//android.widget.Button'])
    assert not snap.exists(['//*[@text="absent"]'])


def test_an_invalid_selector_finds_nothing_instead_of_raising():
    assert ScreenSnapshot(DUMP).find('//*[') == []


def test_an_empty_dump_is_an_empty_photo():
    snap = ScreenSnapshot(None)
    assert snap.is_empty and not snap.exists('//*') and snap.first('//*') is None


def test_the_source_keeps_a_photo_until_its_ttl_or_an_invalidation():
    dumps = []
    source = SnapshotSource(lambda: dumps.append(1) or DUMP, ttl_s=60)
    first = source.snapshot()
    assert source.snapshot() is first and len(dumps) == 1
    source.invalidate()
    assert source.snapshot() is not first and len(dumps) == 2


def test_waiting_takes_new_photos_until_the_screen_answers():
    screens = iter([DUMP.replace("Suivi(e)", "Suivre"), DUMP])
    source = SnapshotSource(lambda: next(screens))
    snap = source.wait_for(lambda s: s.exists('//*[@text="Suivi(e)"]'), timeout=5, poll_ms=1)
    assert snap is not None and snap.first('//android.widget.Button').text == "Suivi(e)"


def test_waiting_gives_up_at_the_timeout():
    source = SnapshotSource(lambda: DUMP)
    assert source.wait_for(lambda s: s.exists('//*[@text="never"]'), timeout=0, poll_ms=1) is None


CORPUS = Path(os.environ.get("TAKTIK_DEBUG_UI") or Path(__file__).resolve().parents[4] / "debug_ui")


@pytest.mark.skipif(not CORPUS.is_dir(), reason="no captured dumps here (they never enter the repository)")
def test_equality_on_a_sample_of_real_dumps():
    """A sample; the whole corpus is `scripts/check_snapshot_equality.py`."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_snapshot_equality", Path(__file__).resolve().parents[4] / "scripts" / "check_snapshot_equality.py")
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    selectors = check.catalogue_selectors()[::10]
    dumps = sorted(CORPUS.rglob("*.xml"))[::200]
    for dump in dumps:
        xml = dump.read_text(encoding="utf-8", errors="replace")
        source, snap = PageSource.parse(xml), ScreenSnapshot(xml)
        for selector in selectors:
            expected, error = check._paths_u2(source, selector)
            if error is None:
                assert check._paths_snapshot(snap, selector) == expected, (dump.name, selector)


def test_the_shared_facade_takes_and_keeps_photos():
    from taktik.core.shared.device.facade import BaseDeviceFacade

    class Device:
        dumps = 0

        def dump_hierarchy(self):
            Device.dumps += 1
            return DUMP

    facade = BaseDeviceFacade(Device())
    first = facade.snapshot()
    assert first.exists('//android.widget.Button') and facade.snapshot() is first
    facade.invalidate_snapshot()
    assert facade.snapshot() is not first and Device.dumps == 2
