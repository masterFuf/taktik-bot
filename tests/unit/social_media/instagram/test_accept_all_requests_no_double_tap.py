"""accept_all_requests must never re-tap a username already confirmed in the same batch.

Device case: a just-accepted row can still render for a moment (Instagram hasn't removed it from
the list yet), so the next dump can show the SAME username again with an "accept" affordance —
tapping it again either wastes a tap on a stale row, or worse, hits whatever DIFFERENT element now
occupies that screen slot (e.g. a post-accept "Message"/"Follow back" CTA matched by the same
selector). Observed on device: "amourlestyliste" logged as accepted 4 times, two of the taps only
~10px apart (the same row read twice).
"""

from taktik.core.social_media.instagram.workflows.notifications.notifications_workflow import (
    NotificationsEngagementWorkflow,
)


def _wf(row_sequences):
    """A workflow whose _wait_for_request_rows yields each given rows-list in order (last one
    repeats once exhausted, simulating "no more requests")."""
    wf = object.__new__(NotificationsEngagementWorkflow)
    wf.ensure_follow_requests_screen = lambda: True
    wf.logger = type('L', (), {'success': lambda *a, **k: None, 'warning': lambda *a, **k: None,
                                'debug': lambda *a, **k: None, 'info': lambda *a, **k: None})()
    wf._notify = lambda *a, **k: None
    wf.tapped = []
    seq = iter(row_sequences)
    last = [row_sequences[-1]] if row_sequences else [[]]

    def _wait_rows():
        return next(seq, last[0])

    wf._wait_for_request_rows = _wait_rows

    def _tap(point, name):
        wf.tapped.append(name)
        return True

    wf._tap_point = _tap
    return wf


def test_stale_lingering_row_resolves_to_a_new_one_within_the_repoll(monkeypatch):
    import taktik.core.social_media.instagram.workflows.notifications.notifications_workflow as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)
    # First read after tapping alice still shows only her (lingering); the bounded re-poll then
    # reveals bob, a genuinely new request.
    rows_over_time = [
        [{"username": "alice", "accept": (1, 1)}],
        [{"username": "alice", "accept": (1, 1)}],   # still there — must NOT be re-tapped
        [{"username": "bob", "accept": (2, 2)}],       # a genuinely new request, found on re-poll
        [],                                              # nothing left
    ]
    wf = _wf(rows_over_time)
    result = wf.accept_all_requests(max_requests=10, delay_range=(0, 0))
    assert result["accepted"] == ["alice", "bob"]
    assert result["count"] == 2
    assert wf.tapped == ["accept alice", "accept bob"]


def test_all_lingering_stops_the_batch(monkeypatch):
    import taktik.core.social_media.instagram.workflows.notifications.notifications_workflow as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)
    # The already-accepted row keeps appearing on every re-poll -> no progress possible, stops cleanly.
    rows_over_time = [[{"username": "alice", "accept": (1, 1)}]] * 6
    wf = _wf(rows_over_time)
    result = wf.accept_all_requests(max_requests=10, delay_range=(0, 0))
    assert result["accepted"] == ["alice"]
    assert wf.tapped == ["accept alice"]  # never tapped a second time


def test_case_insensitive_dedup(monkeypatch):
    import taktik.core.social_media.instagram.workflows.notifications.notifications_workflow as mod
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)
    rows_over_time = [
        [{"username": "Alice", "accept": (1, 1)}],
        [{"username": "alice", "accept": (1, 1)}],  # same person, different case -> skip
        [],
    ]
    wf = _wf(rows_over_time)
    result = wf.accept_all_requests(max_requests=10, delay_range=(0, 0))
    assert result["accepted"] == ["Alice"]
