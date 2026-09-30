"""The media capture forwards to the desktop what the app reads: profiles and media.

The proxy also reports every CDN image downloaded and the slides of a carousel. Forwarded as
`cdn_captured` and `carousel_captured`, neither had a reader.
"""

from taktik.core.social_media.instagram.media import MediaCaptureService


def _service():
    sent = []
    service = MediaCaptureService(device_id="fake", desktop_bridge_callback=lambda kind, _data: sent.append(kind))
    return service, sent


def test_profiles_and_media_reach_the_desktop():
    service, sent = _service()

    service._handle_proxy_message({"type": "profile_data", "username": "alice"})
    service._handle_proxy_message({"type": "media_data", "media_id": "1", "image_url": "https://cdn/1.jpg"})

    assert sent == ["profile_captured", "media_captured"]


def test_cdn_images_and_carousel_slides_stay_in_process():
    service, sent = _service()
    seen = []
    service.on_cdn_captured = seen.append
    cdn = {"type": "cdn_capture", "url": "https://cdn/2.jpg", "size": 2048}

    service._handle_proxy_message(cdn)
    service._handle_proxy_message({"type": "carousel_media", "parent_media_id": "1", "index": 0})

    assert sent == []
    assert seen == [cdn]
