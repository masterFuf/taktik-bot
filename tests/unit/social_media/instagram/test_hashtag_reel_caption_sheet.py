"""A reel opened from a hashtag grid is read without touching it, and a stray comments sheet
is closed before the post is engaged.

Device dumps of 2026-09-24 (IG 447, French): on the reel as it opens, the caption is collapsed
("…") and the like button sits in the action column; ONE tap on `clips_caption_component`
opens the caption-and-comments sheet over the reel -- the like button is gone and the thread
composer ("Rejoindre la conversation…") appears. The hashtag metadata read tapped that caption
to expand it, the like was then refused ("Not on a post screen"), and the run went on inside the
sheet until a comment was published there.

The two screens below reproduce the structure of those dumps with invented names and text.
"""

import types

import pytest
from lxml import etree

from taktik.core.compat.selectors.setup import _load_yaml_overrides, _resolve_overrides_for_version
from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
    HashtagBusiness,
)
from taktik.core.social_media.instagram.ui.selectors import locales
from taktik.core.social_media.instagram.ui.selectors.shell.screen_state import DETECTION_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.hashtag import HASHTAG_SELECTORS
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_SELECTORS
from taktik.core.social_media.instagram.workflows.management.session import stop_reasons

ID = "com.instagram.android:id/"
CAPTION = "Une legende inventee pour ce test, assez longue pour etre repliee par Instagram …"

# The reel as it opens from the grid (structure of dump 2).
REEL_OPEN = f"""<hierarchy>
<node class="android.widget.FrameLayout" resource-id="{ID}clips_viewer_container" bounds="[0,0][1080,2400]">
  <node class="android.view.ViewGroup" resource-id="{ID}clips_media_component" clickable="false"
        content-desc="Reel de demo_author. Appuyez deux fois pour lire ou mettre en pause." bounds="[0,132][1080,2179]"/>
  <node class="android.view.ViewGroup" resource-id="{ID}clips_author_info_component" bounds="[42,1860][900,1940]">
    <node class="android.widget.Button" resource-id="{ID}clips_author_username" clickable="true"
          text="demo_author\u00a0\u00a0" content-desc="demo_author\u00a0\u00a0" bounds="[137,1874][453,1922]"/>
  </node>
  <node class="android.view.ViewGroup" resource-id="{ID}clips_caption_component" bounds="[42,1954][943,2116]">
    <node class="android.widget.ScrollView" bounds="[42,1954][943,2116]">
      <node class="android.view.ViewGroup" bounds="[42,1965][943,2116]">
        <node class="android.view.ViewGroup" clickable="true" content-desc="{CAPTION}" bounds="[42,1965][943,2116]"/>
      </node>
    </node>
  </node>
  <node class="android.view.ViewGroup" resource-id="{ID}clips_ufi_component" bounds="[943,1005][1080,2153]">
    <node class="android.widget.ImageView" resource-id="{ID}like_button" clickable="true" content-desc="J’aime" bounds="[943,1229][1059,1345]"/>
    <node class="android.widget.ImageView" resource-id="{ID}comment_button" clickable="true" content-desc="Commentaire" bounds="[943,1407][1059,1523]"/>
  </node>
  <node class="android.widget.LinearLayout" resource-id="{ID}comment_composer_inner_layout" bounds="[42,2200][1038,2326]">
    <node class="android.widget.Button" resource-id="{ID}comment_composer_text_view" clickable="true"
          text="Ajoutez un commentaire…" bounds="[42,2200][1038,2326]"/>
  </node>
</node>
</hierarchy>"""

# One second after a single tap on the caption (structure of dump 3).
SHEET_OPEN = f"""<hierarchy>
<node class="android.widget.FrameLayout" resource-id="{ID}clips_viewer_container" bounds="[0,0][1080,2400]">
  <node class="android.view.ViewGroup" resource-id="{ID}clips_media_component" clickable="false"
        content-desc="Reel de demo_author. Appuyez deux fois pour lire ou mettre en pause." bounds="[0,132][1080,2179]"/>
  <node class="android.widget.LinearLayout" resource-id="{ID}comment_composer_inner_layout" bounds="[42,2200][1038,2326]">
    <node class="android.widget.Button" resource-id="{ID}comment_composer_text_view" clickable="true"
          text="Ajoutez un commentaire…" bounds="[42,2200][1038,2326]"/>
  </node>
  <node class="android.widget.FrameLayout" resource-id="{ID}layout_container_bottom_sheet" clickable="true" bounds="[0,132][1080,2337]">
    <node class="android.widget.FrameLayout" resource-id="{ID}bottom_sheet_drag_handle_frame" bounds="[0,1014][1080,1083]"/>
    <node class="android.widget.Button" resource-id="{ID}clips_author_username" clickable="true"
          text="demo_author\u00a0\u00a0" bounds="[150,1143][466,1191]"/>
    <node class="android.widget.AutoCompleteTextView" resource-id="{ID}layout_comment_thread_edittext_multiline"
          clickable="true" text="Rejoindre la conversation…" hint="Rejoindre la conversation…" bounds="[148,2232][833,2327]"/>
  </node>
</node>
</hierarchy>"""


