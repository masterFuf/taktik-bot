"""What a hashtag run does with each post — and the promise that old configs still run.

The three modes could not be combined because they were never three values of one setting:
`likers` opened ONE post and spent the run on its likers, `posts` walked many posts. Two
loops wearing one option. The plan makes the POST the unit and lets the three choices
combine, with a budget PER POST and PER POPULATION — "five likers and two commenters, on
each post" is the sentence a single shared number could not express.

The translation tests are the important half: a preset or a schedule saved last month must
behave exactly as it did, or this is a rewrite dressed up as a refactor.
"""

import pytest

from taktik.core.social_media.instagram.actions.business.workflows.hashtag.interaction_plan import (
    resolve_interaction_plan,
)


# ─────────────────────────────────────────────── legacy configs must not move

def test_likers_still_means_one_post_and_its_people():
    plan = resolve_interaction_plan({'interaction_mode': 'likers', 'max_interactions': 30})
    assert (plan.walk_likers, plan.walk_commenters, plan.engage_posts) == (True, False, False)
    assert plan.max_posts == 1
    assert plan.max_likers_per_post == 30       # what `max_interactions` meant there


def test_commenters_still_means_one_post_and_its_people():
    plan = resolve_interaction_plan({'interaction_mode': 'commenters', 'max_interactions': 12})
    assert (plan.walk_commenters, plan.engage_posts) == (True, False)
    assert plan.max_posts == 1
    assert plan.max_commenters_per_post == 12


def test_posts_still_means_many_posts_and_nobody():
    """`max_interactions` counted POSTS in this mode — the very ambiguity being removed."""
    plan = resolve_interaction_plan({'interaction_mode': 'posts', 'max_interactions': 30})
    assert plan.engage_posts is True
    assert plan.max_posts == 30
    assert plan.visits_profiles is False


def test_an_empty_config_is_the_historical_default():
    plan = resolve_interaction_plan({})
    assert plan.walk_likers is True
    assert plan.max_posts == 1


def test_an_unknown_mode_falls_back_to_likers():
    plan = resolve_interaction_plan({'interaction_mode': 'nonsense'})
    assert plan.walk_likers is True
    assert plan.legacy_mode == 'likers'


# ───────────────────────────────────────────────────────── the new model

def test_the_three_can_finally_be_mixed():
    plan = resolve_interaction_plan({
        'engage_posts': True, 'walk_likers': True, 'walk_commenters': True,
        'max_posts': 10, 'max_likers_per_post': 5, 'max_commenters_per_post': 2,
    })
    assert plan.engage_posts and plan.walk_likers and plan.walk_commenters
    assert (plan.max_posts, plan.max_likers_per_post, plan.max_commenters_per_post) == (10, 5, 2)


def test_the_two_populations_keep_separate_budgets():
    """"Five of this post and two commenters" — one shared number could not say it."""
    plan = resolve_interaction_plan({
        'walk_likers': True, 'walk_commenters': True,
        'max_likers_per_post': 5, 'max_commenters_per_post': 2,
    })
    assert plan.max_likers_per_post != plan.max_commenters_per_post


def test_engaging_posts_alone_visits_nobody():
    """The most discreet run we have, and a warm-up alternative to the feed workflow: posts
    are engaged where they stand, no profile is ever opened."""
    plan = resolve_interaction_plan({'engage_posts': True, 'max_posts': 15})
    assert plan.visits_profiles is False
    assert plan.max_posts == 15


def test_an_explicit_plan_wins_over_a_leftover_legacy_mode():
    """A saved config can carry both while the UI migrates; the stated intent decides."""
    plan = resolve_interaction_plan({'interaction_mode': 'likers', 'engage_posts': True})
    assert plan.engage_posts is True
    assert plan.walk_likers is False
    assert plan.legacy_mode is None


def test_a_plan_that_does_nothing_says_so():
    """Better a caller that can check than a run that walks posts and touches none of them."""
    assert resolve_interaction_plan({'engage_posts': False}).is_noop is True


@pytest.mark.parametrize("value", [0, -3, None, 'x'])
def test_a_meaningless_budget_falls_back_instead_of_disabling_the_run(value):
    plan = resolve_interaction_plan({'walk_likers': True, 'max_likers_per_post': value})
    assert plan.max_likers_per_post > 0


