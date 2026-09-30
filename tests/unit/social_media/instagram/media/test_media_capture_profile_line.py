"""The media capture's profile line leaves out what Instagram's answer did not carry: never 0 nor false.

The proxy reads a profile from Instagram's answer (`mitm_addon`) and the media capture forwards it
to the desktop as `profile_captured`, twice: the service (`MediaCaptureService._handle_profile_data`)
and the automation bridge's callback (`InstagramMediaCaptureRuntime._on_profile`). A counter the
answer did not carry went out as 0 (the `ProfileCapture` defaults, for a message without it) or
null (the addon's None, which the contract does not allow), a flag the message lacks as false: a
profile passed for a public one with 0 followers. And the capture's stats summed that None and
raised, which skipped the stop of the capture.

As the lot `correctifs` did for `send_profile_captured`: what was not read is left out of the line.
"""

import pytest

import bridges.instagram.automation.media_capture as bridge_media_capture
from taktik.core.social_media.instagram.media import MediaCaptureService

UNREAD_KEYS = ("follower_count", "following_count", "media_count", "is_private", "is_verified", "is_business")


def _service():
    sent = []
    service = MediaCaptureService(device_id="fake",
                                  desktop_bridge_callback=lambda kind, data: sent.append((kind, data)))
    return service, sent


def test_a_profile_answer_without_counters_sends_none_of_them():
    service, sent = _service()

    service._handle_proxy_message({"type": "profile_data", "username": "user_1", "biography": "bio_1"})

    ((kind, line),) = sent
    assert kind == "profile_captured"
    assert [key for key in UNREAD_KEYS if key in line] == [], f"sent as measures: {line}"
    assert line["username"] == "user_1" and line["biography"] == "bio_1"


def test_what_the_addon_could_not_read_is_left_out():
    # The addon sends each counter, None when Instagram's answer lacks it (a flag it lacks, the
    # addon still sends as false).
    service, sent = _service()

    service._handle_proxy_message({"type": "profile_data", "username": "user_2", "follower_count": None,
                                   "following_count": 12, "media_count": None, "is_private": False,
                                   "is_verified": False, "is_business": False})

    ((_kind, line),) = sent
    assert "follower_count" not in line and "media_count" not in line
    assert line["following_count"] == 12 and line["is_private"] is False


def test_what_was_read_goes_out_as_read():
    service, sent = _service()

    service._handle_proxy_message({"type": "profile_data", "username": "user_3", "follower_count": 120,
                                   "following_count": 0, "media_count": 7, "is_private": True,
                                   "is_verified": False, "is_business": False})

    ((_kind, line),) = sent
    assert {key: line[key] for key in UNREAD_KEYS} == {
        "follower_count": 120, "following_count": 0, "media_count": 7,
        "is_private": True, "is_verified": False, "is_business": False}


def test_the_capture_stats_count_only_the_followers_read():
    service, _sent = _service()
    service._handle_proxy_message({"type": "profile_data", "username": "user_4", "follower_count": 30})
    service._handle_proxy_message({"type": "profile_data", "username": "user_5", "follower_count": None})

    stats = service.get_stats()

    assert (stats["profiles_captured"], stats["total_followers"]) == (2, 30)


@pytest.fixture
def bridge_lines(monkeypatch):
    lines = []
    monkeypatch.setattr(bridge_media_capture, "send_message",
                        lambda line_type, **fields: lines.append({"type": line_type, **fields}))
    monkeypatch.setattr(bridge_media_capture, "send_log", lambda *_a, **_k: None)
    return lines


def test_the_bridges_line_leaves_out_what_was_not_read(bridge_lines):
    service, _sent = _service()
    service.on_profile_captured = bridge_media_capture.InstagramMediaCaptureRuntime._on_profile

    service._handle_proxy_message({"type": "profile_data", "username": "user_6", "follower_count": None,
                                   "following_count": 9})

    (line,) = bridge_lines
    assert line["type"] == "profile_captured" and line["username"] == "user_6"
    assert "follower_count" not in line and "is_private" not in line
    assert line["following_count"] == 9