def _tree(xml):
    """The screen as uiautomator2 queries it: each node renamed after its class."""
    tree = etree.fromstring(xml.encode("utf-8"))
    for node in tree.iter("node"):
        node.tag = node.get("class")
    return tree


def _matches(xml, selector):
    return len(_tree(xml).xpath(selector))


@pytest.fixture
def french():
    before = locales.active_locale()
    locales.set_active_locale("fr")
    yield
    locales.set_active_locale(before)


def _sheet_indicators_on_447():
    """The comments-sheet detector the phone runs on IG 447 (version overrides included)."""
    overrides = _resolve_overrides_for_version(_load_yaml_overrides("instagram"), "447.0.0.55.81")
    return overrides["popup._comments_view_indicators_base"]


# ─────────────────────────────────────────────────── what each screen answers

def test_the_like_button_is_on_the_reel_and_not_under_the_sheet(french):
    """Why "Not on a post screen" was the right answer once the sheet was open."""
    hits = lambda xml: sum(_matches(xml, s) for s in DETECTION_SELECTORS.post_screen_indicators)
    assert hits(REEL_OPEN) > 0
    assert hits(SHEET_OPEN) == 0


def test_the_447_sheet_detector_sees_the_sheet_and_not_the_reel():
    """The reel carries a composer ENTRY of its own ("Ajoutez un commentaire…"), so a detector
    keyed on `comment_composer` would close sheets that are not there. The thread field is the
    proof of the sheet."""
    hits = lambda xml: sum(_matches(xml, s) for s in _sheet_indicators_on_447())
    assert hits(SHEET_OPEN) > 0
    assert hits(REEL_OPEN) == 0


def test_the_caption_and_the_author_are_readable_without_a_tap(french):
    assert _matches(REEL_OPEN, POST_SELECTORS.reel_caption_selectors[0]) == 1
    assert _matches(REEL_OPEN, POST_SELECTORS.reel_author_username_selectors[0]) == 1


# ─────────────────────────────────────────────────── the metadata read

class _Element:
    def __init__(self, nodes, taps):
        self._nodes = nodes
        self._taps = taps
        self.exists = bool(nodes)

    @property
    def info(self):
        node = self._nodes[0]
        return {'contentDescription': node.get('content-desc', ''), 'text': node.get('text', '')}

    def get_text(self):
        return self._nodes[0].get('text') if self._nodes else None

    def click(self):
        self._taps.append(self._nodes[0].get('resource-id') or self._nodes[0].get('content-desc'))

    def all(self):
        return [_Element([node], self._taps) for node in self._nodes]


class _Screen:
    """A device that answers xpath queries from one XML screen and records every tap."""

    def __init__(self, xml):
        self._tree = _tree(xml)
        self.taps = []

    def xpath(self, selector):
        try:
            nodes = self._tree.xpath(selector)
        except etree.XPathEvalError:
            nodes = []
        return _Element(nodes, self.taps)


def _log():
    return types.SimpleNamespace(debug=lambda *a, **k: None, info=lambda *a, **k: None,
                                 warning=lambda *a, **k: None, error=lambda *a, **k: None)


def _reader(xml):
    host = HashtagBusiness.__new__(HashtagBusiness)
    host.device = _Screen(xml)
    host.logger = _log()
    host.post_selectors = POST_SELECTORS
    host._hashtag_sel = HASHTAG_SELECTORS
    host._is_reel_post = lambda: True
    host.ui_extractors = types.SimpleNamespace(
        extract_likes_count_from_ui=lambda is_reel=None: 120,
        extract_comments_count_from_ui=lambda is_reel=None: 4,
    )
    return host


@pytest.fixture
def no_wait(monkeypatch):
    import taktik.core.social_media.instagram.actions.business.workflows.hashtag.mixins.post_finder as finder
    monkeypatch.setattr(finder.time, 'sleep', lambda *_a, **_k: None)


def test_a_collapsed_reel_caption_is_read_and_never_tapped(french, no_wait):
    host = _reader(REEL_OPEN)

    metadata = host._extract_current_post_metadata(is_reel=True)

    assert host.device.taps == [], "the caption tap is what opens the comments sheet on IG 447"
    assert metadata['author'] == 'demo_author'
    assert metadata['caption'].startswith('Une legende inventee')
    assert metadata['caption_hash']


