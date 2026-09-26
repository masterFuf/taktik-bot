"""A publish deletes the media it pushed once Instagram confirmed it on screen, and only then.

Every Instagram publish of the app (post, reel, carousel, story) goes through this workflow, which
pushes its media under camera names (`IMG_...`) and records them in `pushed_media_registry`. They
used to stay on the phone until a later publish purged them by age; a small phone filled up. They
are now deleted as soon as the publish is confirmed: the upload indicator of the feed (pending row)
or of the Reels tab (snackbar) seen then gone, or, for a story, our own bubble of the feed tray
going from "Add to story" to a story of ours. A failed, rehearsed or unconfirmed publish keeps its
media for the age purge.

The story used to be declared published once the caption field was gone, a field its editor never
shows: the verdict held whatever happened. It now reads the tray. The tray fixtures are real IG 410
dumps (handles replaced): our bubble whole without a story (Lab corpus, French), the same bubble cut
by the scroll, and a phone run in English with our story up then deleted. On IG 410 the "Add to
story" badge stays on our bubble while the story is up: only its ring (`seen_state`) tells, and a
verdict read on the badge never confirmed a story, so its media were never deleted.
"""

import os
import time
import types
from pathlib import Path

import pytest

from taktik.core.shared.device import media_store, pushed_media_registry
from taktik.core.shared.device.snapshot import ScreenSnapshot
from taktik.core.social_media.instagram.actions.atomic.interaction.information_window import (
    InformationWindows,
)
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.content_creation import (
    CONTENT_CREATION_SELECTORS as CC,
)
from taktik.core.social_media.instagram.workflows.publish import post_workflow
from taktik.core.social_media.instagram.workflows.publish.post_workflow import InstagramPostWorkflow

FIXTURES = Path(__file__).parents[1] / "fixtures"
TRAY_EMPTY = (FIXTURES / "ig410_fr_feed_tray_own_story_empty.xml").read_text(encoding="utf-8")
TRAY_SCROLLED = (FIXTURES / "ig410_fr_feed_tray_scrolled_off.xml").read_text(encoding="utf-8")
# Phone run: our story up (badge AND ring), then the same tray once it was deleted (badge, no ring).
TRAY_POSTED = (FIXTURES / "ig410_en_feed_tray_own_story_up.xml").read_text(encoding="utf-8")
TRAY_EMPTY_EN = (FIXTURES / "ig410_en_feed_tray_own_story_deleted.xml").read_text(encoding="utf-8")


def _screen(*nodes: str) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">' + "".join(nodes) + "</hierarchy>"


def _node(resource_id: str = "", text: str = "") -> str:
    return (f'<node index="0" text="{text}" resource-id="{resource_id}" class="android.widget.FrameLayout" '
            f'package="com.instagram.android" content-desc="" clickable="false" enabled="true" '
            f'bounds="[0,300][1080,420]" />')


# After a post or a carousel: the feed's pending row (Lab dump `publish.tap_share`, IG 410).
PENDING_ROW = _screen(_node("com.instagram.android:id/row_pending_container"),
                      _node(text="Keep Instagram open to finish posting…"))
# After a reel: the Reels tab's upload snackbar (same Lab run).
REELS_UPLOADING = _screen(_node("com.instagram.android:id/upload_snackbar_container"),
                          _node(text="Sharing to Reels…"))
FEED = _screen(_node("com.instagram.android:id/refreshable_container"))
EDITOR = _screen(_node(text="Your story"))
MEDIA = __file__


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(time, "sleep", lambda *_: None)
    monkeypatch.setenv("TAKTIK_DATA_DIR", str(tmp_path / "data"))
    set_active_locale(None)
    yield
    set_active_locale(None)


class Phone:
    """The screens Instagram shows, one per read; the last one stays."""

    def __init__(self, *screens):
        self.screens = list(screens)
        self.reads = 0

    def _current(self):
        return self.screens[0]

    def snapshot(self, max_age_s=0.0):
        self.reads += 1
        xml = self.screens.pop(0) if len(self.screens) > 1 else self.screens[0]
        return ScreenSnapshot(xml)

    def wait_for_snapshot(self, predicate, timeout, poll_ms=300):
        photo = self.snapshot()
        return photo if predicate(photo) else None

    def invalidate_snapshot(self):
        pass

    def human_tap(self, bounds, **_):
        raise AssertionError("nothing on these screens is to be tapped")


