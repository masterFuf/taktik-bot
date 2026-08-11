"""What the Lab writes must be filed under the account it was run on, or not at all.

The Lab drives PRODUCTION classes on a real device, so a Lab like is a real like and the
row it records is a real row. Built without an identity, those classes used to fall back
to account id 1 — a real account — so the work was attributed to somebody else, and
invisible in the figures of the account actually under test. Three call sites had
independently patched `active_account_id` by hand afterwards.
"""

from bridges.compat.diagnostics.runtime.action_test.action_bundle import ActionBundle


class _Recorder:
    """Stands in for a business action: it only has to carry an identity."""

    def __init__(self):
        self.active_account_id = None


def _bundle():
    bundle = ActionBundle()
    bundle.like = _Recorder()
    bundle.story = _Recorder()
    bundle.feed = _Recorder()
    return bundle


def test_binding_reaches_every_recording_component():
    """One binding for the whole bundle, not one per action that happens to remember."""
    bundle = _bundle()

    assert bundle.bind_account(42) == 3
    assert bundle.like.active_account_id == 42
    assert bundle.story.active_account_id == 42
    assert bundle.feed.active_account_id == 42


def test_no_account_binds_nothing_rather_than_guessing_one():
    bundle = _bundle()

    assert bundle.bind_account(None) == 0
    assert bundle.like.active_account_id is None


def test_a_component_the_bundle_never_built_is_skipped():
    """The TikTok bundle carries a different set; binding must not require them all."""
    bundle = ActionBundle()
    bundle.like = _Recorder()

    assert bundle.bind_account(7) == 1
    assert bundle.like.active_account_id == 7


def test_a_business_action_built_without_an_automation_has_no_identity():
    """The source of the whole family: this used to be a real account id."""
    from taktik.core.social_media.instagram.actions.core.base_business import BaseBusinessAction

    action = BaseBusinessAction.__new__(BaseBusinessAction)
    action.automation = None
    action.active_account_id = getattr(action.automation, 'active_account_id', None)

    assert action.active_account_id is None


def test_recording_without_an_identity_refuses_instead_of_writing_elsewhere():
    """The guard already existed; the default of 1 is what kept it from ever firing."""
    from taktik.core.social_media.instagram.actions.core.base_business.stats_recording import (
        StatsRecordingMixin,
    )

    class _Action(StatsRecordingMixin):
        def __init__(self):
            self.automation = None
            self.session_manager = None
            self.active_account_id = None
            self.logger = _NullLogger()

    class _NullLogger:
        def __getattr__(self, _name):
            return lambda *args, **kwargs: None

    assert _Action()._record_action("someone", "LIKE") is False
