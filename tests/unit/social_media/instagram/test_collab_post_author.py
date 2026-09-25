"""A post in collaboration is filed under its first author, never under the whole header line.

Seen on a phone (Pixel 4a, Instagram 410, hashtag #videoproduction): the author line of a
collaboration post reads "abelstudios.au et mark.kobakian", the hashtag workflow took it whole,
and the like was filed as `LIKE` on "@abelstudios.au et mark.kobakian", a profile that does not
exist. The Feed's cleaner glued the same line into "abelstudios.auetmark.kobakian", and the post
URL fallback returned it whole.

The header lines below are the shapes found in the Lab dumps (`row_feed_photo_profile_name`),
French and English, two authors or "N others". The rule needs no conjunction: a handle has no
space, so the first word is the first author in any language.
"""

import types

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.feed.post_actions import (
    FeedPostActionsMixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.hashtag.mixins.post_finder import (
    HashtagPostFinderMixin,
)
from taktik.core.social_media.instagram.actions.business.workflows.post_url.mixins.url_handling import (
    PostUrlHandlingMixin,
)
from taktik.core.social_media.instagram.ui.extractors import username_from_author_header
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_SELECTORS

COLLAB = "abelstudios.au et mark.kobakian"


@pytest.mark.parametrize("line, author", [
    ("abelstudios.au et mark.kobakian", "abelstudios.au"),
    ("studioalldaylong and ab.buxton", "studioalldaylong"),
    ("lisa.maria.b   and inseltreffbarbados", "lisa.maria.b"),
    ("meta   and 2 others", "meta"),
    ("lequartiergenial et 3 autres personnes", "lequartiergenial"),
    ("bazaarfrance   et cartier  ", "bazaarfrance"),
    ("chachafoodandtravel et cottage_ofilduloir", "chachafoodandtravel"),
    ("mo.de_festival", "mo.de_festival"),
    ("@Bob_Studio", "bob_studio"),
])
def test_the_first_handle_of_the_header_is_the_author(line, author):
    assert username_from_author_header(line) == author


@pytest.mark.parametrize("line", ["", "   ", None, "J’aime et 2 autres", ".bad et good"])
def test_a_line_that_starts_with_no_handle_names_no_author(line):
    assert username_from_author_header(line) is None


def _log():
    return types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None,
                                 warning=lambda *a, **k: None, error=lambda *a, **k: None)


class _El:
    def __init__(self, text):
        self.exists = text is not None
        self._text = text
        self.info = {'contentDescription': text or '', 'text': text or ''}
        self.attrib = {'content-desc': text or ''}

    def get_text(self):
        return self._text


class _Device:
    """Shows `text` on the selectors listed in `on`, nothing anywhere else."""

    def __init__(self, on, text):
        self.on = set(on)
        self.text = text

    def xpath(self, selector):
        return _El(self.text if selector in self.on else None)


def test_the_hashtag_files_a_collaboration_under_its_first_author():
    finder = object.__new__(HashtagPostFinderMixin)
    finder.logger = _log()
    finder.post_selectors = POST_SELECTORS
    finder.device = _Device(POST_SELECTORS.post_author_username_selectors[:1], COLLAB)
    finder._is_reel_post = lambda: False
    finder.ui_extractors = types.SimpleNamespace(
        extract_likes_count_from_ui=lambda **k: None, extract_comments_count_from_ui=lambda **k: None)

    metadata = finder._extract_current_post_metadata(is_reel=False)

    assert metadata['author'] == "abelstudios.au"


def test_the_feed_reads_the_first_author_not_a_glued_handle():
    feed = object.__new__(FeedPostActionsMixin)
    feed.logger = _log()
    feed._feed_selectors = {'post_author_username': ['author_sel'], 'post_author_avatar': []}
    feed.device = _Device(['author_sel'], COLLAB)

    assert feed._get_current_post_author() == "abelstudios.au"


def test_post_url_reads_the_first_author_from_the_header():
    handler = object.__new__(PostUrlHandlingMixin)
    handler.logger = _log()
    handler._hashtag_sel = types.SimpleNamespace(reel_author_container=['reel_sel'])
    handler.post_selectors = types.SimpleNamespace(
        profile_image_selectors=[], header_selectors=['header_sel'], username_extraction_selectors=[])
    handler.device = _Device(['header_sel'], COLLAB)

    assert handler._extract_author_username() == "abelstudios.au"


def test_post_url_text_fallback_never_returns_the_whole_line():
    handler = object.__new__(PostUrlHandlingMixin)
    handler.logger = _log()
    handler._hashtag_sel = types.SimpleNamespace(reel_author_container=['reel_sel'])
    handler.post_selectors = types.SimpleNamespace(
        profile_image_selectors=[], header_selectors=[], username_extraction_selectors=['text_sel'])
    handler.device = _Device([], None)
    handler._get_text_from_element = lambda selector: COLLAB

    assert handler._extract_author_username() == "abelstudios.au"
