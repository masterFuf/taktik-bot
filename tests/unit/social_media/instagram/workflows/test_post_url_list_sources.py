"""A post gathers TWO populations, and engaging either is the same intention.

`interact_with_post_likers` only ever read the likers bottom-sheet. The people who took the
time to WRITE a comment are a stronger signal, and reaching them is the same loop with a
different row source — which is exactly how the scraping side already models it
(`workflows/scraping/list_strategy`). These tests lock that abstraction.
"""

import types

from taktik.core.social_media.instagram.actions.business.workflows.common.list_sources import (
    make_commenters_source,
    make_likers_source,
    resolve_list_source,
)


class _FakeElement:
    def __init__(self, text, content_desc, clicked=None):
        self.text = text
        self.attrib = {"content-desc": content_desc}
        self._clicked = clicked if clicked is not None else []

    def click(self):
        self._clicked.append(self.text)


def _workflow(buttons=None, comments_open=True, scoped_buttons=None):
    """Minimal stand-in exposing only what the sources touch.

    `scoped_buttons` answers the comments-list-scoped query; `buttons` answers the
    whole-screen fallback, so a test can tell the two paths apart.
    """
    def _xpath(selector):
        scoped = selector.startswith('//*[@resource-id=')
        rows = scoped_buttons if (scoped and scoped_buttons is not None) else (buttons or [])
        if scoped and scoped_buttons is None:
            rows = []  # container not resolvable -> falls back to the whole screen
        return types.SimpleNamespace(all=lambda: list(rows), exists=comments_open)

    return types.SimpleNamespace(
        device=types.SimpleNamespace(
            xpath=_xpath,
            press=lambda _key: None,
        ),
        logger=types.SimpleNamespace(
            debug=lambda *a, **k: None, info=lambda *a, **k: None,
            warning=lambda *a, **k: None, error=lambda *a, **k: None,
        ),
        scroll_actions=types.SimpleNamespace(scroll_down=lambda: None),
        detection_actions=types.SimpleNamespace(
            get_visible_followers_with_elements=lambda: [{"username": "liker", "element": None}],
            get_row_follow_state=lambda _u: "follow_back",
            click_follower_in_list=lambda _u: True,
        ),
        _is_likers_popup_open=lambda: True,
        _scroll_likers_popup_up=lambda: True,
        _ensure_on_likers_popup=lambda force_back=False: True,
        _exit_wrong_likers_screen=lambda: None,
    )


# ── Which source a run gets ─────────────────────────────────────────────────

def test_likers_stays_the_default_for_anything_unrecognised():
    """A run that predates the option, or carries a typo, must behave exactly as before."""
    wf = _workflow()
    for mode in (None, "", "likers", "LIKERS", "garbage"):
        assert resolve_list_source(wf, mode).label == "likers"


def test_commenters_is_selectable_and_case_insensitive():
    wf = _workflow()
    assert resolve_list_source(wf, "commenters").label == "commenters"
    assert resolve_list_source(wf, "Commenters").label == "commenters"


# ── Reading commenter rows ──────────────────────────────────────────────────

def test_only_username_buttons_are_kept():
    """A commenter's username has an EMPTY content-desc; the action buttons around it
    (Reply / Like / See translation) carry a non-empty one."""
    buttons = [
        _FakeElement("alice", ""),            # username
        _FakeElement("Reply", "Reply"),       # action button
        _FakeElement("bob", ""),              # username
        _FakeElement("Like", "Like button"),  # action button
    ]
    rows = make_commenters_source(_workflow(buttons)).get_visible()
    assert [r["username"] for r in rows] == ["alice", "bob"]


def test_action_labels_are_rejected_even_with_an_empty_content_desc():
    buttons = [_FakeElement("Reply", ""), _FakeElement("Suivre", ""), _FakeElement("carol", "")]
    rows = make_commenters_source(_workflow(buttons)).get_visible()
    assert [r["username"] for r in rows] == ["carol"]


def test_non_username_text_is_rejected():
    buttons = [
        _FakeElement("this is a sentence, not a handle", ""),
        _FakeElement("", ""),
        _FakeElement("ok.user_1", ""),
    ]
    rows = make_commenters_source(_workflow(buttons)).get_visible()
    assert [r["username"] for r in rows] == ["ok.user_1"]


def test_at_sign_is_stripped():
    rows = make_commenters_source(_workflow([_FakeElement("@dave", "")])).get_visible()
    assert rows[0]["username"] == "dave"


def test_an_unreadable_screen_yields_no_rows_instead_of_raising():
    wf = _workflow()
    wf.device.xpath = lambda _sel: (_ for _ in ()).throw(RuntimeError("dump failed"))
    assert make_commenters_source(wf).get_visible() == []


def test_the_post_cards_own_counters_are_never_read_as_people():
    """Taken from a real dump (2026-02-08): under the comments sheet, the post card still
    exposes its like/comment/share counters as Buttons with an EMPTY content-desc and
    numeric text — shaped exactly like a username node. Scoping to the comments list
    removes them, and the count-shaped filter removes them again if scoping fails."""
    real_commenters = [
        _FakeElement("dianeou38", ""),
        _FakeElement("taktik_r2d2", ""),
        _FakeElement("maryonlnd", ""),
    ]
    post_counters = [_FakeElement(t, "") for t in ("18.5K", "428", "4", "97", "1,204")]

    scoped = _workflow(buttons=real_commenters + post_counters, scoped_buttons=real_commenters)
    assert [r["username"] for r in make_commenters_source(scoped).get_visible()] == [
        "dianeou38", "taktik_r2d2", "maryonlnd",
    ]

    # Container not resolvable -> whole-screen fallback, counters still rejected.
    unscoped = _workflow(buttons=real_commenters + post_counters)
    assert [r["username"] for r in make_commenters_source(unscoped).get_visible()] == [
        "dianeou38", "taktik_r2d2", "maryonlnd",
    ]


# ── Clicking ────────────────────────────────────────────────────────────────

def test_a_commenter_is_opened_through_its_own_element():
    """Unlike a follow-list row there is no stable by-username selector to re-find a
    commenter with, so the located element is what gets clicked."""
    clicked = []
    element = _FakeElement("alice", "", clicked)
    source = make_commenters_source(_workflow([element]))

    assert source.click("alice", element) is True
    assert clicked == ["alice"]


def test_clicking_without_an_element_fails_rather_than_guessing():
    assert make_commenters_source(_workflow()).click("alice", None) is False


# ── Row-level relationship check ────────────────────────────────────────────

def test_comment_rows_report_an_unknown_follow_state():
    """A comment row carries no follow button. 'unknown' is what the loop already treats
    as fail-open, so the relationship check falls back to the profile-level guard."""
    assert make_commenters_source(_workflow()).row_follow_state("alice") == "unknown"


def test_liker_rows_still_report_their_real_follow_state():
    assert make_likers_source(_workflow()).row_follow_state("alice") == "follow_back"