class Click:
    """The workflow's click actions: presence is read on the current screen, without a read."""

    def __init__(self, phone):
        self.device = phone

    def _is_element_present(self, selectors, timeout=None):
        return ScreenSnapshot(self.device._current()).exists(selectors)


class Run(InstagramPostWorkflow):
    """The real orchestration and verdicts; navigation up to the share button left out."""

    def __init__(self, phone, post_type="post", share=True, push_for_real=False):
        self.device = phone
        self.device_id = "test-device"
        self._log = lambda *a, **k: None
        self._status = lambda *a, **k: None
        self.package_name = "com.instagram.android"
        self.post_type = post_type
        self.story_via_feed = False
        self.permission_prompts_answered = 0
        self.information_windows_acknowledged = 0
        self._pushed_paths = []
        self._a = {"click": Click(phone)}
        self._share = share
        self._push_for_real = push_for_real

    def _push_all(self, media_paths):
        if self._push_for_real:
            return super()._push_all(media_paths)
        self._pushed_paths = [f"/sdcard/DCIM/Camera/IMG_20260926_101010_{i}.jpg" for i in range(len(media_paths))]
        return True

    def _launch_and_home(self):
        pass

    def _detect_app_language(self):
        pass

    def _open_creation_and_gallery(self):
        return None

    def _select_carousel(self, count):
        return True

    def _advance_to_composer(self, max_taps=3):
        return True

    def _fill_caption(self, text):
        return True

    def _acknowledge_information_windows(self, unless_on_screen=(), wait_s=6.0):
        return InformationWindows()

    def _tap(self, selectors, timeout=4.0):
        selectors = [selectors] if isinstance(selectors, str) else list(selectors)
        if selectors in (CC.share_button_xpaths(), CC.story_publish_xpaths()):
            return self._share
        return True

    def _present(self, selectors, timeout=4.0):
        return True


@pytest.fixture
def deletions(monkeypatch):
    calls = []

    def record(device_id, remote_paths, log=None):
        calls.append(list(remote_paths))
        return len(calls[-1])

    monkeypatch.setattr(post_workflow, "delete_pushed_media", record)
    return calls


def _publish(phone, post_type="post", **kwargs):
    media = [MEDIA, MEDIA] if post_type == "carousel" else [MEDIA]
    stop = kwargs.pop("stop_before_share", False)
    workflow = Run(phone, post_type, **kwargs)
    return workflow, workflow.execute(caption="hello", media_paths=media, stop_before_share=stop)


# --- post, reel, carousel ---------------------------------------------------------------------


@pytest.mark.parametrize("post_type", ["post", "carousel"])
def test_the_media_go_once_the_pending_row_has_come_and_gone(deletions, post_type):
    workflow, result = _publish(Phone(PENDING_ROW, PENDING_ROW, FEED), post_type)

    assert result["success"] is True
    assert result["confirmed"] is True
    assert deletions == [workflow._pushed_paths]
    assert result["media_released"] == len(workflow._pushed_paths)


def test_a_reel_is_confirmed_by_the_upload_snackbar(deletions):
    workflow, result = _publish(Phone(REELS_UPLOADING, FEED), "reel")

    assert result["confirmed"] is True
    assert deletions == [workflow._pushed_paths]


def test_an_upload_still_running_keeps_the_media(deletions):
    workflow, result = _publish(Phone(PENDING_ROW))

    assert result["success"] is True
    assert result["confirmed"] is False
    assert deletions == []


def test_no_upload_seen_is_no_confirmation(deletions):
    workflow, result = _publish(Phone(FEED))

    assert result["confirmed"] is False
    assert deletions == []


def test_a_failed_share_keeps_the_media(deletions):
    workflow, result = _publish(Phone(FEED), share=False)

    assert result["success"] is False
    assert deletions == []


