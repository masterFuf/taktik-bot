"""Every workflow must record its own name in the session history.

Four of them did not. `create_workflow_session` recognised `interact_with_followers`,
`hashtag` and `post_url`, and anything else fell through to the default — `USER` /
"unknown". Feed, unfollow and the two syncs were therefore written as target runs: the
session existed, the row existed, the history simply called it something else. Which is why
no Feed line ever showed up in the sessions page, and why it looked like feed runs were not
recorded at all.

The mapping is now a table with an entry for the workflows that have no target of their own,
and an unmapped type warns instead of quietly borrowing the default's identity.
"""

import inspect

import pytest

from taktik.core.social_media.instagram.workflows.support import workflow_helpers

SOURCE = inspect.getsource(workflow_helpers.WorkflowHelpers.create_workflow_session)


@pytest.mark.parametrize("action_type,expected", [
    ('interact_with_followers', 'USER'),
    ('hashtag', 'HASHTAG'),
    ('post_url', 'POST_URL'),
    ('feed', 'FEED'),
    ('unfollow', 'UNFOLLOW'),
    ('sync_following', 'SYNC_FOLLOWING'),
    ('sync_followers_following', 'SYNC_FOLLOWING'),
])
def test_every_action_type_has_its_own_label(action_type, expected):
    assert f"'{action_type}': (\"{expected}\"" in SOURCE


def test_the_workflows_without_a_target_are_declared_as_such():
    """feed / unfollow / sync work on our own feed or our own following list. Declaring
    `None` for the target key is what stops them inheriting "unknown" from a lookup that was
    never going to find anything."""
    for action_type in ('feed', 'unfollow', 'sync_following'):
        entry = SOURCE.split(f"'{action_type}': (")[1].split(')')[0]
        assert 'None' in entry, entry


def test_an_unmapped_action_type_says_so():
    """The old chain of elifs was silent: a new workflow was recorded as USER and nobody
    learned about it until a page looked wrong months later."""
    assert 'Unmapped action type' in SOURCE
    assert '_ACTION_TARGETS' in SOURCE


def test_both_paths_read_the_same_table():
    """The override path and the config path each had their own copy of the elif chain, so a
    type added to one stayed missing from the other."""
    assert SOURCE.count('_ACTION_TARGETS.get(') == 2
