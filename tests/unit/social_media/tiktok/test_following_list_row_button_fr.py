"""T4: the French row button of TikTok's following list is the row's own Button.

The French entry had been framed on a profile header and found none of the 6 to 9 buttons of the
list, so the TikTok unfollow unfollowed nobody on a French phone. The structure below follows the
captures of TikTok 43.1.4 and 46.6.3 in French (row: avatar, names, then a clickable Button
"Suivis" or "Ami(e)s" with a trailing space; tab title "Suivis 39" is a TextView); the usernames
are invented, the dumps stay out of this public repository.
"""

import pytest
from lxml import etree

from taktik.core.social_media.tiktok.ui.selectors.locales import set_active_locale
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS


@pytest.fixture(autouse=True)
def french():
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _row(username, label):
    return (
        '<android.widget.LinearLayout clickable="true">'
        '<android.widget.FrameLayout clickable="false"/>'
        f'<android.widget.LinearLayout clickable="false"><android.widget.TextView text="{username}"/></android.widget.LinearLayout>'
        f'<android.widget.Button text="{label} " clickable="true"/>'
        '</android.widget.LinearLayout>'
    )


FOLLOWING_LIST = etree.fromstring(
    '<hierarchy>'
    '<android.widget.LinearLayout clickable="true"><android.widget.TextView text="Suivis 39"/></android.widget.LinearLayout>'
    + _row("alpha_one", "Suivis") + _row("beta_two", "Ami(e)s") + _row("gamma_three", "Suivis")
    + '</hierarchy>'
)

# A profile header: the "Suivis" counter label next to its value, and the profile's own Button.
PROFILE_HEADER = etree.fromstring(
    '<hierarchy><android.widget.LinearLayout clickable="true">'
    '<android.widget.TextView text="39"/><android.widget.TextView text="Suivis"/>'
    '</android.widget.LinearLayout>'
    '<android.widget.Button text="Modifier le profil" clickable="true"/></hierarchy>'
)


def _matches(tree):
    return [node for sel in FOLLOWERS_SELECTORS.following_or_friends_button for node in tree.xpath(sel)]


def test_every_row_button_of_the_following_list_is_found():
    labels = [node.get("text").strip() for node in _matches(FOLLOWING_LIST)]
    assert labels == ["Suivis", "Ami(e)s", "Suivis"]


def test_the_tab_title_and_a_profile_header_are_not_row_buttons():
    assert _matches(PROFILE_HEADER) == []
    assert all(node.tag == "android.widget.Button" for node in _matches(FOLLOWING_LIST))
