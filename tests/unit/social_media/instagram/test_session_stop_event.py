"""The `session_stop` event must gain the structured code without losing anything.

The desktop app reads this event to tell the operator why a run ended. Today it recovers the
meaning by matching the English sentence in `reason` with regular expressions; tomorrow it reads
`reason_code`. Both have to work at once, because the bot and the app are separate repositories
and nothing guarantees they move together.

So the event is additive, and these tests pin that down: a motive from the catalogue adds two
fields and leaves `reason` byte-for-byte as it was, and a terminal path not yet routed through
the catalogue still emits exactly the shape it emitted before.
"""

import json
import time

from taktik.core.social_media.instagram.workflows.management.session import stop_reasons as sr
from taktik.core.social_media.instagram.workflows.support.workflow_helpers import WorkflowHelpers


class _Automation:
    """The bare minimum finalize_session touches."""

    def __init__(self):
        self.stats = {'start_time': time.time()}
        self.session_finalized = False
        self.current_session_id = None


def _helpers() -> WorkflowHelpers:
    helpers = WorkflowHelpers(_Automation())
    helpers._close_instagram = lambda: None  # no device in a unit test
    return helpers


def _emitted_event(capsys) -> dict:
    """The JSON line finalize_session printed for the desktop app."""
    printed = [line for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    assert printed, "finalize_session printed no event"
    return json.loads(printed[-1])


def test_a_catalogue_motive_adds_the_code_and_keeps_the_sentence(capsys):
    _helpers().finalize_session(status='COMPLETED', reason=sr.follows_cap(5, 5))

    event = _emitted_event(capsys)

    assert event['reason'] == "Follows limit reached (5/5)"
    assert event['reason_code'] == "follows_cap"
    assert event['reason_params'] == {'count': 5, 'limit': 5}
    assert event['status'] == 'COMPLETED'


def test_a_plain_string_motive_still_emits_the_legacy_shape(capsys):
    # Not every terminal path is routed through the catalogue yet. Those still passing a plain
    # string must emit exactly what they emitted before -- no new fields, nothing renamed.
    _helpers().finalize_session(
        status='COMPLETED', reason='Sources exhausted (no further progress)'
    )

    event = _emitted_event(capsys)

    assert event['reason'] == 'Sources exhausted (no further progress)'
    assert 'reason_code' not in event
    assert 'reason_params' not in event


def test_the_event_stays_json_serialisable(capsys):
    # StopReason subclasses str, so json.dumps treats it as the sentence. If it ever stopped
    # being a str, finalize_session would raise instead of reporting the end of the run -- which
    # is why this is pinned here rather than left to chance.
    _helpers().finalize_session(status='INTERRUPTED', reason=sr.manual_stop())

    event = _emitted_event(capsys)

    assert event['reason'] == "Manual stop (Ctrl+C)"
    assert event['reason_code'] == "manual_stop"
    assert event['status'] == 'INTERRUPTED'
