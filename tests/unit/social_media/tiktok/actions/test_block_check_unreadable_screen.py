"""TikTok's block check never answers "no" on a screen it could not read.

`DetectionActions.is_action_blocked` is the look every TikTok writing path makes after its
gesture (`look_for_action_block`). It used to swallow a failed dump in `debug` and answer False:
a refusal shown on a screen the bot could not read passed for "not blocked", and nothing said so.
It now reads through the facade's photo (`device.snapshot()`), the same read as every other TikTok
screen question, and a screen that cannot be read raises `SnapshotUnavailable`, the exception the
Instagram detector raises: the shared look then says that a block cannot be ruled out.

The "no" is read on a real capture: a For You video of TikTok 43.1.4 in French (Pixel 3a).
"""

import pytest
from loguru import logger

from taktik.core.shared.device.snapshot import SnapshotUnavailable
from taktik.core.shared.diagnostics import run_halt
from taktik.core.shared.diagnostics.action_block import look_for_action_block
from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
from unit.paths import CORE

VIDEO = (CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_for_you_video.xml").read_text(encoding="utf-8")


class _Phone:
    """uiautomator2 as the check reads it: one screen, or the error its dump raises."""

    def __init__(self, screen):
        self.screen = screen
        self.gestures = []

    def dump_hierarchy(self, *_a, **_k):
        if isinstance(self.screen, Exception):
            raise self.screen
        return self.screen

    def click(self, *args):
        self.gestures.append(("click", args))

    def press(self, key):
        self.gestures.append(("press", key))


@pytest.fixture(autouse=True)
def fresh_latch():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


@pytest.fixture
def warnings_logged():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="WARNING")
    yield lines
    logger.remove(sink)


UNREADABLE = {
    "the dump fails": RuntimeError("uiautomator2 server gone"),
    "the dump is empty": "",
}


def test_a_video_is_read_and_is_no_block():
    phone = _Phone(VIDEO)

    assert DetectionActions(phone).is_action_blocked() is False
    assert run_halt.arret_demande() is None
    assert phone.gestures == []


@pytest.mark.parametrize("screen", UNREADABLE.values(), ids=UNREADABLE.keys())
def test_a_screen_that_cannot_be_read_is_never_a_no(screen):
    phone = _Phone(screen)

    with pytest.raises(SnapshotUnavailable):
        DetectionActions(phone).is_action_blocked()
    assert run_halt.arret_demande() is None
    assert phone.gestures == []


def test_the_look_after_a_gesture_says_the_block_cannot_be_ruled_out(warnings_logged):
    detection = DetectionActions(_Phone(RuntimeError("uiautomator2 server gone")))

    # Nothing is proven, so nothing is stopped; the log says why there is no answer.
    assert look_for_action_block(detection, after="like", target="demo") is False
    assert run_halt.arret_demande() is None
    assert any("cannot be ruled out" in line for line in warnings_logged)
