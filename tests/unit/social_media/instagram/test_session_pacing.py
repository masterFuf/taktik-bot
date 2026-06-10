"""SessionManager pacing: explicit user delay wins (back-compat); else the profile drives it."""

from taktik.core.social_media.instagram.workflows.management.session.session import SessionManager


def test_explicit_user_delay_wins_backcompat():
    # Today's config sends an explicit delay → it must be honoured (no behaviour change).
    sm = SessionManager({'session_settings': {'delay_between_actions': {'min': 5, 'max': 15}}})
    for _ in range(50):
        assert 5 <= sm.get_delay_between_actions() <= 15


def test_no_explicit_delay_uses_balanced_default():
    # No explicit delay, no profile → default 'balanced' = historical 5-15s.
    sm = SessionManager({'session_settings': {}})
    assert sm.pacing.profile_id == 'balanced'
    for _ in range(50):
        assert 5 <= sm.get_delay_between_actions() <= 15


def test_profile_drives_delay_when_no_explicit():
    sm = SessionManager({
        'session_settings': {},
        'behaviorPolicy': {'profileId': 'careful'},
    })
    assert sm.pacing.profile_id == 'careful'
    for _ in range(50):
        assert 8 <= sm.get_delay_between_actions() <= 24


def test_explicit_delay_overrides_profile():
    # Even with a profile, an explicit delay still wins (until the UI drops it in Lot 4).
    sm = SessionManager({
        'session_settings': {'delay_between_actions': {'min': 2, 'max': 4}},
        'behaviorPolicy': {'profileId': 'careful'},
    })
    for _ in range(50):
        assert 2 <= sm.get_delay_between_actions() <= 4


def test_unknown_profile_falls_back_to_balanced():
    sm = SessionManager({'session_settings': {}, 'behaviorPolicy': {'profileId': 'nope'}})
    assert sm.pacing.profile_id == 'balanced'


def test_update_config_reresolves_pacing_profile():
    # update_config is called on every run_workflow; a changed profile must be picked up.
    sm = SessionManager({'session_settings': {}, 'behaviorPolicy': {'profileId': 'balanced'}})
    assert sm.pacing.profile_id == 'balanced'
    sm.update_config({'session_settings': {}, 'behaviorPolicy': {'profileId': 'careful'}})
    assert sm.pacing.profile_id == 'careful'
    for _ in range(30):
        assert 8 <= sm.get_delay_between_actions() <= 24
    # dropping the profile reverts to balanced
    sm.update_config({'session_settings': {}})
    assert sm.pacing.profile_id == 'balanced'
