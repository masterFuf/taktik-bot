from taktik.core.social_media.tiktok.services.publish.touch_fallbacks import (
    tap_caption_focus_fallback,
    tap_create_button_fallback,
    tap_first_gallery_item_fallback,
    tap_upload_bottom_left_fallback,
    tap_upload_right_strip_fallback,
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


def test_tap_create_button_fallback_uses_bottom_nav_ratio():
    device = FakeDevice({"displayWidth": 1000, "displayHeight": 2000})

    assert tap_create_button_fallback(device)
    assert device.clicks == [(400, 1880)]


def test_tap_upload_right_strip_fallback_uses_camera_strip_ratio():
    device = FakeDevice({"displayWidth": 576, "displayHeight": 1280})

    assert tap_upload_right_strip_fallback(device)
    assert device.clicks == [(469, 1004)]


def test_tap_upload_bottom_left_fallback_uses_large_layout_ratio():
    device = FakeDevice({"displayWidth": 1000, "displayHeight": 2000})

    assert tap_upload_bottom_left_fallback(device)
    assert device.clicks == [(86, 1842)]


def test_tap_first_gallery_item_fallback_taps_first_grid_cell_and_waits():
    device = FakeDevice({"displayWidth": 720, "displayHeight": 1520})
    sleeps = []

    assert tap_first_gallery_item_fallback(
        device,
        is_camera_creation_screen=lambda: False,
        sleep=sleeps.append,
    )
    assert device.clicks == [(120, 304)]
    assert sleeps == [1.0]


def test_tap_first_gallery_item_fallback_fails_if_still_on_camera_screen():
    device = FakeDevice({"displayWidth": 720, "displayHeight": 1520})

    assert not tap_first_gallery_item_fallback(
        device,
        is_camera_creation_screen=lambda: True,
        sleep=lambda _seconds: None,
    )


def test_tap_caption_focus_fallback_uses_caption_default_size():
    device = FakeDevice()

    assert tap_caption_focus_fallback(device)
    assert device.clicks == [(288, 384)]
