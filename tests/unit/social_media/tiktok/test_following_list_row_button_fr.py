"""T4: the French row button of TikTok's following list is the row's own Button.

The French entry had been framed on a profile header and found none of the 6 to 9 buttons of the
list, so the TikTok unfollow unfollowed nobody on a French phone. The screens below follow the
captures of TikTok 43.1.4 and 46.6.3 in French, as the device dumps them (every element a <node>,
the widget type an attribute) and evaluated by uiautomator2's own `d.xpath()` engine: a row is
avatar, names, then a clickable Button "Suivis" or "Ami(e)s" (no trailing space on the rows);
the tab title "Suivis 39" is a TextView. The usernames are invented: the dumps stay out of this
public repository.
"""

import pytest
from uiautomator2.xpath import XPathEntry

from taktik.core.social_media.tiktok.ui.labels import is_friends_button
from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _node(cls, text="", clickable="false", children=""):
    return (f'<node class="{cls}" text="{text}" resource-id="" content-desc="" clickable="{clickable}" '
            f'bounds="[0,0][10,10]">{children}</node>')


def _row(username, label):
    return _node("android.widget.LinearLayout", clickable="true", children=(
        _node("android.widget.FrameLayout")
        + _node("android.widget.LinearLayout", children=_node("android.widget.TextView", username))
        + _node("android.widget.Button", label, clickable="true")
    ))


def _screen(body):
    return f'<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">{body}</hierarchy>'


FOLLOWING_LIST = _screen(
    _node("android.widget.LinearLayout", clickable="true",
          children=_node("android.widget.TextView", "Suivis 39"))
    + _row("alpha_one", "Suivis") + _row("beta_two", "Ami(e)s") + _row("gamma_three", "Suivis")
)

# The trap the first entry fell into: a FOLLOWED profile's header. Its "Suivis " (trailing
# space, as captured) is a TextView inside a clickable container, next to the profile's Button.
FOLLOWED_PROFILE = _screen(
    _node("android.widget.LinearLayout", clickable="true", children=(
        _node("android.widget.TextView", "Suivis ")
        + _node("android.widget.Button", "@delta_four", clickable="true")
    ))
    + _node("android.widget.LinearLayout", clickable="true", children=(
        _node("android.widget.TextView", "39") + _node("android.widget.TextView", "Suivis")
    ))
)


class _Device:
    wait_timeout = 1.0

    def __init__(self, xml):
        self.xml = xml
        self.xpath = XPathEntry(self)

    def dump_hierarchy(self, *a, **k):
        return self.xml


def _found(xml):
    device = _Device(xml)
    return [el for sel in FOLLOWERS_SELECTORS.following_or_friends_button for el in device.xpath(sel).all()]


def test_every_row_button_of_the_following_list_is_found():
    assert [el.attrib.get("text") for el in _found(FOLLOWING_LIST)] == ["Suivis", "Ami(e)s", "Suivis"]


def test_a_followed_profile_header_is_not_a_row_button():
    assert _found(FOLLOWED_PROFILE) == []


def test_the_friends_option_recognises_what_the_selector_finds():
    """`include_friends=False` skips mutual rows by their label: it can only work on the
    Button's own text (the old match returned a container whose text is empty)."""
    labels = [el.attrib.get("text") for el in _found(FOLLOWING_LIST)]
    assert [is_friends_button(label) for label in labels] == [False, True, False]


def test_the_lab_counts_the_row_buttons_the_unfollow_taps():
    """Cartography Lab coverage: `tt.followers.count_anchors` reads the same catalogue field."""
    import types

    from bridges.compat.diagnostics.actions.tiktok import ACTION_REGISTRY, register_actions

    register_actions()
    bundle = types.SimpleNamespace(device=_Device(FOLLOWING_LIST))
    result = ACTION_REGISTRY["tt.followers.count_anchors"](bundle, {})
    assert result["details"]["following_or_friends_button"] == 3


def test_the_mutual_row_of_46_9_is_found_and_read_as_friends():
    """TikTok 46.9.3 writes the mutual button « Amis » (43.1.4 and 46.6.3: « Ami(e)s »); the tab
    title « Amis 6 » stays a TextView."""
    screen = _screen(
        _node("android.widget.LinearLayout", clickable="true",
              children=_node("android.widget.TextView", "Amis 6"))
        + _row("alpha_one", "Suivis") + _row("epsilon_five", "Amis")
    )
    labels = [el.attrib.get("text") for el in _found(screen)]
    assert labels == ["Suivis", "Amis"]
    assert [is_friends_button(label) for label in labels] == [False, True]
