from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
    POST_DETAIL_SELECTORS,
)
import pytest

from taktik.core.social_media.instagram.workflows.core.ai_hooks import (
    crop_screenshot_to_post,
    install_instagram_ai_hooks,
    _resolve_comment_language,
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


@pytest.mark.parametrize(
    "base_lang, post_language, expected",
    [
        # base_lang = account preferred language (fallback app). Allowed = {base_lang, English}.
        ("fr", "French", "fr"),           # post in base language -> comment in it
        ("fr", "english", "en"),          # English always allowed (case-insensitive)
        ("fr", "Spanish", None),          # other language -> skip
        ("fr", "Chinese", None),
        ("fr", None, "fr"),               # undetected -> default to base language
        ("fr", "", "fr"),
        ("en", "English", "en"),
        ("en", "French", None),           # EN account: French is NOT allowed (only English)
        ("en", None, "en"),
        ("en", "Mandarin", None),
        # Account targeting a non-FR/EN audience (preferred_language beyond fr/en).
        ("es", "Spanish", "es"),
        ("es", "español", "es"),
        ("es", "Castellano", "es"),
        ("es", "English", "en"),          # English still allowed for a Spanish account
        ("es", "French", None),           # Spanish account, French post -> skip
        ("es", None, "es"),
        ("de", "German", "de"),
        ("ar", "Arabic", "ar"),
        ("it", "Italian", "it"),
        ("pt", "Portuguese", "pt"),
        # Robustness: a name that merely CONTAINS "en" must not be read as English.
        ("fr", "Slovenian", None),
        # The model may emit a code instead of a name.
        ("fr", "fr", "fr"),
        ("fr", "en", "en"),
        # Decorated name (flag/extra) still resolves via startswith.
        ("fr", "French (Français)", "fr"),
    ],
)
def test_resolve_comment_language_policy(base_lang, post_language, expected):
    assert _resolve_comment_language(base_lang, post_language) == expected
