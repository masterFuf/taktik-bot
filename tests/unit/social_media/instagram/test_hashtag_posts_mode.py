"""Hashtag `interaction_mode='posts'` — engage the POSTS, never a list of people.

The historical mode opens ONE post and spends the whole run on the people who liked it.
This one keeps walking the hashtag: pick a post by the same criteria, like/comment it where
it stands, move on. Same discovery machinery, different thing engaged.

The first test is the one that matters most: the default must still be the likers path,
byte for byte. Everything else here is new surface; that one is the promise that nothing
already in production changed.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
    HashtagBusiness,
)


class _Recorder:
    def __init__(self):
        self.likes = []
        self.comments = []


class _Host(HashtagBusiness):
    """HashtagBusiness with the screen and the production atomics stubbed."""

    def __init__(self, posts, *, already_processed=(), like_ok=True):
        self._posts = list(posts)          # successive posts the "screen" shows
        self._index = 0
        self._already = set(already_processed)
        self._like_ok = like_ok
        self.recorder = _Recorder()
        self.recorded = []                 # posts written to the dedup store
        self.advances = 0
        self.likers_popup_opened = False
        self.session_manager = None
        self.automation = None

        class _Log:
            def debug(self, *a, **k): pass
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        self.logger = _Log()

        host = self

        class _Like:
            def like_current_post(self):
                host.recorder.likes.append(host._current()['author'])
                return host._like_ok

        class _Comment:
            def comment_on_post(self, **kwargs):
                host.recorder.comments.append(kwargs.get('username'))
                return {'commented': True}

        class _Stats:
            def increment(self, *a, **k): pass
            def display_final_stats(self, **k): pass

        class _Scroll:
            def human_reading_pause(self, **k): pass

        self.like_business = _Like()
        self.comment_business = _Comment()
        self.stats_manager = _Stats()
        self.scroll_actions = _Scroll()

    # --- the "screen" ---------------------------------------------------
    def _current(self):
        return self._posts[self._index] if self._index < len(self._posts) else {}

    def _find_first_valid_post(self, hashtag, config, skip_count=0):
        return dict(self._current()) or None

    def _is_reel_post(self):
        return bool(self._current().get('is_reel'))

    def _extract_current_post_metadata(self, is_reel=False):
        post = self._current()
        return {'author': post.get('author'), 'likes_count': post.get('likes_count'),
                'comments_count': post.get('comments_count'), 'caption_hash': post.get('author')}

    def _signature_of(self, metadata):
        return str((metadata or {}).get('likes_count'))

    def _swipe_to_next_post(self, known_signature=None):
        self.advances += 1
        self._index += 1
        return self._index < len(self._posts)

    def _human_like_delay(self, *a, **k):
        pass

    def _open_likers_popup(self, is_reel=False):
        self.likers_popup_opened = True
        return False

    @property
    def ui_extractors(self):
        host = self

        class _Ext:
            def extract_likes_count_from_ui(self, is_reel=None):
                return host._current().get('likes_count')

            def extract_comments_count_from_ui(self, is_reel=None):
                return host._current().get('comments_count')

        return _Ext()


def _post(author, likes=500, comments=3, is_reel=False):
    return {'author': author, 'likes_count': likes, 'comments_count': comments, 'is_reel': is_reel}


def _config(**overrides):
    base = {'min_likes': 100, 'max_likes': 50000, 'max_interactions': 3,
            'max_posts_to_analyze': 20, 'like_percentage': 100, 'comment_percentage': 0,
            'interaction_mode': 'posts'}
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _no_persistence(monkeypatch):
    """Stub the dedup store: `is_processed` answers from the host, `record_processed` logs."""
    import taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow as mod

    class _Service:
        host = None

        @staticmethod
        def is_processed(*, hashtag, post_author, post_caption_hash, account_id, hours_limit):
            return post_author in _Service.host._already

        @staticmethod
        def record_processed(**kwargs):
            _Service.host.recorded.append(kwargs['post_author'])

    monkeypatch.setattr(mod, 'InstagramHashtagPostService', _Service)
    monkeypatch.setattr(mod.IPCEmitter, 'emit_current_post', staticmethod(lambda **k: None))
    monkeypatch.setattr(mod.IPCEmitter, 'emit_post_skipped', staticmethod(lambda **k: None))
    return _Service


def _run(host, service, **config_overrides):
    service.host = host
    stats = {'posts_analyzed': 0, 'posts_selected': 0, 'likes_made': 0,
             'comments_made': 0, 'users_interacted': 0, 'errors': 0}
    return host._interact_with_hashtag_posts(
        'esthetique', _config(**config_overrides), stats, account_id=42, finalize=False,
    )


# ─────────────────────────────────────────────────────────────── no regression

def test_the_default_mode_is_still_the_likers_path():
    """The whole point of shipping this as a MODE: an unset `interaction_mode` must run
    exactly what production ran yesterday."""
    from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import (
        HASHTAG_DEFAULTS,
    )
    assert HASHTAG_DEFAULTS['interaction_mode'] == 'likers'


# ─────────────────────────────────────────────────────────────── posts mode

def test_it_engages_several_posts_and_never_opens_a_people_list(_no_persistence):
    host = _Host([_post('a'), _post('b'), _post('c')])
    stats = _run(host, _no_persistence)

    assert host.recorder.likes == ['a', 'b', 'c']
    assert stats['likes_made'] == 3
    assert stats['users_interacted'] == 3
    assert host.likers_popup_opened is False


def test_it_stops_at_the_post_budget(_no_persistence):
    host = _Host([_post('a'), _post('b'), _post('c'), _post('d')])
    stats = _run(host, _no_persistence, max_interactions=2)

    assert host.recorder.likes == ['a', 'b']
    assert stats['stop_reason'] == 'budget_reached'


def test_an_already_engaged_post_is_skipped_not_re_liked(_no_persistence):
    """Re-tapping a liked post UNLIKES it — the 7-day guard is what stands between the run
    and undoing its own work."""
    host = _Host([_post('a'), _post('b')], already_processed={'a'})
    _run(host, _no_persistence)

    assert host.recorder.likes == ['b']


def test_a_post_outside_the_like_bounds_is_skipped(_no_persistence):
    host = _Host([_post('small', likes=10), _post('ok', likes=500)])
    _run(host, _no_persistence, min_likes=100, max_likes=50000)

    assert host.recorder.likes == ['ok']


def test_an_engaged_post_is_recorded_so_the_next_run_skips_it(_no_persistence):
    host = _Host([_post('a')])
    _run(host, _no_persistence, max_interactions=1)

    assert host.recorded == ['a']


def test_a_post_that_could_not_be_liked_is_not_recorded_as_engaged(_no_persistence):
    """Recording a post we did not actually engage would burn it for 7 days for nothing."""
    host = _Host([_post('a')], like_ok=False)
    stats = _run(host, _no_persistence, max_interactions=1)

    assert host.recorded == []
    assert stats['likes_made'] == 0


def test_comments_go_through_the_production_action(_no_persistence):
    """`comment_on_post` is what the AI smart-comment hook wraps — a private path here would
    silently lose smart comments, telemetry and the daily caps."""
    host = _Host([_post('a')])
    stats = _run(host, _no_persistence, max_interactions=1, like_percentage=0,
                 comment_percentage=100)

    assert host.recorder.comments == ['a']
    assert stats['comments_made'] == 1


def test_running_out_of_posts_stops_cleanly(_no_persistence):
    host = _Host([_post('a')])
    stats = _run(host, _no_persistence, max_interactions=5)

    assert stats['stop_reason'] == 'no_new_post'
    assert stats['success'] is True


# ──────────────────────────────────────────────────────── the config chain

def test_the_mode_survives_the_whole_config_chain():
    """Page -> config builder -> runner -> workflow. Each hop is a WHITELIST, and a key
    missing from any one of them is dropped in silence: that is exactly how the post-like
    bounds were lost (the page sent them, the workflow never saw them)."""
    from taktik.core.social_media.instagram.workflows.core.config_builder import (
        build_instagram_automation_config,
    )
    import inspect
    from taktik.core.social_media.instagram.workflows.core import workflow_runner

    built = build_instagram_automation_config({
        'workflowType': 'hashtags', 'target': 'esthetique', 'interactionMode': 'posts',
    })
    action = built['actions'][0]
    assert action.get('interaction_mode') == 'posts'

    # The runner rebuilds its own config and copies keys one by one — the hop that
    # swallowed `post_criteria` before it was added explicitly.
    assert "config['interaction_mode'] = action['interaction_mode']" in inspect.getsource(
        workflow_runner
    )


def test_a_page_that_says_nothing_leaves_the_mode_unset():
    """Unset must stay unset all the way down, so the workflow applies its own default
    ('likers') rather than a value invented mid-chain."""
    from taktik.core.social_media.instagram.workflows.core.config_builder import (
        build_instagram_automation_config,
    )
    built = build_instagram_automation_config({'workflowType': 'hashtags', 'target': 'esthetique'})
    assert built['actions'][0].get('interaction_mode') is None


# ─────────────────────────────────────────────────────── commenters source

def test_the_three_modes_are_documented_in_the_defaults():
    """'commenters' walks the same post, but the people who WROTE something. It reuses the
    post_url list source as-is, so only the row plumbing differs — everything downstream of
    the click is the shared loop."""
    from taktik.core.social_media.instagram.actions.business.common.workflow_defaults import (
        HASHTAG_DEFAULTS,
    )
    import inspect
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag import workflow

    assert HASHTAG_DEFAULTS['interaction_mode'] == 'likers'
    source = inspect.getsource(workflow)
    assert "resolve_list_source(self, source_mode)" in source
    assert "if source_mode == 'commenters':" in source


def test_an_unknown_mode_falls_back_to_likers_instead_of_failing():
    """A typo in a saved preset must not abort a run, and must not silently pick the wrong
    population either — likers is the historical, safe answer."""
    import inspect
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag import workflow

    source = inspect.getsource(workflow)
    assert "if source_mode not in ('likers', 'commenters'):" in source
    assert "falling back to likers" in source