def test_the_plan_can_be_recorded_on_the_session():
    """The history has to be able to say WHICH modes were active, which today is buried in
    an opaque config blob."""
    plan = resolve_interaction_plan({'engage_posts': True, 'walk_likers': True, 'max_posts': 4})
    record = plan.as_record()
    assert record['engage_posts'] is True and record['walk_likers'] is True
    assert record['max_posts'] == 4
    assert 'posts' in plan.describe() and 'likers' in plan.describe()


# ────────────────────────────────────────── the per-post engagement building block

from taktik.core.social_media.instagram.actions.business.workflows.hashtag.workflow import (
    HashtagBusiness,
)


class _Host(HashtagBusiness):
    """The real `_engage_one_post` / `_walk_post_people`, with only the screen stubbed."""

    def __init__(self, likers_ok=True, commenters_ok=True):
        self.opened, self.closed, self.walked = [], [], []
        self._likers_ok, self._commenters_ok = likers_ok, commenters_ok
        self.liked = False

        class _Log:
            def debug(self, *a, **k): pass
            def info(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass

        self.logger = _Log()

    # --- surfaces
    def _open_likers_popup(self, is_reel=False):
        self.opened.append('likers')
        return self._likers_ok

    def _open_comments_view(self):
        self.opened.append('commenters')
        return self._commenters_ok

    def _close_likers_popup(self):
        self.closed.append('likers')

    def _close_comments_view(self):
        self.closed.append('commenters')

    def _interact_with_likers_list(self, *, stats, effective_config, max_interactions,
                                   source_type, source_name, list_source=None):
        self.walked.append((source_name, max_interactions))
        stats['users_interacted'] = stats.get('users_interacted', 0) + 1

    def _engage_post_itself(self, config, stats, author):
        self.liked = True
        return True

    def engage(self, plan, stats=None):
        stats = stats if stats is not None else {'users_interacted': 0, 'errors': 0}
        ok = self._engage_one_post(
            'esthetique', plan, {'like_percentage': 100}, stats, False, 'someone',
        )
        return ok, stats


@pytest.fixture(autouse=True)
def _stub_list_source(monkeypatch):
    """`resolve_list_source` reaches into real selectors; which population the rows come
    from is covered by its own tests. Here we measure the open/walk/close choreography."""
    from taktik.core.social_media.instagram.actions.business.workflows.hashtag import workflow
    monkeypatch.setattr(workflow, 'resolve_list_source', lambda wf, mode: mode)


def _plan(**kw):
    base = {'engage_posts': False, 'walk_likers': False, 'walk_commenters': False}
    base.update(kw)
    return resolve_interaction_plan(base)


def test_only_the_enabled_populations_are_opened():
    host = _Host()
    host.engage(_plan(walk_likers=True, max_likers_per_post=5))
    assert host.opened == ['likers']


def test_the_three_run_together_on_the_same_post():
    host = _Host()
    ok, _ = host.engage(_plan(engage_posts=True, walk_likers=True, walk_commenters=True))
    assert ok is True
    assert host.liked is True
    assert host.opened == ['likers', 'commenters']


def test_each_population_gets_its_own_budget():
    host = _Host()
    host.engage(_plan(walk_likers=True, walk_commenters=True,
                      max_likers_per_post=5, max_commenters_per_post=2))
    assert [budget for _name, budget in host.walked] == [5, 2]


@pytest.mark.parametrize("mode,other", [('walk_likers', 'likers'), ('walk_commenters', 'commenters')])
def test_what_was_opened_is_always_closed(mode, other):
    """The next population — and the next advance — both assume we are back on the post."""
    host = _Host()
    host.engage(_plan(**{mode: True}))
    assert host.closed == [other]


def test_a_population_that_will_not_open_is_closed_anyway_and_does_not_stop_the_others():
    host = _Host(likers_ok=False)
    ok, stats = host.engage(_plan(walk_likers=True, walk_commenters=True))
    assert host.opened == ['likers', 'commenters']   # the failure did not abort the rest
    assert ok is True                                 # the commenters walk still counted


def test_engaging_posts_alone_never_opens_a_people_list():
    host = _Host()
    ok, _ = host.engage(_plan(engage_posts=True))
    assert ok is True
    assert host.opened == []
