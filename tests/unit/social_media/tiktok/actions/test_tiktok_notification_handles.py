"""The handles behind the two rows that only show display names: a suggested account, a wave.

The screens are invented and shaped like the 43.1.4 captures they stand for. A suggestion row
(Activity summary) holds a Button whose text is the display name, a clickable avatar, the follow
button and the remove button, and no handle; the handle is on the profile it opens. A thread
prints the display name in its header and `@handle` on the profile card at its top.
"""

import types

import pytest

import taktik.core.shared.actions.base_action as shared_base_action
import taktik.core.social_media.tiktok.actions.core.base_action as base_action
from taktik.core.shared.device.ui_dump import parse_ui_dump
from taktik.core.social_media.tiktok.actions.atomic.interaction.activity_actions import ActivityActions
from taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions import DMActions
import taktik.core.social_media.tiktok.services.profile.username as username_service

TT = "com.zhiliaoapp.musically:id"


def _screen(body):
    return ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
            f'<node class="android.widget.FrameLayout" package="com.zhiliaoapp.musically" '
            f'bounds="[0,0][1440,3120]">{body}</node></hierarchy>')


def _suggestion(name, button):
    return (
        '<node class="android.widget.LinearLayout" clickable="true" bounds="[0,2500][1440,2780]">'
        f'<node class="android.widget.FrameLayout" resource-id="{TT}/han" bounds="[42,2528][266,2752]">'
        f'<node class="android.widget.ImageView" resource-id="{TT}/b7o" content-desc="@2131888161" '
        'clickable="true" bounds="[56,2542][252,2738]"/></node>'
        f'<node class="android.widget.LinearLayout" resource-id="{TT}/n05" bounds="[266,2545][950,2735]">'
        '<node class="android.view.ViewGroup" bounds="[294,2545][908,2612]">'
        f'<node class="android.widget.Button" resource-id="{TT}/ntx" text="{name}" clickable="true" '
        'bounds="[294,2545][700,2612]"/></node>'
        f'<node class="android.widget.TextView" resource-id="{TT}/rdt" text="Te suit" '
        'bounds="[294,2623][433,2679]"/></node>'
        f'<node class="android.widget.Button" resource-id="{TT}/rdh" text="{button}" clickable="true" '
        'bounds="[950,2563][1258,2661]"/>'
        f'<node class="android.widget.Button" resource-id="{TT}/ew3" '
        f'content-desc="Supprimer {name} des comptes suggérés" clickable="true" '
        'bounds="[1300,2570][1384,2654]"/>'
        '</node>'
    )


ACTIVITY = _screen(
    '<node class="android.widget.ImageView" content-desc="Filtres" clickable="true" bounds="[1300,150][1400,250]"/>'
    + _suggestion("Jo Doe", "Suivre")
    + _suggestion("Cam Style", "Suivre en retour")
)


def _profile(handle):
    return _screen(
        f'<node class="android.widget.Button" resource-id="{TT}/qh5" text="@{handle}" '
        'clickable="true" bounds="[500,700][940,760]"/>'
    )


def _thread(header, *texts):
    card = "".join(
        f'<node class="android.widget.TextView" text="{text}" bounds="[500,{900 + 60 * i}][940,{950 + 60 * i}]"/>'
        for i, text in enumerate(texts)
    )
    return _screen(
        f'<node class="android.widget.ImageView" resource-id="{TT}/lep" content-desc="Retour" '
        'clickable="true" bounds="[0,150][120,250]"/>'
        f'<node class="android.widget.TextView" resource-id="{TT}/h4a" text="‎{header}" '
        'bounds="[140,150][800,250]"/>'
        f'<node class="android.widget.LinearLayout" resource-id="{TT}/qgb" bounds="[300,800][1140,1300]">'
        f'{card}</node>'
    )


class _Element:
    def __init__(self, node, device):
        self._node = node
        self._device = device
        self.text = node.get("text") or ""
        self.info = {"contentDescription": node.get("content-desc") or "", "text": self.text}

    def click(self):
        self._device.tapped(self._node)


class _Selection:
    def __init__(self, nodes, device):
        self._elements = [_Element(node, device) for node in nodes]

    @property
    def exists(self):
        return bool(self._elements)

    def all(self):
        return list(self._elements)

    def get_text(self):
        return self._elements[0].text if self._elements else None

    def get(self, timeout=None):
        raise RuntimeError("bounds are not read in this double")

    def click(self):
        self._elements[0].click()


