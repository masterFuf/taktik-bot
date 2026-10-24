"""Every scroll gesture leaves one line in the journal: where the finger went down, where it lifted,
and how long it took.

A tap writes its point in the journal (`human_tap_at`); the scroll gestures wrote nothing. Their
only trace was a `step_metric`, which reaches stdout only when a bridge has wired a telemetry sink:
the single-shot Lab, the CLI and the tests had none. The proof of the Lab's follow and unfollow on
2026-09-28 counted the nine drags of the unfollow's walk from the `scrolls` figure of its result,
with no line to read them from (question 5 of that report). The drag primitive the unfollow walks
its following list with is checked too, through the mixin method the engine calls.
"""

import pytest
from loguru import logger

import taktik.core.shared.behavior.gesture_primitives as gp
from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.social_media.instagram.workflows.automation.unfollow.mixins.actions import (
    UnfollowActionsMixin,
)

_PATH = [[270, 1900], [285, 1680], [305, 1180], [320, 420]]


class _Log:
    def __init__(self):
        self.lines = []

    def debug(self, message, *_args, **_kwargs):
        self.lines.append(message)

    def error(self, message, *_args, **_kwargs):
        self.lines.append(message)


class _RawSwipe:
    """A device that takes a straight swipe or a whole path, and records nothing else."""

    def __init__(self):
        self.calls = []

    def swipe(self, x1, y1, x2, y2, duration=0.5):
        self.calls.append(("swipe", x1, y1, x2, y2))

    def swipe_points(self, path, duration):
        self.calls.append(("swipe_points", path[0], path[-1]))

    @property
    def info(self):
        return {"displayWidth": 1080, "displayHeight": 2280}


class _Device:
    def __init__(self, raw):
        self._device = raw

    def swipe_coordinates(self, *args):
        self._device.calls.append(("swipe_coordinates",) + args)


class _Host(gp.GestureMixin):
    screen_width = 1080
    screen_height = 2280

    def __init__(self):
        self.device = _Device(_RawSwipe())
        self.logger = _Log()


@pytest.fixture(autouse=True)
def _sampled_path_and_no_pause(monkeypatch):
    monkeypatch.setattr(gp, "sample_swipe", lambda *_a, **_k: ([p[:] for p in _PATH], 0.6))
    monkeypatch.setattr(gp.time, "sleep", lambda _seconds: None)


GESTURES = {
    "curve": lambda host: host._human_swipe("up"),
    "controlled curve": lambda host: host._human_swipe("up", controlled=True),
    "flick": lambda host: host._strong_flick("up"),
    "drag": lambda host: host._long_drag("up"),
    "hswipe": lambda host: host._human_horizontal_swipe("left", y_ratio=0.5),
}


def _gesture_lines(lines):
    return [line for line in lines if line.startswith("Gesture ")]


@pytest.mark.parametrize("name", list(GESTURES))
def test_each_scroll_gesture_writes_its_line(name):
    host = _Host()

    assert GESTURES[name](host) is True

    lines = _gesture_lines(host.logger.lines)
    assert len(lines) == 1, host.logger.lines
    assert " -> " in lines[0] and " ms" in lines[0]


def test_the_line_says_where_the_finger_went_down_and_lifted():
    host = _Host()

    host._strong_flick("up")

    (line,) = _gesture_lines(host.logger.lines)
    (_kind, sx, sy, ex, ey) = host.device._device.calls[-1]
    assert f"({sx}, {sy}) -> ({ex}, {ey})" in line
    assert line.startswith("Gesture flick up:")


@pytest.fixture
def journal():
    lines = []
    sink = logger.add(lambda message: lines.append(message.record["message"]), level="DEBUG")
    yield lines
    logger.remove(sink)


def test_a_drag_between_two_points_writes_its_line_without_a_logger_given(journal):
    raw = _RawSwipe()

    assert gp.human_drag_between_raw(raw, (540, 1750), (550, 740), duration=0.6) is True

    lines = _gesture_lines(journal)
    assert lines == ["Gesture drag up: (540, 1750) -> (550, 740) in 600 ms"]


class _UnfollowWalk(UnfollowActionsMixin):
    """The unfollow's list drag, on a device that takes a whole path."""

    def __init__(self):
        self.device = BaseDeviceFacade(_RawSwipe())
        self.logger = _Log()


def test_each_drag_of_the_unfollow_walk_is_in_the_journal(journal):
    walk = _UnfollowWalk()

    for _ in range(3):
        assert walk._drag_follow_list() is True

    assert len(_gesture_lines(journal)) == 3
    assert all(line.startswith("Gesture drag up:") for line in _gesture_lines(journal))
