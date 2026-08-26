"""The post card is ONE composition of four existing reads, and it fails soft.

A `social_posts` row needs the author, the counters, the caption and the share URL of the
open post. Each read has its own production owner; this checks the composition uses them
as production does (atomic counters first, framed-post reader for photos, reel selectors
for reels, share sheet only when asked) and that an unreadable value stays None — never a
zero that would overwrite a measurement the catalogue already holds.
"""

from types import SimpleNamespace

from taktik.core.database.instagram_post_identity import build_post_ref
from taktik.core.social_media.instagram.workflows.common import post_card


class _Extractors:
    def __init__(self, atomic=None, likes=0, comments=0):
        self._atomic, self._likes, self._comments = atomic, likes, comments
        self.calls = []

    def extract_post_stats_atomic(self):
        self.calls.append("atomic")
        return self._atomic

    def extract_likes_count_from_ui(self, is_reel=None):
        self.calls.append(("likes", is_reel))
        return self._likes

    def extract_comments_count_from_ui(self, is_reel=None):
        self.calls.append(("comments", is_reel))
        return self._comments


class _Scroll:
    def __init__(self, ctx):
        self._ctx = ctx

    def framed_post_context(self):
        return self._ctx


class _Element:
    def __init__(self, text="", desc=""):
        self.exists = True
        self._text, self._desc = text, desc

    @property
    def info(self):
        return {"text": self._text, "contentDescription": self._desc}

    def get_text(self):
        return self._text

    def all(self):
        return [self]


class _Missing:
    exists = False

    def all(self):
        return []


class _Device:
    """A device whose xpath answers by SUBSTRING of the selector — enough to route the
    catalogue's reel selectors (author / caption / date) and the reel indicator."""

    def __init__(self, answers):
        self._answers = answers

    def xpath(self, selector):
        for needle, element in self._answers.items():
            if needle in selector:
                return element
        return _Missing()


def _photo_device():
    return _Device({})  # no reel indicator, no reel selectors


def test_a_framed_photo_is_read_through_the_production_reader_without_the_share_sheet(monkeypatch):
    monkeypatch.setattr(post_card, "get_post_url_from_share", lambda *a, **k: (_ for _ in ()).throw(AssertionError("share sheet must not open")))
    scroll = _Scroll({
        "author": "alice",
        "header_desc": "alice a publié une photo le 9 août",
        # The UI glues the handle in front of the prose; the cleaner strips it (production path).
        "caption_text": "alice Nouvelle collection printemps disponible en boutique",
    })
    extractors = _Extractors(atomic={"likes": 96, "comments": 9})

    card = post_card.read_open_post_card(
        _photo_device(), ui_extractors=extractors, scroll_actions=scroll, with_url=False,
    )

    assert card.author == "alice"
    assert card.is_reel is False
    assert (card.likes_count, card.comments_count, card.counters_atomic) == (96, 9, True)
    assert card.caption == "Nouvelle collection printemps disponible en boutique"
    assert card.posted_at_label == "a publié une photo le 9 août"
    assert card.post_url is None
    assert card.post_ref == build_post_ref("alice", card.caption)
    assert extractors.calls == ["atomic"]


def test_the_share_url_is_canonicalised_when_asked_for(monkeypatch):
    monkeypatch.setattr(
        post_card, "get_post_url_from_share",
        lambda *a, **k: "https://www.instagram.com/p/DAbC123xyz/?igsh=MWQ1ZmE0NzE2Zg==",
    )
    card = post_card.read_open_post_card(
        _photo_device(), ui_extractors=_Extractors(atomic={"likes": 1, "comments": 0}),
        scroll_actions=_Scroll({"author": "alice", "header_desc": "alice a publié", "caption_text": ""}),
    )
    assert card.post_url == "https://www.instagram.com/p/DAbC123xyz/"


def test_unreadable_counters_stay_none_not_zero():
    # No atomic read, and the separate extractors answer their "found nothing" zero.
    extractors = _Extractors(atomic=None, likes=0, comments=0)
    card = post_card.read_open_post_card(
        _photo_device(), ui_extractors=extractors, with_url=False,
        scroll_actions=_Scroll({"author": "alice", "header_desc": "alice", "caption_text": ""}),
    )
    assert (card.likes_count, card.comments_count, card.counters_atomic) == (None, None, False)
    assert ("likes", False) in extractors.calls and ("comments", False) in extractors.calls


def test_separate_counters_are_kept_when_at_least_one_was_read():
    extractors = _Extractors(atomic=None, likes=120, comments=0)
    card = post_card.read_open_post_card(
        _photo_device(), ui_extractors=extractors, with_url=False,
        scroll_actions=_Scroll({"author": "alice", "header_desc": "alice", "caption_text": ""}),
    )
    assert (card.likes_count, card.comments_count, card.counters_atomic) == (120, 0, False)


def test_a_reel_is_read_through_the_reel_selectors():
    device = _Device({
        "Reel de": _Element(desc="Reel de bob, 96 J’aime, 9 commentaires, 9 août"),   # reel indicator
        "clips_author_username": _Element(text="bob"),
        "clips_caption_component\"]//android.widget.ScrollView": _Element(desc="bob Derrière les coulisses de l'atelier ce matin"),
        "clips_caption_component\"]//android.view.ViewGroup[@text]": _Element(text="31 octobre 2025"),
    })
    extractors = _Extractors(atomic={"likes": 96, "comments": 9})

    card = post_card.read_open_post_card(device, ui_extractors=extractors, with_url=False)

    assert card.is_reel is True
    assert card.author == "bob"
    assert card.caption == "Derrière les coulisses de l'atelier ce matin"
    assert card.posted_at_label == "31 octobre 2025"
    assert card.post_ref == build_post_ref("bob", card.caption)


def test_the_grid_owner_fills_in_when_no_author_is_readable():
    card = post_card.read_open_post_card(
        _photo_device(), ui_extractors=_Extractors(atomic={"likes": 3, "comments": 1}),
        scroll_actions=_Scroll(None), with_url=False, author_hint="@Carol",
    )
    assert card.author == "carol"
    assert card.caption is None
    assert card.post_ref == "carol"


def test_a_share_link_without_a_shortcode_yields_no_url(monkeypatch):
    monkeypatch.setattr(post_card, "get_post_url_from_share", lambda *a, **k: "https://www.instagram.com/alice/")
    card = post_card.read_open_post_card(
        _photo_device(), ui_extractors=_Extractors(atomic={"likes": 3, "comments": 1}),
        scroll_actions=_Scroll(None), author_hint="alice",
    )
    assert card.post_url is None


def test_as_dict_is_json_ready():
    card = post_card.PostCard("a", False, 1, 2, "c", None, None, "a:x", True)
    assert card.as_dict() == {
        "author": "a", "is_reel": False, "likes_count": 1, "comments_count": 2, "caption": "c",
        "posted_at_label": None, "post_url": None, "post_ref": "a:x", "counters_atomic": True,
    }
