"""The Feed files a post's gestures under the author of the FRAMED post, the post it likes.

It read the first author line of the screen. When the framed post's header sits just under the top
of the list, its own name line is out of the dump and the line read is the NEXT post's: 3 of the
135 landings of the Lab corpus whose post was framed (Pixel 3a, Instagram 410 in French, 163
`scroll.feed_next` runs, June 2026). When the post above still shows its header under the action
bar, the line read is that post's. The like, given to the framed post, was filed under another
account. The author is now the first handle of the framed post's own header description
(`framed_post_identity`, the reader of the like's own guards). A collaboration names several
accounts: its header description's first (Kevin's decision, 2026-09-28); its author line can start
with another account (2 landings of the corpus).

Real home feeds of that phone, anonymised (a handle-like word is `user_N`, another word `name_N`):
- `ig410_fr_feed_framed_header_without_its_name.xml`: the framed header just under the top of the
  list, its name line out of the dump; the next post's header and name line above the tabs;
- `ig410_fr_feed_header_under_action_bar.xml`: the post above's header under the action bar, the
  framed post's header below it;
- `ig410_fr_feed_collaboration_framed.xml`: a collaboration whose header description ("user_1 a
  publié ...") and author line ("name_18 et 2 autres personnes") start with two accounts;
- `ig410_fr_feed_framed_header_without_description.xml`: a framed header with no description (9
  landings of the corpus), its own name line inside it;
- `ig410_fr_feed_post_without_header.xml`: no header framed.
"""

import pytest
from loguru import logger

import taktik.core.shared.device.facade as shared_facade_module
import taktik.core.social_media.instagram.actions.atomic.scroll.feed_scroll as feed_scroll
import taktik.core.social_media.instagram.actions.atomic.scroll.post_reading as post_reading
import taktik.core.social_media.instagram.actions.business.actions.like.orchestration as orchestration
import taktik.core.social_media.instagram.actions.core.device.facade as facade_module
from profile_posts_phone import ProfilePostsPhone, capture, like_on_phone
from taktik.core.social_media.instagram.actions.business.workflows.feed.workflow import FeedBusiness
from taktik.core.social_media.instagram.ui.selectors.locales import set_active_locale
from taktik.core.social_media.instagram.ui.selectors.surfaces.feed import FEED_SELECTORS

PIXEL_3A_H = 2220
FRAMED_WITHOUT_ITS_NAME = capture("ig410_fr_feed_framed_header_without_its_name.xml")
ABOVE_UNDER_THE_BAR = capture("ig410_fr_feed_header_under_action_bar.xml")
COLLABORATION = capture("ig410_fr_feed_collaboration_framed.xml")
WITHOUT_DESCRIPTION = capture("ig410_fr_feed_framed_header_without_description.xml")
NO_HEADER = capture("ig410_fr_feed_post_without_header.xml")


@pytest.fixture(autouse=True)
def _french_phone_no_waits(monkeypatch):
    for module in (facade_module, shared_facade_module, post_reading, feed_scroll, orchestration):
        monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    set_active_locale("fr")
    yield
    set_active_locale(None)


def _feed(screen, likes_on_tap=False):
    """The Feed on the replayed phone, with the production like of a list and its readers."""
    phone = ProfilePostsPhone(screen=screen, height=PIXEL_3A_H, likes_on_tap=likes_on_tap)
    like = like_on_phone(phone)
    feed = object.__new__(FeedBusiness)
    feed.logger = logger.bind(module="test_feed_author_is_the_framed_posts")
    feed.like_business = like
    feed.scroll_actions = like.scroll_actions
    feed.device = like.device
    feed._feed_sel = FEED_SELECTORS
    feed._human_like_delay = lambda *_args, **_kwargs: None
    return feed


def test_a_framed_post_whose_name_line_is_off_screen_is_not_filed_under_the_next_one():
    assert _feed(FRAMED_WITHOUT_ITS_NAME)._get_current_post_author() == "user_1"


def test_the_post_above_under_the_action_bar_is_not_the_author():
    assert _feed(ABOVE_UNDER_THE_BAR)._get_current_post_author() == "name_15"


def test_a_collaboration_is_filed_under_the_first_account_of_its_header():
    assert _feed(COLLABORATION)._get_current_post_author() == "user_1"


def test_a_framed_header_without_description_is_named_by_its_own_name_line():
    """Its description is empty: the name line INSIDE the framed header, never another post's."""
    assert _feed(WITHOUT_DESCRIPTION)._get_current_post_author() == "name_1"


def test_no_framed_post_names_no_author():
    assert _feed(NO_HEADER)._get_current_post_author() is None


def test_the_like_of_the_framed_post_is_filed_under_its_own_author(monkeypatch):
    """The Feed's two calls: the author, then the like of the framed post filed under it."""
    monkeypatch.setattr(orchestration, "should_double_tap_like", lambda: False)
    feed = _feed(FRAMED_WITHOUT_ITS_NAME, likes_on_tap=True)

    author = feed._get_current_post_author()
    assert feed._like_current_post(record_as=author) is True

    assert feed.like_business.rows == [("user_1", "LIKE", 1)]
