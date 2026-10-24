"""Four TikTok screen capabilities of production that had no Lab action.

The read of our own profile at the start of every run (`ProfileActions.get_own_profile_info`), the
opening of a video in a profile's grid by the scraping (`ClickActions.open_profile_grid_post`),
the avatar crop of a visited profile (`AvatarActions.capture_avatar`) and the sound opened by its
name by the scraping (`SoundActions.open_sound_by_name`). Each action must call that function.
"""

from types import SimpleNamespace

import taktik.core.social_media.tiktok.actions.atomic.detection.avatar_actions as avatar_module
import taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions as sound_module
import taktik.core.social_media.tiktok.services.profile.profile_actions as profile_module
from bridges.tools.lab.actions.tiktok.profile import capture_avatar, open_grid_post, read_own
from bridges.tools.lab.actions.tiktok.video import open_sound_by_name
from taktik.core.social_media.tiktok.services.profile.profile_actions import TikTokProfileInfo


def test_our_profile_is_read_as_the_start_of_a_run_reads_it(monkeypatch):
    info = TikTokProfileInfo(username="our_account", display_name="Our", followers_count=120,
                             following_count=80, likes_count=900, bio="hello",
                             profile_pic_base64="data:image/jpeg;base64," + "A" * 4096)

    class _Profile:
        def __init__(self, device):
            assert device == "warm"

        def get_own_profile_info(self):
            return info

    monkeypatch.setattr(profile_module, "ProfileActions", _Profile)

    result = read_own(SimpleNamespace(device="warm"), {})

    assert result["success"] is True
    assert result["details"]["username"] == "our_account"
    assert result["details"]["followers_count"] == 120
    # The picture is said, never shipped: the stdout of the Lab stays light.
    assert "profile_pic_base64" not in result["details"]
    assert result["details"]["has_picture"] is True


def test_an_unreadable_own_profile_is_a_failure(monkeypatch):
    monkeypatch.setattr(profile_module, "ProfileActions",
                        type("P", (), {"__init__": lambda self, d: None, "get_own_profile_info": lambda self: None}))

    assert read_own(SimpleNamespace(device="warm"), {})["success"] is False


def test_a_grid_video_is_opened_by_the_production_tap():
    taps = []
    click = SimpleNamespace(open_profile_grid_post=lambda index: taps.append(index) or True)

    result = open_grid_post(SimpleNamespace(click=click), {"index": "2"})

    assert taps == [2]
    assert result["success"] is True


def test_the_avatar_is_cropped_by_the_production_capture(monkeypatch):
    class _Avatar:
        def __init__(self, device):
            assert device == "warm"

        def capture_avatar(self):
            return "data:image/jpeg;base64," + "A" * 8192

    monkeypatch.setattr(avatar_module, "AvatarActions", _Avatar)

    result = capture_avatar(SimpleNamespace(device="warm"), {})

    assert result["success"] is True
    assert result["details"] == {"extracted": True, "size_kb": 6}


def test_a_sound_is_opened_by_its_name_as_the_scraping_opens_it(monkeypatch):
    calls = []

    class _Sound:
        def __init__(self, device):
            assert device == "warm"

        def open_sound_by_name(self, query, *, index=0):
            calls.append((query, index))
            return "Umbrella (Ember Island)"

    monkeypatch.setattr(sound_module, "SoundActions", _Sound)

    result = open_sound_by_name(SimpleNamespace(device="warm"), {"query": " Umbrella ", "index": "1"})

    assert calls == [("Umbrella", 1)]
    assert result["success"] is True
    # The title the page shows, not the query: which sound a row is is only known once opened.
    assert result["details"]["title"] == "Umbrella (Ember Island)"


def test_no_query_opens_no_sound(monkeypatch):
    monkeypatch.setattr(sound_module, "SoundActions", lambda device: (_ for _ in ()).throw(AssertionError("searched")))

    assert open_sound_by_name(SimpleNamespace(device="warm"), {})["success"] is False
