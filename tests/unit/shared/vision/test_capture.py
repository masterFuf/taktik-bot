"""A black frame is a valid image — these lock the fact that we can still tell it apart.

The threshold matters in one direction only: a real screen, dark theme included, carries text and
icons, so its brightest pixel is near 255. The frames measured on the production base (116 of
28 983 stored AI screenshots, byte-identical) read (0, 0) — nothing was ever drawn.
"""

from PIL import Image

from taktik.core.shared.vision.capture import capture_non_blank, is_blank_capture


def _flat(level):
    return Image.new("RGB", (108, 240), (level,) * 3)


def _dark_theme_screen():
    """A dark profile page: near-black background, white text somewhere on it."""
    image = _flat(4)
    image.putpixel((50, 120), (255, 255, 255))
    return image


class TestIsBlankCapture:
    def test_pure_black_is_blank(self):
        assert is_blank_capture(_flat(0)) is True

    def test_almost_black_is_blank(self):
        # A device returning near-zero noise instead of exact zeros is the same non-screen.
        assert is_blank_capture(_flat(10)) is True

    def test_dark_theme_screen_is_not_blank(self):
        # The whole point: a dark UI must survive the check.
        assert is_blank_capture(_dark_theme_screen()) is False

    def test_just_above_threshold_is_not_blank(self):
        assert is_blank_capture(_flat(13)) is False

    def test_none_is_blank(self):
        assert is_blank_capture(None) is True

    def test_unreadable_object_is_not_declared_blank(self):
        # Refusing to judge beats declaring a real capture blank on the strength of an exception.
        assert is_blank_capture(object()) is False


class _Device:
    """Hands back the frames it was given, one per call."""

    def __init__(self, frames):
        self._frames = list(frames)
        self.calls = 0

    def screenshot(self):
        self.calls += 1
        frame = self._frames.pop(0)
        if isinstance(frame, Exception):
            raise frame
        return frame


class TestCaptureNonBlank:
    def test_returns_the_first_usable_frame(self):
        screen = _dark_theme_screen()
        device = _Device([screen])
        assert capture_non_blank(device, retry_delay=0) is screen
        assert device.calls == 1

    def test_retries_past_a_blank_frame(self):
        screen = _dark_theme_screen()
        device = _Device([_flat(0), screen])
        assert capture_non_blank(device, retry_delay=0) is screen
        assert device.calls == 2

    def test_returns_none_when_every_attempt_is_blank(self):
        # None, not a black image: the caller must know it has nothing rather than believe it has
        # a screen. This is what keeps the vision model from describing a void.
        device = _Device([_flat(0), _flat(0)])
        assert capture_non_blank(device, retry_delay=0) is None
        assert device.calls == 2

    def test_survives_a_raising_device(self):
        screen = _dark_theme_screen()
        device = _Device([RuntimeError("device offline"), screen])
        assert capture_non_blank(device, retry_delay=0) is screen

    def test_returns_none_when_the_device_only_raises(self):
        device = _Device([RuntimeError("boom"), RuntimeError("boom")])
        assert capture_non_blank(device, retry_delay=0) is None
