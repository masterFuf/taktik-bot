"""Writing on the comment sheet, and refusing to when the screen does not agree.

Every rule here was learned on a real sheet on 2026-08-29, the first day this surface was ever
opened. The device tests live in data/tiktok-parite/outils; these lock the decisions those
measurements forced.
"""

import re

from taktik.core.social_media.tiktok.actions.atomic.interaction.comment_actions import CommentActions


class _SilentLogger:
    def __init__(self):
        self.warnings = []

    def warning(self, message):
        self.warnings.append(message)

    def success(self, message):
        pass

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _Node:
    def __init__(self, text="", on_click=None):
        self.text = text
        self._on_click = on_click

    def click(self):
        if self._on_click:
            self._on_click(self)


class _LikeNode(_Node):
    """A like count lives on its own id inside the row, and only when the comment has likes."""


class _Result:
    def __init__(self, nodes):
        self._nodes = nodes

    def all(self):
        return self._nodes

    def get_text(self):
        return self._nodes[0].text if self._nodes else ""

    @property
    def exists(self):
        return bool(self._nodes)


class _Sheet:
    """A comment sheet built the way the real one is: a list of ROWS, each holding its own fields.

    The earlier double held two parallel lists, authors and bodies, and answered any body query
    with all of them at once. That is exactly the shape the production reader used, so the double
    could not express the bug it had: a row whose body node is absent drops out of the body list,
    and every pairing after it shifts by one. Rows here can carry an empty body, which is what a
    comment made of a single emoji looks like once the XML dump has eaten it.
    """

    def __init__(self, *, is_open=True, rows=None, authors=(), bodies=(), replies=0, composer=""):
        if rows is None:
            # Kept so the posting tests keep reading as they did; a row per author.
            rows = [
                {"author": author, "text": bodies[index] if index < len(bodies) else ""}
                for index, author in enumerate(authors)
            ]
        self.is_open = is_open
        self.rows = [dict(row) for row in rows]
        self.composer = composer
        self.tapped_reply = None
        self._replies = [
            _Node(on_click=lambda n, i=i: setattr(self, "tapped_reply", i))
            for i in range(replies)
        ]

    @property
    def authors(self):
        return [row["author"] for row in self.rows]

    def _row_index(self, selector):
        """The 1-based index a positional selector addresses, or None."""
        match = re.search(r"\)\[(\d+)\]", selector)
        return int(match.group(1)) if match else None

    def xpath(self, selector):
        # The sheet PANEL is what says the sheet is open -- one id per app version. The composer
        # affordance used to play that role and belongs to the VIDEO screen, so it answered yes
        # on a closed sheet; a double that still keyed on it would keep testing the bug.
        if any(f':id/{rid}"' in selector for rid in ("o3y", "ieb", "maf", "h7t")):
            return _Result([_Node()] if self.is_open else [])
        if "Mention" in selector or "Stickers" in selector:
            return _Result([_Node()])   # present whether or not the sheet is up

        index = self._row_index(selector)
        if index is not None and ":id/title" in selector:
            if index > len(self.rows):
                return _Result([])
            row = self.rows[index - 1]
            if "tv_like_count" in selector:
                likes = row.get("like_count")
                return _Result([_LikeNode(likes)] if likes else [])
            if "focusable" in selector:
                # The body is the row's focusable TextView. A row can have none -- an emoji-only
                # comment reads empty once the dump has eaten the emoji -- and the row still
                # renders its date and its reply label, which is what made "the first text after
                # the author" pick the wrong node twice over.
                body = row.get("text", "")
                return _Result([_Node(body)] if body else [])
            return _Result([_Node(row["author"])])

        if ":id/title" in selector and "focusable" not in selector:
            return _Result([_Node(row["author"]) for row in self.rows])
        if "focusable" in selector:
            return _Result([_Node(row["text"]) for row in self.rows if row.get("text")])
        if "Répondre" in selector or "Reply" in selector:
            return _Result(self._replies)
        if "EditText" in selector:
            return _Result([_Node(self.composer)])
        return _Result([])


def _actions(sheet) -> CommentActions:
    actions = CommentActions.__new__(CommentActions)
    actions.device = sheet
    actions.logger = _SilentLogger()
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.comments import (
        COMMENT_SELECTORS,
    )
    from taktik.core.social_media.tiktok.ui.selectors.surfaces.video import VIDEO_SELECTORS

    actions.comment_selectors = COMMENT_SELECTORS
    actions.video_selectors = VIDEO_SELECTORS
    return actions


# --- the gate --------------------------------------------------------------------------------


def test_an_open_but_empty_sheet_still_counts_as_open():
    """The failure this catches: the first indicator was a comment's LIKE button, which scores
    perfectly on a full sheet and answers NO on a video with no comments yet — so the bot would
    have refused to comment on exactly the videos where a first comment is worth something."""
    actions = _actions(_Sheet(is_open=True, authors=(), bodies=()))
    assert actions.is_comment_sheet_open() is True


def test_nothing_is_read_when_the_sheet_is_closed():
    """`title`, the id carrying an author, also resolves on the inbox and the feed. Reading
    without the gate returns a confident, wrong comment from whatever screen is up."""
    actions = _actions(_Sheet(is_open=False, authors=["someone"], bodies=["from another screen"]))
    assert actions.read_comments() == []
    assert any("not open" in w for w in actions.logger.warnings)