# ─────────────────────────────────────────────────── the stray sheet

class _Keys:
    """Closes the sheet after `closes_after` back presses; records which API was used."""

    def __init__(self, closes_after):
        self.closes_after = closes_after
        self.back_presses = 0
        self.facade_presses = []

    def press_back(self):
        self.back_presses += 1

    def press(self, key):
        self.facade_presses.append(key)  # the Instagram facade's press('back') does nothing

    def is_open(self):
        return self.closes_after is None or self.back_presses < self.closes_after


def _sheet_host(closes_after):
    keys = _Keys(closes_after)
    host = HashtagBusiness.__new__(HashtagBusiness)
    host.device = keys
    host.logger = _log()
    host._is_comments_view_open = keys.is_open
    return host, keys


@pytest.fixture
def no_sheet_wait(monkeypatch):
    import taktik.core.social_media.instagram.actions.business.workflows.hashtag.mixins.post_detection as detection
    monkeypatch.setattr(detection.time, 'sleep', lambda *_a, **_k: None)


def test_no_sheet_means_no_key_press(no_sheet_wait):
    host, keys = _sheet_host(closes_after=0)

    assert host._close_stray_comments_sheet() is True
    assert keys.back_presses == 0


def test_a_stray_sheet_is_closed_with_the_working_back_key(no_sheet_wait):
    """First press may only hide the keyboard: the second closes the sheet."""
    host, keys = _sheet_host(closes_after=2)

    assert host._close_stray_comments_sheet() is True
    assert keys.back_presses == 2
    assert keys.facade_presses == []


def test_a_sheet_that_will_not_close_is_reported(no_sheet_wait):
    host, keys = _sheet_host(closes_after=None)

    assert host._close_stray_comments_sheet() is False
    assert keys.back_presses == HashtagBusiness._STRAY_SHEET_BACK_PRESSES


# ─────────────────────────────────────────────────── the posts loop

class _Loop(HashtagBusiness):
    """The posts loop with one reel on screen and a comments sheet that may not close."""

    def __init__(self, sheet_closes):
        self.logger = _log()
        self.session_manager = None
        self.automation = None
        self.engaged = []
        self._sheet_closes = sheet_closes
        self.stats_manager = types.SimpleNamespace(increment=lambda *a, **k: None,
                                                   display_final_stats=lambda **k: None)
        self.scroll_actions = types.SimpleNamespace(human_reading_pause=lambda **k: None)

    def _find_first_valid_post(self, hashtag, config, skip_count=0):
        return {'likes_count': 120, 'comments_count': 4, 'is_reel': True}

    def _extract_current_post_metadata(self, is_reel=False):
        return {'author': 'demo_author', 'likes_count': 120, 'comments_count': 4, 'caption_hash': 'h'}

    def _close_stray_comments_sheet(self):
        return self._sheet_closes

    def _engage_one_post(self, hashtag, plan, effective_config, stats, is_reel, author):
        self.engaged.append(author)
        return False

    def _swipe_to_next_post(self, known_signature=None):
        return False


@pytest.fixture
def no_store(monkeypatch):
    import taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow as mod
    monkeypatch.setattr(mod.InstagramHashtagPostService, 'is_processed', staticmethod(lambda **k: False))
    monkeypatch.setattr(mod.IPCEmitter, 'emit_current_post', staticmethod(lambda **k: None))


def _run(loop):
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag.interaction_plan import (
        resolve_interaction_plan,
    )
    plan = resolve_interaction_plan({'engage_posts': True, 'max_posts': 3})
    stats = {'posts_analyzed': 0, 'likes_made': 0, 'comments_made': 0,
             'users_interacted': 0, 'errors': 0}
    config = {'min_likes': 0, 'max_likes': 10 ** 9, 'max_posts_to_analyze': 5}
    return loop._run_interaction_plan('demo', plan, config, stats, account_id=7, finalize=False)


def test_a_sheet_that_stays_open_stops_the_run_before_any_gesture(no_store):
    loop = _Loop(sheet_closes=False)

    stats = _run(loop)

    assert loop.engaged == []
    assert getattr(stats['stop_reason'], 'code', None) == 'navigation_lost'
    assert stop_reasons.terminal_status(stats['stop_reason']) == 'INTERRUPTED'


def test_a_closed_sheet_lets_the_post_be_engaged(no_store):
    loop = _Loop(sheet_closes=True)

    _run(loop)

    assert loop.engaged == ['demo_author']
