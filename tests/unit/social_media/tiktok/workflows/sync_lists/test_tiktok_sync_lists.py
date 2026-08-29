"""Reading the operated account's own follow lists.

Every case here comes from a measurement on the two shipped versions (2026-08-29), because the
list screen is not the shape it looks like: it names only some of its rows, and the row's own
button carries the relationship.
"""

from taktik.core.social_media.tiktok.actions.business.workflows.sync_lists import (
    FOLLOWERS,
    FOLLOWING,
    SyncListsConfig,
    SyncListsWorkflow,
)
from taktik.core.social_media.tiktok.ui.labels import is_following_button, is_friends_button


class _SilentLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _Node:
    def __init__(self, text, top):
        self.text = text
        self.bounds = (0, top, 1080, top + 40)


class _Screen:
    """Answers each selector family with the nodes a real row layout would expose.

    The button family is matched FIRST and on its node type. Its production anchor is written in
    terms of the display-name id (`//android.widget.Button[../..//*[…txt_user_name]]` — a button
    whose grandparent names someone), so a fake that only looked for id substrings handed the
    display names back for the button query and every row's relationship came out as a name.
    """

    def __init__(self, names, handles, buttons):
        self._names = names
        self._handles = handles
        self._buttons = buttons

    def xpath(self, selector):
        if "android.widget.Button" in selector or ":id/tvn" in selector or ":id/rdh" in selector:
            return _Result(self._buttons)
        if "txt_desc" in selector or ":id/ygv" in selector:
            return _Result(self._handles)
        if "txt_user_name" in selector or ":id/yhq" in selector:
            return _Result(self._names)
        return _Result([])


class _Result:
    def __init__(self, nodes):
        self._nodes = nodes

    def all(self):
        return self._nodes


def _workflow(screen=None, **config_kwargs) -> SyncListsWorkflow:
    workflow = SyncListsWorkflow.__new__(SyncListsWorkflow)
    workflow.config = SyncListsConfig(**config_kwargs)
    workflow.logger = _SilentLogger()
    workflow.device = screen
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import (
        FOLLOWERS_SELECTORS,
    )

    workflow.selectors = FOLLOWERS_SELECTORS
    return workflow


# --- which list(s) a run reads -------------------------------------------------------------


def test_a_run_reads_the_list_it_was_asked_for():
    assert _workflow(list_type="following")._lists_to_sync() == [FOLLOWING]
    assert _workflow(list_type="followers")._lists_to_sync() == [FOLLOWERS]
    assert _workflow(list_type="both")._lists_to_sync() == [FOLLOWING, FOLLOWERS]


# --- the rows ------------------------------------------------------------------------------


def test_a_row_pairs_its_own_handle_and_button():
    screen = _Screen(
        names=[_Node("Charli", 100), _Node("Zach", 300)],
        handles=[_Node("charlidamelio", 160), _Node("zachking", 360)],
        buttons=[_Node("Suivis", 110), _Node("Ami(e)s", 310)],
    )
    rows = _workflow(screen)._read_visible_rows()
    assert rows == [
        {"display_name": "Charli", "username": "charlidamelio", "relationship": "Suivis"},
        {"display_name": "Zach", "username": "zachking", "relationship": "Ami(e)s"},
    ]


def test_a_missing_handle_does_not_shift_onto_the_next_row():
    """The whole reason the fields are paired by position and not by index.

    Measured: the FOLLOWING list renders the handle on roughly half its rows (19 of 39 on the
    test account). Zipping two lists together would have given the second person's handle to
    the first, and every row after it would be wrong too — silently, with plausible data.
    """
    screen = _Screen(
        names=[_Node("Diamanta97238", 100), _Node("Charli", 300)],
        handles=[_Node("charlidamelio", 360)],           # belongs to the SECOND row
        buttons=[_Node("Suivis", 110), _Node("Suivis", 310)],
    )
    rows = _workflow(screen)._read_visible_rows()
    assert rows[0]["display_name"] == "Diamanta97238"
    assert rows[0]["username"] == ""
    assert rows[1]["username"] == "charlidamelio"


def test_an_empty_field_is_not_a_row():
    screen = _Screen(names=[_Node("", 100), _Node("Zach", 300)], handles=[], buttons=[])
    rows = _workflow(screen)._read_visible_rows()
    assert [row["display_name"] for row in rows] == ["Zach"]


# --- the relationship ----------------------------------------------------------------------


def test_the_button_text_is_the_relationship():
    """One pass over a list gives both directions, because the row says which it is."""
    assert is_following_button("Suivis") is True
    assert is_following_button("Following") is True
    assert is_friends_button("Ami(e)s") is True
    assert is_friends_button("Friends") is True


def test_follow_back_is_not_following():
    """« Suivre en retour » means THEY follow US and we do not follow them. Reading it as "we
    follow them" would invert the relationship on every row of a followers list."""
    assert is_following_button("Suivre en retour") is False
    assert is_friends_button("Suivre en retour") is False
    assert is_following_button("Suivre") is False


# --- honesty about what was not read -------------------------------------------------------


def test_the_default_does_not_pay_a_visit_per_row():
    """Resolving unnamed rows costs one profile visit each; on a large account that is hours."""
    assert SyncListsConfig().resolve_missing_handles is False


def test_a_sync_is_incremental_by_default():
    assert SyncListsConfig().incremental is True