# --- reading ---------------------------------------------------------------------------------


def test_a_comment_keeps_its_own_body():
    actions = _actions(_Sheet(rows=[
        {"author": "marie", "text": "bonjour"},
        {"author": "paul", "text": "salut"},
    ]))
    assert actions.read_comments() == [
        {"author": "marie", "text": "bonjour", "like_count": None},
        {"author": "paul", "text": "salut", "like_count": None},
    ]


def test_a_comment_with_no_body_does_not_steal_the_next_one_s():
    """The bug this locks, found on a real sheet on 2026-08-30.

    Bodies were collected as one flat list with the empties dropped, then joined to the authors by
    index. A comment made of a single emoji reads as empty once the dump has eaten it -- so it
    contributed no entry, and from there every body was attributed to the person above its author.
    A scrape that hands an AI "what this person wrote" would have handed it a stranger's words.
    """
    actions = _actions(_Sheet(rows=[
        {"author": "marie", "text": ""},          # emoji-only, eaten by the dump
        {"author": "paul", "text": "salut"},
    ]))

    assert actions.read_comments() == [
        {"author": "marie", "text": "", "like_count": None},
        {"author": "paul", "text": "salut", "like_count": None},
    ]


def test_a_date_is_never_reported_as_a_body():
    """Inside a row the date follows the body. With the body absent, the first remaining text IS
    the date -- and calling it a comment is the same misattribution, one node further along."""
    actions = _actions(_Sheet(rows=[{"author": "marie", "text": "", "date": "06-11"}]))

    assert actions.read_comments() == [{"author": "marie", "text": "", "like_count": None}]


def test_a_missing_like_count_is_none_not_zero():
    """`tv_like_count` does not exist on 43.1.4 at all, and is absent on any comment with no
    like. Reporting 0 would state something the screen never said."""
    comments = _actions(_Sheet(rows=[{"author": "marie", "text": "bonjour"}])).read_comments()
    assert comments[0]["like_count"] is None


def test_a_like_count_is_read_from_its_own_row():
    actions = _actions(_Sheet(rows=[
        {"author": "marie", "text": "bonjour"},
        {"author": "paul", "text": "salut", "like_count": "783"},
    ]))
    assert [c["like_count"] for c in actions.read_comments()] == [None, "783"]


# --- posting ---------------------------------------------------------------------------------


def test_an_empty_comment_is_refused_before_anything_is_typed():
    actions = _actions(_Sheet())
    assert actions.post_comment("   ") is False


def test_posting_is_refused_when_the_sheet_is_closed():
    actions = _actions(_Sheet(is_open=False))
    assert actions.post_comment("bonjour") is False


# --- replying --------------------------------------------------------------------------------


def test_a_reply_targets_the_named_comment_not_the_first_of_that_author():
    """One person often leaves several comments. Measured on device with three comments sharing
    one author: without the body, the reply landed under the first of them."""
    sheet = _Sheet(authors=["marie", "marie", "paul"],
                   bodies=["premier", "deuxieme", "autre"], replies=3)
    actions = _actions(sheet)
    actions._tap_reply_of("marie", "deuxieme")
    assert sheet.tapped_reply == 1


def test_a_reply_to_a_body_that_is_not_there_is_refused():
    """Falling back to the first comment of that author would answer the wrong message."""
    sheet = _Sheet(authors=["marie"], bodies=["premier"], replies=1)
    actions = _actions(sheet)
    assert actions._tap_reply_of("marie", "does not exist") is False
    assert sheet.tapped_reply is None


def test_without_a_body_the_first_comment_of_that_author_is_used():
    """The documented, deliberate fallback — and the reason `to_text` exists."""
    sheet = _Sheet(authors=["marie", "marie"], bodies=["premier", "deuxieme"], replies=2)
    actions = _actions(sheet)
    assert actions._tap_reply_of("marie") is True
    assert sheet.tapped_reply == 0


def test_replying_is_refused_when_the_sheet_is_closed():
    actions = _actions(_Sheet(is_open=False, authors=["marie"], replies=1))
    assert actions.reply_to_comment("marie", "bonjour") is False

def test_a_reply_matches_to_text_against_the_right_person_s_row():
    """The bug: bodies came from one flat list joined to the rows by index, and that list drops
    rows whose body node is absent. With an emoji-only comment above them, `to_text` was compared
    to a neighbour's words -- so the reply went to the wrong comment, which is the exact failure
    `to_text` was added to prevent (one person often leaves several).

    Here marie's comment is body-less. paul's row must still be matched on paul's own words.
    """
    sheet = _Sheet(rows=[
        {"author": "marie", "text": ""},
        {"author": "paul", "text": "salut"},
    ], replies=2)
    actions = _actions(sheet)

    assert actions._tap_reply_of("paul", to_text="salut") is True
    assert sheet.tapped_reply == 1


def test_a_reply_is_refused_when_no_row_carries_that_text():
    """Answering the first comment that merely shares an author is worse than not answering."""
    sheet = _Sheet(rows=[{"author": "paul", "text": "salut"}], replies=1)
    actions = _actions(sheet)

    assert actions._tap_reply_of("paul", to_text="jamais ecrit") is False
    assert sheet.tapped_reply is None

