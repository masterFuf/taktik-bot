"""A hashtag post of the account the run acts as is passed: no like, no comment.

Found by reading the code: a post of the operated account met on a hashtag was liked under its
own name. Its likers walk already passed that account; the post itself is now passed by the same
comparison (`ActionUtils.same_username` against `automation.active_username`), before any gesture,
counted with the posts a filter left out (`already_filtered`) and said as skipped with the reason
the likers loop already gives that account, `own_account`.
"""

import types

from unit.social_media.instagram.workflows.automation.hashtag.test_hashtag_posts_mode import (
    _Host,
    _no_persistence,  # noqa: F401 - the autouse fixture of the harness
    _post,
    _run,
)


def test_the_accounts_own_post_is_not_engaged(_no_persistence, monkeypatch):
    import taktik.core.social_media.instagram.workflows.automation.hashtag.workflow as mod
    skipped = []
    monkeypatch.setattr(mod.IPCEmitter, 'emit_post_skipped',
                        staticmethod(lambda **k: skipped.append((k['author'], k['reason']))))
    host = _Host([_post('a'), _post('Demo_Account'), _post('c')])
    host.automation = types.SimpleNamespace(active_username='demo_account')

    stats = _run(host, _no_persistence)

    assert host.recorder.likes == ['a', 'c']
    assert host.recorded == ['a', 'c']
    assert stats['already_filtered'] == 1
    assert skipped == [('Demo_Account', 'own_account')]


def test_a_run_that_does_not_know_its_account_engages_every_post(_no_persistence):
    host = _Host([_post('a'), _post('b'), _post('c')])
    host.automation = types.SimpleNamespace(active_username=None)

    _run(host, _no_persistence)

    assert host.recorder.likes == ['a', 'b', 'c']
