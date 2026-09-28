from taktik.core.social_media.tiktok.services.publish.touch_fallbacks import (
    tap_caption_focus_fallback,
)


class FakeDevice:
    def __init__(self, info=None, fail_click: bool = False):
        self.info = info or {}
        self.fail_click = fail_click
        self.clicks = []

    def click(self, x: int, y: int) -> None:
        if self.fail_click:
            raise RuntimeError("click failed")
        self.clicks.append((x, y))


def test_tap_caption_focus_fallback_uses_caption_default_size():
    device = FakeDevice()

    assert tap_caption_focus_fallback(device)
    assert device.clicks == [(288, 384)]
