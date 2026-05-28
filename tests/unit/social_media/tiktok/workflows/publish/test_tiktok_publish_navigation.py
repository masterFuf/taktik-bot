from taktik.core.social_media.tiktok.services import publish_navigation
from taktik.core.social_media.tiktok.services.publish_navigation import (
    advance_to_post_screen,
    ensure_gallery_picker_open,
    select_first_gallery_item,
    tap_create_button,
    tap_upload_button,
)


class FakeDevice:
    pass


def test_tap_create_button_uses_selector_before_fallback(monkeypatch):
    calls = []

    monkeypatch.setattr(
        publish_navigation,
        "tap_element",
        lambda device, selectors, timeout: calls.append((device, selectors, timeout)) or True,
    )
    monkeypatch.setattr(
        publish_navigation,
        "tap_create_button_fallback",
        lambda *_args, **_kwargs: calls.append("fallback") or True,
    )

    device = FakeDevice()
    assert tap_create_button(device)
    assert calls == [(device, publish_navigation.PUBLISH_SELECTORS.create_btn, 3.0)]


def test_tap_create_button_uses_fallback_after_selector_failure(monkeypatch):
    monkeypatch.setattr(publish_navigation, "tap_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(publish_navigation, "tap_create_button_fallback", lambda *_args, **_kwargs: True)

    assert tap_create_button(FakeDevice())


def test_tap_upload_button_tries_selector_dump_and_fallbacks_in_order(monkeypatch):
    calls = []

    monkeypatch.setattr(
        publish_navigation,
        "tap_element",
        lambda *_args, **_kwargs: calls.append("selector") or False,
    )
    monkeypatch.setattr(
        publish_navigation,
        "tap_upload_button_from_dump",
        lambda *_args, **_kwargs: calls.append("dump") or False,
    )
    monkeypatch.setattr(
        publish_navigation,
        "tap_upload_right_strip_fallback",
        lambda *_args, **_kwargs: calls.append("right") or False,
    )
    monkeypatch.setattr(
        publish_navigation,
        "tap_upload_bottom_left_fallback",
        lambda *_args, **_kwargs: calls.append("bottom") or True,
    )

    assert tap_upload_button(FakeDevice())
    assert calls == ["selector", "dump", "right", "bottom"]


def test_ensure_gallery_picker_open_retries_upload_when_still_on_camera(monkeypatch):
    gallery_states = iter([False, True])
    tap_calls = []
    sleeps = []

    monkeypatch.setattr(publish_navigation, "handle_permission_dialog", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(publish_navigation, "is_gallery_picker_open", lambda _device: next(gallery_states))
    monkeypatch.setattr(publish_navigation, "is_camera_creation_screen", lambda _device: True)
    monkeypatch.setattr(
        publish_navigation,
        "tap_upload_button",
        lambda device, **_kwargs: tap_calls.append(device) or True,
    )

    device = FakeDevice()
    assert ensure_gallery_picker_open(device, "device-1", sleep=sleeps.append)
    assert tap_calls == [device]
    assert sleeps == [1.2, 1.0, 1.2, 1.0]


def test_ensure_gallery_picker_open_checks_permissions_once_more_after_attempts(monkeypatch):
    permission_calls = []
    gallery_states = iter([False, True])

    monkeypatch.setattr(
        publish_navigation,
        "handle_permission_dialog",
        lambda *_args, **_kwargs: permission_calls.append("permission") or False,
    )
    monkeypatch.setattr(publish_navigation, "is_gallery_picker_open", lambda _device: next(gallery_states))
    monkeypatch.setattr(publish_navigation, "is_camera_creation_screen", lambda _device: False)
    monkeypatch.setattr(publish_navigation, "tap_upload_button", lambda *_args, **_kwargs: True)

    assert ensure_gallery_picker_open(FakeDevice(), "device-1", attempts=1, sleep=lambda _seconds: None)
    assert permission_calls == ["permission", "permission"]


def test_select_first_gallery_item_uses_selector_before_fallback(monkeypatch):
    calls = []

    monkeypatch.setattr(publish_navigation, "tap_element", lambda *_args, **_kwargs: calls.append("selector") or True)
    monkeypatch.setattr(
        publish_navigation,
        "tap_first_gallery_item_fallback",
        lambda *_args, **_kwargs: calls.append("fallback") or True,
    )

    assert select_first_gallery_item(FakeDevice())
    assert calls == ["selector"]


def test_select_first_gallery_item_uses_fallback_after_selector_failure(monkeypatch):
    monkeypatch.setattr(publish_navigation, "tap_element", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        publish_navigation,
        "tap_first_gallery_item_fallback",
        lambda *_args, **_kwargs: True,
    )

    assert select_first_gallery_item(FakeDevice(), sleep=lambda _seconds: None)


def test_advance_to_post_screen_taps_next_until_post_screen(monkeypatch):
    post_states = iter([False, True])
    sleeps = []
    taps = []

    monkeypatch.setattr(publish_navigation, "is_post_screen", lambda _device: next(post_states))
    monkeypatch.setattr(publish_navigation, "tap_element", lambda *_args, **_kwargs: taps.append("next") or True)

    assert advance_to_post_screen(FakeDevice(), sleep=sleeps.append)
    assert taps == ["next"]
    assert sleeps == [1.5]


def test_advance_to_post_screen_returns_false_when_next_is_missing(monkeypatch):
    monkeypatch.setattr(publish_navigation, "is_post_screen", lambda _device: False)
    monkeypatch.setattr(publish_navigation, "tap_element", lambda *_args, **_kwargs: False)

    assert not advance_to_post_screen(FakeDevice(), sleep=lambda _seconds: None)
