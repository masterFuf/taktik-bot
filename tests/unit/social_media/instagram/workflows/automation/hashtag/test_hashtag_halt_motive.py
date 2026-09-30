"""The hashtag run ends with the motive the shared latch carries, not always "action blocked".

Seen on a phone: the desktop app died in the middle of a hashtag run, the watchdog raised the
latch with DESKTOP_GONE, and the session was filed as `action_blocked`, an Instagram block that
never happened. The loop read the latch but wrote `action_blocked()` whatever its code.
"""

import pytest

from taktik.core.shared.diagnostics import run_halt

from test_hashtag_posts_mode import _Host, _no_persistence, _post, _run  # noqa: F401 (fixture)


@pytest.fixture(autouse=True)
def _clean_latch():
    run_halt.reinitialiser()
    yield
    run_halt.reinitialiser()


def _code(stats):
    return getattr(stats['stop_reason'], 'code', None)


def test_a_desktop_gone_before_the_first_post_is_filed_as_desktop_gone(_no_persistence):
    host = _Host([_post('a'), _post('b')])
    run_halt.demander_arret(run_halt.DESKTOP_GONE, "desktop pid exited")

    stats = _run(host, _no_persistence)

    assert _code(stats) == "desktop_gone"
    assert host.recorder.likes == []


def test_a_desktop_gone_after_a_like_ends_the_run_as_desktop_gone(_no_persistence, monkeypatch):
    host = _Host([_post('a'), _post('b'), _post('c')])
    like = host.like_business.like_current_post

    def like_then_desktop_dies(record_as=None):
        ok = like(record_as=record_as)
        run_halt.demander_arret(run_halt.DESKTOP_GONE, "desktop pid exited")
        return ok

    monkeypatch.setattr(host.like_business, "like_current_post", like_then_desktop_dies)
    stats = _run(host, _no_persistence)

    assert host.recorder.likes == ['a']
    assert _code(stats) == "desktop_gone"


def test_a_real_block_is_still_filed_as_action_blocked(_no_persistence):
    host = _Host([_post('a')])
    run_halt.demander_arret(run_halt.ACTION_BLOCKED, "try_again_later_page")

    stats = _run(host, _no_persistence)

    assert _code(stats) == "action_blocked"