@pytest.mark.parametrize("post_type", ["post", "story"])
def test_a_rehearsal_keeps_the_media(deletions, post_type):
    workflow, result = _publish(Phone(TRAY_EMPTY, EDITOR), post_type, stop_before_share=True)

    assert result["success"] is True
    assert result["confirmed"] is False
    assert deletions == []


# --- story ------------------------------------------------------------------------------------


def test_the_tray_reads_our_bubble_on_real_dumps():
    workflow = Run(Phone(FEED))

    assert workflow._own_story_state(ScreenSnapshot(TRAY_EMPTY)) == "empty"
    assert workflow._own_story_state(ScreenSnapshot(TRAY_EMPTY_EN)) == "empty"
    assert workflow._own_story_state(ScreenSnapshot(TRAY_POSTED)) == "posted"
    # Cut by the scroll, the avatar has no ring either: never read at all.
    assert workflow._own_story_state(ScreenSnapshot(TRAY_SCROLLED)) is None
    assert workflow._own_story_state(ScreenSnapshot(EDITOR)) is None


def test_the_badge_stays_while_our_story_is_up():
    """What the former read missed: the same bubble, badge and content-desc, with and without
    our story. Only the ring differs."""

    def bubble(xml):
        [own] = ScreenSnapshot(xml).elements(CC.own_story_bubble_xpath())
        return {(n.get("resource-id") or "").split("/")[-1]: n.get("content-desc")
                for n in own.elem.iter()}

    up, deleted = bubble(TRAY_POSTED), bubble(TRAY_EMPTY_EN)
    assert "reel_empty_badge" in up and "reel_empty_badge" in deleted
    assert up.pop("seen_state") == ""
    assert up == deleted


def test_other_bubbles_rings_are_not_ours():
    """Every other bubble of the tray carries a ring: only ours is read."""
    assert ScreenSnapshot(TRAY_EMPTY_EN).exists('//*[contains(@resource-id, "seen_state")]')
    assert not ScreenSnapshot(TRAY_EMPTY_EN).exists(CC.own_story_ring_xpath())


def test_a_story_is_published_when_our_bubble_turns_to_a_story(deletions):
    # Before the share, then the feed while it uploads (no ring yet), then our story.
    workflow, result = _publish(Phone(TRAY_EMPTY_EN, EDITOR, TRAY_EMPTY_EN, TRAY_POSTED), "story")

    assert result["success"] is True
    assert result["confirmed"] is True
    assert deletions == [workflow._pushed_paths]


def test_a_story_whose_editor_stays_open_is_not_published():
    """The former verdict looked for the caption field, which the story editor never shows: it
    declared this story published."""
    workflow, result = _publish(Phone(TRAY_EMPTY, EDITOR), "story")

    assert result["success"] is False
    assert result["error_type"] == "publish_not_committed"


def test_a_story_still_uploading_is_shared_but_not_confirmed(deletions):
    workflow, result = _publish(Phone(TRAY_EMPTY, EDITOR, TRAY_EMPTY), "story")

    assert result["success"] is True
    assert result["confirmed"] is False
    assert "not confirmed" in result["message"]
    assert deletions == []


def test_a_story_already_up_leaves_nothing_to_compare(deletions):
    workflow, result = _publish(Phone(TRAY_POSTED, EDITOR, TRAY_POSTED), "story")

    assert result["success"] is True
    assert result["confirmed"] is False
    assert deletions == []


def test_a_bubble_not_read_before_the_share_confirms_nothing(deletions):
    workflow, result = _publish(Phone(TRAY_SCROLLED, EDITOR, TRAY_POSTED), "story")

    assert result["confirmed"] is False
    assert deletions == []


# --- the registry, end to end ------------------------------------------------------------------


