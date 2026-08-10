"""The per-profile pipeline injected into the notifications workflow.

The obstacle it lifts: that workflow knows only its device and its selectors. These
tests lock the fact that what is injected really is the PRODUCTION business object —
the one carrying the single implementation of the extract, filter, qualify, follow
and write pipeline — and not a
reimplementation locale.
"""

from unittest.mock import MagicMock

from taktik.core.shared.device.facade import BaseDeviceFacade
from taktik.core.social_media.instagram.actions.core.base_business import BaseBusinessAction
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade
from taktik.core.social_media.instagram.workflows.management.notifications import (
    DEFAULT_SUGGESTION_INTERACTION_CONFIG,
    build_notifications_profile_pipeline,
)


def test_the_injected_object_is_the_production_business_action():
    """Same class and same business modules as the target run: nothing is rewritten."""
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=42)

    assert isinstance(pipeline.business, BaseBusinessAction)
    # The single pipeline plus the two services it depends on.
    assert hasattr(pipeline.business, "_process_profile_on_screen")
    assert pipeline.business.profile_business is not None
    assert pipeline.business.filtering_business is not None


def test_the_follows_are_bound_to_the_given_account():
    """Without an explicit account the business object falls back on the default id: the
    follows would go under another account, in the very table the daily caps read."""
    assert build_notifications_profile_pipeline(MagicMock(), account_id=42).account_id == 42


def test_a_facade_is_never_wrapped_twice():
    """A warm device facade may already be passed in; stacking another would break every access."""
    facade = DeviceFacade(MagicMock())

    pipeline = build_notifications_profile_pipeline(facade, account_id=1)

    assert pipeline.business.device is facade


def test_a_raw_device_is_wrapped_once():
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=1)

    assert isinstance(pipeline.business.device, BaseDeviceFacade)


def test_the_default_plan_follows_and_does_nothing_else():
    """This run is about ACQUISITION: a like or a story on an unknown account does not serve
    that goal and would multiply the watched gestures."""
    config = DEFAULT_SUGGESTION_INTERACTION_CONFIG

    assert config["follow_percentage"] == 100
    assert config["like_percentage"] == 0
    assert config["comment_percentage"] == 0
    assert config["story_watch_percentage"] == 0
    # EMPTY criteria: that surface exposes no filter setting, and inventing
    # thresholds would reject suggestions silently.
    assert config["filter_criteria"] == {}


def test_the_session_counter_exists_so_the_follow_cap_is_not_dead():
    """The follow action increments the session counter; without a session it stays dead."""
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=1)

    assert pipeline.business.session_manager is not None
    assert hasattr(pipeline.business.session_manager, "record_action")


def test_process_delegates_to_the_single_production_pipeline():
    """One single contact point with the shared pipeline, carrying the provenance."""
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=7)
    pipeline.business._process_profile_on_screen = MagicMock(return_value="done")

    assert pipeline.process("real_handle") == "done"
    _args, kwargs = pipeline.business._process_profile_on_screen.call_args
    assert kwargs["source_type"] == "NOTIFICATIONS"
    assert kwargs["source_name"] == "notifications_suggestions"
    assert kwargs["account_id"] == 7
