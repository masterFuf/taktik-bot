"""Six TikTok screen capabilities of production that the Lab did not run as production does.

The read of our own profile at the start of every run (`ProfileActions.get_own_profile_info`), the
opening of a video in a profile's grid by the scraping (`ClickActions.open_profile_grid_post`), the
avatar crop of a visited profile (`AvatarActions.capture_avatar`), the sound opened by its name by
the scraping (`SoundActions.open_sound_by_name`), the popup chain of every workflow
(`PopupHandler.close_all`) and the inbox notifications as the inbox command reads them
(`DMWorkflow.read_notifications`). Each action must call that function.
"""

from types import SimpleNamespace

import pytest

import taktik.core.social_media.tiktok.actions.atomic.detection.avatar_actions as avatar_module
import taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions as sound_module
import taktik.core.social_media.tiktok.services.profile.profile_actions as profile_module
import taktik.core.social_media.tiktok.workflows.common.popup_handler as popup_handler_module
import taktik.core.social_media.tiktok.workflows.dm.workflow as dm_workflow_module
from bridges.tools.lab.actions.tiktok.inbox import get_notifications
from bridges.tools.lab.actions.tiktok.popups import close_all
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


# The popup chain of every TikTok workflow (`PopupHandler.close_all`), which the Lab only knew
# closer by closer: the order, the inbox escaped, the refusal left alone were never tested as one.



class _Chain:
    calls = []
    closes = True

    def __init__(self, click, detection, owned_surfaces=frozenset()):
        _Chain.calls.append(("init", click, detection, owned_surfaces))

    def close_all(self, screen=None):
        _Chain.calls.append(("close_all", screen))
        return _Chain.closes


def _bundle(popups):
    screen = SimpleNamespace(popups=set(popups))
    return SimpleNamespace(click="click", detection=SimpleNamespace(read_screen=lambda: screen),
                           device="warm"), screen


def test_the_chain_of_the_workflows_closes_on_the_photo_of_the_turn(monkeypatch):
    _Chain.calls, _Chain.closes = [], True
    monkeypatch.setattr(popup_handler_module, "PopupHandler", _Chain)
    bundle, screen = _bundle({"collections"})

    result = close_all(bundle, {})

    assert _Chain.calls[0][:3] == ("init", "click", bundle.detection)
    assert _Chain.calls[0][3] == frozenset()
    # One photo for the turn, as a For You turn reads it: the chain takes no dump of its own.
    assert _Chain.calls[1] == ("close_all", screen)
    assert result["success"] is True
    assert result["details"] == {"found": ["collections"], "closed": True}


def test_a_refusal_is_left_on_screen_and_said(monkeypatch):
    _Chain.calls, _Chain.closes = [], False
    monkeypatch.setattr(popup_handler_module, "PopupHandler", _Chain)
    bundle, _ = _bundle({"action_blocked"})

    result = close_all(bundle, {})

    assert result["success"] is False
    assert "refuses" in result["message"]


def test_a_popup_seen_and_not_closed_is_a_failure(monkeypatch):
    _Chain.calls, _Chain.closes = [], False
    monkeypatch.setattr(popup_handler_module, "PopupHandler", _Chain)
    bundle, _ = _bundle({"gdpr"})

    result = close_all(bundle, {})

    assert result["success"] is False
    assert result["details"] == {"found": ["gdpr"], "closed": False}


# The notifications of the inbox, read as the inbox command reads them (`DMWorkflow.read_notifications`,
# `inbox_agent_handler`): the list brought back to its top first. The Lab read the atomic alone, which
# reads empty on a list another command left scrolled down, while the workflow reads it.


def test_the_inbox_notifications_are_read_by_the_workflow_read(monkeypatch):
    calls = []

    class _Inbox:
        def __init__(self, device):
            calls.append(("init", device))

        def read_notifications(self, max_items=20):
            calls.append(("read", max_items))
            return [{"title": "x", "category": "activity"}]

    monkeypatch.setattr(dm_workflow_module, "DMWorkflow", _Inbox)
    bundle = SimpleNamespace(device="warm",
                             dm=SimpleNamespace(get_inbox_notifications=lambda *_a: pytest.fail("atomic alone")))

    result = get_notifications(bundle, {"max_items": "7"})

    assert calls == [("init", "warm"), ("read", 7)]
    assert result == [{"title": "x", "category": "activity"}]