class Adb:
    """The device's shared storage, as `adb shell` answers it."""

    def __init__(self):
        self.files = {}
        self.removed = []

    def shell(self, device_id, *args, timeout=15):
        if args[:1] == ("ls",):
            return 0, "\n".join(os.path.basename(p) for p in self.files), ""
        if args[:1] == ("date",):
            return 0, "20260926_101010", ""
        if args[:1] == ("stat",):
            path = args[-1]
            return (0, str(self.files[path]), "") if path in self.files else (1, "", "No such file")
        if args[:1] == ("rm",):
            self.removed.append(args[-1])
            self.files.pop(args[-1], None)
        return 0, "", ""

    def push(self, device_id, local_path, remote_path, timeout=60):
        self.files[remote_path] = os.path.getsize(local_path)
        return True


@pytest.fixture
def adb(monkeypatch):
    fake = Adb()
    monkeypatch.setattr(media_store, "_adb_shell", fake.shell)
    monkeypatch.setattr(media_store, "_adb_push", fake.push)
    return fake


def test_a_confirmed_publish_deletes_what_it_pushed_through_the_registry(adb):
    workflow, result = _publish(Phone(PENDING_ROW, FEED), push_for_real=True)

    assert result["confirmed"] is True
    assert workflow._pushed_paths == ["/sdcard/DCIM/Camera/IMG_20260926_101010.py"]
    assert adb.removed == workflow._pushed_paths
    assert pushed_media_registry.load("test-device") == []


def test_an_unconfirmed_publish_leaves_its_media_in_the_registry(adb):
    workflow, result = _publish(Phone(PENDING_ROW), push_for_real=True)

    assert adb.removed == []
    assert [e["path"] for e in pushed_media_registry.load("test-device")] == workflow._pushed_paths


def test_a_file_that_is_no_longer_ours_is_never_deleted(adb):
    """Same name, another size: the user's file now; forgotten, not deleted."""
    workflow = Run(Phone(FEED), push_for_real=True)
    assert workflow._push_all([MEDIA])
    path = workflow._pushed_paths[0]
    adb.files[path] += 1

    assert media_store.delete_pushed_media("test-device", [path]) == 0
    assert adb.removed == []
    assert pushed_media_registry.load("test-device") == []


def test_only_the_paths_asked_for_are_deleted(adb):
    workflow = Run(Phone(FEED), push_for_real=True)
    assert workflow._push_all([MEDIA])
    first = workflow._pushed_paths[0]
    other = Run(Phone(FEED), push_for_real=True)
    assert other._push_all([MEDIA])
    second = other._pushed_paths[0]

    assert media_store.delete_pushed_media("test-device", [first]) == 1
    assert adb.removed == [first]
    assert [e["path"] for e in pushed_media_registry.load("test-device")] == [second]


# --- the Lab ------------------------------------------------------------------------------------


class RawPhone:
    """A uiautomator2 device showing one screen."""

    def __init__(self, xml):
        self.xml = xml

    def dump_hierarchy(self, *_, **__):
        return self.xml


@pytest.mark.parametrize("xml, state", [(TRAY_EMPTY, "empty"), (TRAY_EMPTY_EN, "empty"), (TRAY_POSTED, "posted"),
                                        (TRAY_SCROLLED, None)],
                         ids=["empty_fr", "empty_en", "posted", "scrolled"])
def test_the_lab_reads_our_bubble_with_the_production_step(xml, state):
    """Same id in the app's `actionCatalog`; the workflow's own read, no gesture."""
    from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    result = ACTION_REGISTRY["publish.read_own_story"](
        types.SimpleNamespace(device=RawPhone(xml), device_id="device-1"), {})

    assert result["details"] == {"state": state}
    assert result["success"] is (state is not None)


def test_the_lab_story_verdict_is_the_production_one():
    from bridges.compat.diagnostics.actions.instagram import ACTION_REGISTRY, register_actions

    register_actions()
    result = ACTION_REGISTRY["publish.wait_story_published"](
        types.SimpleNamespace(device=RawPhone(TRAY_POSTED), device_id="device-1"), {"before": "empty"})

    assert result["details"] == {"verdict": "confirmed", "before": "empty"}
    for action_id in ("publish.wait_upload_finished", "publish.wait_publish_commit"):
        assert action_id in ACTION_REGISTRY