class _Phone:
    """A phone with a current screen, what each tap opens, and where back leads."""

    def __init__(self, screen, *, opens=None, back=None):
        self.screen = screen
        self.opens = opens or {}
        self.back = back or {}
        self.taps = []

    def xpath(self, selector):
        return _Selection(parse_ui_dump(self.screen).xpath(selector), self)

    def dump_hierarchy(self, *_args, **_kwargs):
        """What the facade's photos are taken from, as on a real phone."""
        return self.screen

    def tapped(self, node):
        label = node.get("text") or node.get("resource-id") or node.get("content-desc")
        self.taps.append(label)
        self.screen = self.opens.get(label, self.screen)

    def press_back(self):
        self.taps.append("back")
        self.screen = self.back.get(self.screen, self.screen)

    def press(self, _key):
        self.press_back()


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    for module in (base_action, shared_base_action):
        monkeypatch.setattr(module.time, "sleep", lambda *_a, **_k: None)
    # The profile reader polls on the clock: each poll moves it on, so a wait ends at once.
    clock = iter(range(0, 10_000))
    monkeypatch.setattr(username_service, "time",
                        types.SimpleNamespace(time=lambda: next(clock), sleep=lambda *_a: None))
    import taktik.core.social_media.tiktok.actions.atomic.messaging.dm_actions as dm_module

    monkeypatch.setattr(dm_module.time, "sleep", lambda *_a, **_k: None)


def _activity(phone):
    actions = ActivityActions(phone)
    actions._human_like_delay = lambda *_a, **_k: None
    return actions


def _dm(phone):
    actions = DMActions(phone)
    actions._human_like_delay = lambda *_a, **_k: None
    return actions


def test_a_suggestion_handle_is_read_on_its_profile_and_the_page_comes_back():
    profile = _profile("jo.doe")
    phone = _Phone(ACTIVITY, opens={"Jo Doe": profile}, back={profile: ACTIVITY})

    handle = _activity(phone).resolve_suggested_account_handle("Jo Doe")

    assert handle == "jo.doe"
    assert phone.taps == ["Jo Doe", "back"]
    assert phone.screen == ACTIVITY


def test_the_tap_is_scoped_to_the_named_row():
    profile = _profile("cam_style")
    phone = _Phone(ACTIVITY, opens={"Cam Style": profile}, back={profile: ACTIVITY})

    assert _activity(phone).resolve_suggested_account_handle("Cam Style") == "cam_style"
    assert phone.taps[0] == "Cam Style"


def test_a_tap_that_opens_no_profile_gives_no_handle_and_leaves_the_page_alone():
    phone = _Phone(ACTIVITY)

    assert _activity(phone).resolve_suggested_account_handle("Jo Doe") is None
    assert "back" not in phone.taps
    assert phone.screen == ACTIVITY


def test_a_handle_read_on_a_screen_the_page_does_not_come_back_from_is_dropped():
    profile = _profile("jo.doe")
    phone = _Phone(ACTIVITY, opens={"Jo Doe": profile})

    assert _activity(phone).resolve_suggested_account_handle("Jo Doe") is None


def test_the_thread_card_gives_the_handle_and_the_header_does_not():
    phone = _Phone(_thread("Ana B", "@ana.b", "36 suivis · 105 followers"))

    assert _dm(phone).read_conversation_handle() == "ana.b"


def test_two_handles_on_the_card_are_not_guessed_between():
    phone = _Phone(_thread("Ana B", "@ana.b", "@someone_else"))

    assert _dm(phone).read_conversation_handle() == ""


def test_a_thread_whose_header_is_not_the_row_name_is_not_believed(monkeypatch):
    phone = _Phone(_thread("Anabelle", "@anabelle"))
    dm = _dm(phone)
    monkeypatch.setattr(dm, "click_conversation", lambda name: True)
    back = []
    monkeypatch.setattr(dm, "go_back_to_inbox", lambda: back.append(True) or True)

    assert dm.resolve_conversation_handle("Ana") is None
    assert back == [True]


def test_the_thread_of_the_row_gives_its_handle_and_goes_back(monkeypatch):
    phone = _Phone(_thread("Ana B", "@ana.b"))
    dm = _dm(phone)
    monkeypatch.setattr(dm, "click_conversation", lambda name: True)
    back = []
    monkeypatch.setattr(dm, "go_back_to_inbox", lambda: back.append(True) or True)

    assert dm.resolve_conversation_handle("‎Ana B") == "ana.b"
    assert back == [True]
