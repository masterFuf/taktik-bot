from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_DETAIL_SELECTORS,
)
from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
    crop_screenshot_to_post,
    install_instagram_ai_hooks,
)


class FakeElement:
    def __init__(self, exists, bounds=None):
        self.exists = exists
        self.info = {"bounds": bounds or {}}


class FakeDevice:
    def __init__(self, elements):
        self.elements = elements

    def xpath(self, selector):
        return self.elements.get(selector, FakeElement(False))


class FakeImage:
    size = (100, 200)

    def __init__(self):
        self.crop_box = None

    def crop(self, box):
        cropped = FakeImage()
        cropped.crop_box = box
        return cropped


def test_crop_screenshot_to_post_uses_post_selector_catalogs():
    image = FakeImage()
    device = FakeDevice(
        {
            POST_DETAIL_SELECTORS.ai_crop_header_selectors[0]: FakeElement(
                True,
                {"top": 40},
            ),
            POST_DETAIL_SELECTORS.ai_crop_button_row_selectors[0]: FakeElement(
                True,
                {"bottom": 150},
            ),
        }
    )

    cropped = crop_screenshot_to_post(image, device)

    assert cropped.crop_box == (0, 32, 100, 156)


def test_install_ai_hooks_without_device_is_noop_and_logs_warning():
    logs = []

    install_instagram_ai_hooks(
        ai=object(),
        ai_config={"smartComments": True},
        device=None,
        log=lambda level, message: logs.append((level, message)),
    )

    assert logs == [("warning", "AI hooks: no device available, skipping")]
