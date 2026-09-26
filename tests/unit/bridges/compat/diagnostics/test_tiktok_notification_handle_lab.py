"""The Lab reaches the handle reads of the TikTok notifications pass through the production code.

`tt.activity.suggested.read_handle` is the step taken before a suggested follow,
`tt.inbox.resolve_thread_handle` the one taken after a wave, `tt.inbox.read_thread_handle` its
no-gesture read on an open thread; `tt.inbox.hello_candidates` and `tt.inbox.say_hello` cover the
wave itself, which had no Lab action.
"""

from types import SimpleNamespace

import pytest

from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions
from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions


@pytest.fixture(autouse=True)
def _registered():
    register_actions()


class _Dm:
    def __init__(self):
        self.calls = []

    def say_hello_candidates(self):
        return ["Ana B", "Bob"]

    def say_hello(self, name):
        self.calls.append(("say_hello", name))
        return True

    def read_conversation_handle(self):
        self.calls.append(("read",))
        return "ana.b"

    def resolve_conversation_handle(self, name):
        self.calls.append(("resolve", name))
        return None if name == "Bob" else "ana.b"


def test_the_suggested_handle_read_is_the_production_step(monkeypatch):
    seen = []

    def resolve(self, name):
        seen.append(name)
        return "jo.doe"

    monkeypatch.setattr(ActivityActions, "__init__", lambda self, device: None)
    monkeypatch.setattr(ActivityActions, "resolve_suggested_account_handle", resolve)

    result = ACTION_REGISTRY["tt.activity.suggested.read_handle"](SimpleNamespace(device=None), {"name": "Jo Doe"})

    assert seen == ["Jo Doe"]
    assert result["success"] is True
    assert result["details"] == {"name": "Jo Doe", "handle": "jo.doe"}


def test_the_suggested_handle_read_needs_a_name():
    result = ACTION_REGISTRY["tt.activity.suggested.read_handle"](SimpleNamespace(device=None), {})
    assert result["success"] is False


def test_the_thread_handle_actions_call_the_dm_actions():
    dm = _Dm()
    bundle = SimpleNamespace(dm=dm)

    assert ACTION_REGISTRY["tt.inbox.read_thread_handle"](bundle, {})["details"] == {"handle": "ana.b"}
    assert ACTION_REGISTRY["tt.inbox.resolve_thread_handle"](bundle, {"name": "Ana B"})["success"] is True
    assert ACTION_REGISTRY["tt.inbox.resolve_thread_handle"](bundle, {"name": "Bob"})["success"] is False
    assert dm.calls == [("read",), ("resolve", "Ana B"), ("resolve", "Bob")]


def test_the_wave_has_its_lab_actions():
    dm = _Dm()
    bundle = SimpleNamespace(dm=dm)

    assert ACTION_REGISTRY["tt.inbox.hello_candidates"](bundle, {})["details"] == {"names": ["Ana B", "Bob"]}
    assert ACTION_REGISTRY["tt.inbox.say_hello"](bundle, {"name": "Ana B"})["success"] is True
    assert ACTION_REGISTRY["tt.inbox.say_hello"](bundle, {})["success"] is False
    assert dm.calls == [("say_hello", "Ana B")]


def test_following_a_suggestion_from_the_lab_reports_its_outcome(monkeypatch):
    """The action logged through a name its module never imported: it raised after following."""
    monkeypatch.setattr(ActivityActions, "__init__", lambda self, device: None)
    monkeypatch.setattr(ActivityActions, "follow_suggested_account", lambda self, name: True)

    result = ACTION_REGISTRY["tt.activity.suggested.follow"](SimpleNamespace(device=None), {"name": "Jo Doe"})

    assert result == {"success": True, "message": "followed Jo Doe"}


@pytest.mark.parametrize("params, expand", [({}, True), ({"expand": False}, False), ({"expand": "false"}, False)])
def test_the_activity_open_can_stay_on_the_summary_the_suggestions_live_on(monkeypatch, params, expand):
    seen = []
    monkeypatch.setattr(ActivityActions, "__init__", lambda self, device: None)
    monkeypatch.setattr(ActivityActions, "open_activity", lambda self, expand=True: seen.append(expand) or True)

    result = ACTION_REGISTRY["tt.activity.open"](SimpleNamespace(device=None), params)

    assert seen == [expand]
    assert result["success"] is True
