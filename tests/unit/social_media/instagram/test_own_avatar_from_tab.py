"""The connected account's avatar is captured from the overlay-free bottom-bar
tab avatar, not the profile header (which carries the story ring + "+" badge).

Verifies the selector targets the tab avatar (not the header), and that the tab
crop is upscaled x2 for a sharper thumbnail.
"""

import base64
import io

from PIL import Image

from taktik.core.social_media.instagram.actions.atomic.detection.profile_extraction import (
    ProfileExtractionMixin,
)

# Own profile screen: a polluted header avatar (with the "+" add-to-story badge)
# AND the clean bottom-bar tab avatar. Anonymized from a real IG v410 (FR) dump.
_OWN_PROFILE_XML = """
<hierarchy>
  <node resource-id="com.instagram.android:id/row_profile_header_imageview_frame_layout" bounds="[65,252][286,473]">
    <node resource-id="com.instagram.android:id/row_profile_header_imageview" content-desc="Votre profil. Aucune story" bounds="[65,252][286,473]" />
    <node resource-id="com.instagram.android:id/reel_empty_badge" content-desc="Ajouter à la story" bounds="[193,424][271,502]" />
  </node>
  <node resource-id="com.instagram.android:id/profile_tab" content-desc="Profil" bounds="[864,1967][1080,2088]">
    <node resource-id="com.instagram.android:id/container" bounds="[931,1986][1014,2069]">
      <node resource-id="com.instagram.android:id/tab_avatar" bounds="[931,1986][1014,2069]" />
    </node>
  </node>
</hierarchy>
"""

_SCREEN_W, _SCREEN_H = 1080, 2220


class _FakeDevice:
    """Returns a fixed XML dump and a solid-colour screenshot of screen size."""

    def __init__(self, xml: str):
        self._xml = xml

    def get_xml_dump(self) -> str:
        return self._xml

    def screenshot_pil(self) -> Image.Image:
        return Image.new("RGB", (_SCREEN_W, _SCREEN_H), color=(10, 20, 30))


class _NoopLogger:
    def debug(self, *args, **kwargs):
        return None


class _Extractor(ProfileExtractionMixin):
    def __init__(self, xml: str):
        self.device = _FakeDevice(xml)
        self.logger = _NoopLogger()


def _decode(data_url: str) -> Image.Image:
    assert data_url.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    return Image.open(io.BytesIO(raw))


def test_tab_avatar_is_upscaled_x2():
    extractor = _Extractor(_OWN_PROFILE_XML)
    data_url = extractor.extract_own_avatar_from_tab()
    assert data_url is not None

    # tab_avatar bounds [931,1986][1014,2069] = 83x83; padding 2 each side -> 87x87;
    # upscaled x2 -> 174x174.
    img = _decode(data_url)
    assert img.size == (174, 174)


def test_header_avatar_keeps_native_resolution():
    extractor = _Extractor(_OWN_PROFILE_XML)
    data_url = extractor.extract_profile_image()
    assert data_url is not None

    # header bounds [65,252][286,473] = 221x221; padding 2 each side -> 225x225; no upscale.
    img = _decode(data_url)
    assert img.size == (225, 225)


def test_tab_selector_targets_tab_not_header():
    # The two extractions must crop different regions: the tab avatar is far smaller
    # than the header, proving the tab selector does not fall back to the header.
    extractor = _Extractor(_OWN_PROFILE_XML)
    tab = _decode(extractor.extract_own_avatar_from_tab())
    header = _decode(extractor.extract_profile_image())
    assert tab.size != header.size
