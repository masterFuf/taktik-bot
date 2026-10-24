"""The session row must say what the run actually did.

`scrape_type` was only ever reassigned for `profile_posts`, so every other source fell through to
the default `'followers'`. A qualification pass — a list of known profiles visited and read again,
mining nobody's audience — was therefore stored as a follower scrape: 86 sessions in the base, all
indistinguishable from the real thing in the history and in any count grouped by type.
"""

from taktik.core.social_media.instagram.workflows.scraping.persistence import (
    ScrapingPersistenceMixin,
    saved_post_session_type,
)


class _FakeDb:
    def __init__(self):
        self.created = None

    def create_scraping_session(self, **kwargs):
        self.created = kwargs
        return 1


class _FakeLogger:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def debug(self, *_args, **_kwargs):
        pass


class _Ipc:
    def __init__(self):
        self.sent = []

    def send(self, msg_type, **kwargs):
        self.sent.append((msg_type, kwargs))


class _Workflow(ScrapingPersistenceMixin):
    def __init__(self, config):
        self.config = config
        self.logger = _FakeLogger()
        self.scraping_session_id = None
        self.db = _FakeDb()

    def _local_db(self):
        return self.db


def _create(config):
    workflow = _Workflow(config)
    workflow._create_scraping_session()
    return workflow.db.created


class TestSessionTypePerSource:
    def test_a_username_list_is_a_qualification(self):
        created = _create({'type': 'usernames', 'usernames': ['a', 'b'], 'source_name': 'Target Search cleanup'})
        assert created['scraping_type'] == 'qualification'
        assert created['source_type'] == 'USERNAME_LIST'
        assert created['source_name'] == 'Target Search cleanup (2)'

    def test_the_default_no_longer_leaks_into_it(self):
        # Even with scrape_type explicitly set to the old default, the source decides.
        created = _create({'type': 'usernames', 'usernames': ['a'], 'scrape_type': 'followers'})
        assert created['scraping_type'] == 'qualification'

    def test_a_target_run_keeps_its_scrape_type(self):
        created = _create({'type': 'target', 'target_usernames': ['someone'], 'scrape_type': 'following'})
        assert created['scraping_type'] == 'following'
        assert created['source_type'] == 'TARGET'

    def test_a_target_run_defaults_to_followers(self):
        created = _create({'type': 'target', 'target_usernames': ['someone']})
        assert created['scraping_type'] == 'followers'

    def test_profile_posts_still_names_itself(self):
        created = _create({'type': 'profile_posts', 'target_usernames': ['someone']})
        assert created['scraping_type'] == 'profile_posts'
        assert created['source_type'] == 'PROFILE_POSTS'

    def test_hashtag_and_post_url_keep_their_source(self):
        assert _create({'type': 'hashtag', 'hashtag': 'metz'})['source_type'] == 'HASHTAG'
        assert _create({'type': 'post_url', 'post_url': 'https://x'})['source_type'] == 'POST_URL'

    def test_a_hashtag_run_collects_likers_not_followers(self):
        # Session of 24/10 (#photographie, 5 likers of a post) stored as 'followers'.
        assert _create({'type': 'hashtag', 'hashtag': 'metz'})['scraping_type'] == 'likers'

    def test_a_post_url_run_says_which_lists_of_the_post_it_reads(self):
        base = {'type': 'post_url', 'post_url': 'https://x'}
        assert _create(base)['scraping_type'] == 'likers'
        assert _create({**base, 'scrape_likers': False, 'scrape_commenters': True})['scraping_type'] == 'commenters'
        assert _create({**base, 'scrape_commenters': True})['scraping_type'] == 'likers+commenters'

    def test_the_old_default_does_not_leak_into_a_post_source(self):
        created = _create({'type': 'hashtag', 'hashtag': 'metz', 'scrape_type': 'followers'})
        assert created['scraping_type'] == 'likers'


class TestTheRowIsAnnounced:
    """A killed bridge never closes its row: the desktop closes it by the id announced here."""

    def test_the_desktop_gets_the_id_of_the_row_just_created(self):
        workflow = _Workflow({'type': 'target', 'target_usernames': ['a']})
        workflow._ipc = _Ipc()
        workflow._create_scraping_session()
        assert workflow._ipc.sent == [("scraping_session", {"scraping_id": 1, "platform": "instagram"})]

    def test_nothing_is_announced_when_no_row_was_created(self):
        workflow = _Workflow({'type': 'target', 'target_usernames': ['a']})
        workflow.db.create_scraping_session = lambda **kwargs: None
        workflow._ipc = _Ipc()
        workflow._create_scraping_session()
        assert workflow._ipc.sent == []

    def test_without_a_desktop_the_run_carries_on(self):
        workflow = _Workflow({'type': 'target', 'target_usernames': ['a']})
        workflow._create_scraping_session()
        assert workflow.scraping_session_id == 1


class TestTheSavedConfigIsReadBack:
    """A session stored before its writer typed it is typed again from the config it saved, by the
    same rule; a config that does not say which lists the run read leaves it undecided."""

    def test_the_saved_settings_give_the_type_the_writer_gives(self):
        config = {'type': 'post_url', 'scrape_likers': True, 'scrape_commenters': True}
        assert saved_post_session_type('POST_URL', config) == ('likers+commenters', '')
        assert saved_post_session_type('POST_URL', config)[0] == _create(config)['scraping_type']

    def test_reading_neither_list_is_none_as_the_writer_says(self):
        config = {'type': 'hashtag', 'scrape_likers': False, 'scrape_commenters': False}
        assert saved_post_session_type('HASHTAG', config) == ('none', '')

    def test_an_absent_setting_is_not_filled_with_the_default(self):
        new_type, why = saved_post_session_type('HASHTAG', {'type': 'hashtag', 'scrape_likers': True})
        assert new_type is None
        assert 'scrape_commenters' in why

    def test_the_config_of_another_run_decides_nothing(self):
        config = {'type': 'hashtag', 'scrape_likers': True, 'scrape_commenters': False}
        assert saved_post_session_type('POST_URL', config)[0] is None
        assert saved_post_session_type('HASHTAG', {**config, 'type': 'target'})[0] is None

    def test_a_config_that_is_not_an_object_decides_nothing(self):
        assert saved_post_session_type('HASHTAG', ['likers'])[0] is None
