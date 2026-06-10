"""LikeOrchestration._run_engagement_sequence — executes steps in order, aborts on like fail."""

from taktik.core.social_media.instagram.actions.business.actions.like.orchestration import (
    LikeOrchestration,
)


class _Host(LikeOrchestration):
    def __init__(self, like_ok=True, comment_ok=True, sigs=None):
        self.calls = []
        self._like_ok = like_ok
        self._comment_ok = comment_ok
        # Successive signatures returned by _current_post_signature (default: stable "same").
        self._sigs = list(sigs) if sigs is not None else None

        class _Log:
            def debug(self, *a, **k): pass
            def success(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass
        self.logger = _Log()

    def _current_post_signature(self):
        if self._sigs is None:
            return "same"               # stable → identity guard always passes
        return self._sigs.pop(0) if self._sigs else "same"

    # Stub the three sub-actions; record call order.
    def _read_post_description(self):
        self.calls.append('read')

    def like_current_post(self):
        self.calls.append('like')
        return self._like_ok

    def _comment_current_post(self, *_a, **_k):
        self.calls.append('comment')
        return self._comment_ok


def _run(sequence, like_ok=True, comment_ok=True, sigs=None):
    host = _Host(like_ok=like_ok, comment_ok=comment_ok, sigs=sigs)
    liked, commented = host._run_engagement_sequence(sequence, 'u', [], 'generic', {})
    return host.calls, liked, commented


def test_executes_steps_in_given_order():
    calls, liked, commented = _run(['read', 'like', 'comment'])
    assert calls == ['read', 'like', 'comment']
    assert liked is True and commented is True


def test_like_first_pattern():
    calls, liked, commented = _run(['like', 'read', 'comment'])
    assert calls == ['like', 'read', 'comment']


def test_comment_before_like_pattern_executes_both():
    # Pattern E: read → comment → like (comment lands before the like).
    calls, liked, commented = _run(['read', 'comment', 'like'])
    assert calls == ['read', 'comment', 'like']
    assert liked is True and commented is True


def test_like_failure_aborts_remaining_steps():
    calls, liked, commented = _run(['like', 'read', 'comment'], like_ok=False)
    assert calls == ['like']            # read + comment skipped
    assert liked is False and commented is False


def test_like_failure_after_comment_keeps_comment():
    # E with a failing like at the end: the comment already happened.
    calls, liked, commented = _run(['read', 'comment', 'like'], like_ok=False)
    assert calls == ['read', 'comment', 'like']
    assert liked is False and commented is True


def test_comment_failure_reported():
    calls, liked, commented = _run(['like', 'comment'], comment_ok=False)
    assert calls == ['like', 'comment']
    assert liked is True and commented is False


# ─── Frame-drift identity guard (the Lot 2 review fix) ───────────────────────

def test_drift_after_read_aborts_comment_pattern_E():
    # E: read → comment → like. Signature read BEFORE the read ('A'), then DIFFERENT
    # after the read ('B') = the frame drifted to another post → comment must NOT post.
    calls, liked, commented = _run(['read', 'comment', 'like'], sigs=['A', 'B'])
    assert calls == ['read']                 # comment + like skipped
    assert liked is False and commented is False


def test_no_drift_lets_pattern_E_proceed():
    # Same signature before/after the read → still on the intended post → comment + like.
    calls, liked, commented = _run(['read', 'comment', 'like'], sigs=['A', 'A'])
    assert calls == ['read', 'comment', 'like']
    assert liked is True and commented is True


def test_drift_after_read_aborts_like_pattern_B():
    # B: read → like → comment, frame drifts after read → like (and comment) skipped.
    calls, liked, commented = _run(['read', 'like', 'comment'], sigs=['A', 'B'])
    assert calls == ['read']
    assert liked is False and commented is False


def test_like_first_then_read_then_comment_guarded_once():
    # A: like → read → comment. like (no guard, we're on the post), read, then the
    # comment is guarded against the post-read frame; same sig → comment proceeds.
    calls, liked, commented = _run(['like', 'read', 'comment'], sigs=['X', 'X'])
    assert calls == ['like', 'read', 'comment']
    assert liked is True and commented is True
