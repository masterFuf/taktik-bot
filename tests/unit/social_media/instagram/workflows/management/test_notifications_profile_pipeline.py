"""Le pipeline par-profil injecte au workflow Notifications.

L'obstacle qu'il leve : ``NotificationsEngagementWorkflow`` ne connait que son device
et ses selectors. Ces tests verrouillent le fait que ce qu'on lui injecte est bien
l'objet metier DE PRODUCTION — celui qui porte ``_process_profile_on_screen``, la seule
implementation du pipeline extract -> filtres -> IA -> follow -> DB — et non une
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
    """Meme classe, memes modules metier que target/hashtag : rien n'est reecrit ici."""
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=42)

    assert isinstance(pipeline.business, BaseBusinessAction)
    # Le pipeline unique + les deux services dont il depend.
    assert hasattr(pipeline.business, "_process_profile_on_screen")
    assert pipeline.business.profile_business is not None
    assert pipeline.business.filtering_business is not None


def test_the_follows_are_bound_to_the_given_account():
    """Sans compte explicite l'objet metier retombe sur l'id 1 : les follows partiraient
    sous un autre compte, dans la table meme que lisent les plafonds du jour."""
    assert build_notifications_profile_pipeline(MagicMock(), account_id=42).account_id == 42


def test_a_facade_is_never_wrapped_twice():
    """Le Lab passe deja un DeviceFacade chaud ; l'empiler fausserait tous les acces."""
    facade = DeviceFacade(MagicMock())

    pipeline = build_notifications_profile_pipeline(facade, account_id=1)

    assert pipeline.business.device is facade


def test_a_raw_device_is_wrapped_once():
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=1)

    assert isinstance(pipeline.business.device, BaseDeviceFacade)


def test_the_default_plan_follows_and_does_nothing_else():
    """Ce run cherche a ACQUERIR : un like ou une story sur un inconnu ne sert pas ce but
    et multiplierait les gestes surveilles."""
    config = DEFAULT_SUGGESTION_INTERACTION_CONFIG

    assert config["follow_percentage"] == 100
    assert config["like_percentage"] == 0
    assert config["comment_percentage"] == 0
    assert config["story_watch_percentage"] == 0
    # Criteres VIDES : la page Notifications n'expose aucun reglage de filtre, et
    # inventer des seuils rejetterait des suggestions en silence.
    assert config["filter_criteria"] == {}


def test_the_session_counter_exists_so_the_follow_cap_is_not_dead():
    """``_do_follow`` incremente le compteur de session ; sans session il reste mort."""
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=1)

    assert pipeline.business.session_manager is not None
    assert hasattr(pipeline.business.session_manager, "record_action")


def test_process_delegates_to_the_single_production_pipeline():
    """Un seul point de contact avec ``_process_profile_on_screen``, avec la provenance."""
    pipeline = build_notifications_profile_pipeline(MagicMock(), account_id=7)
    pipeline.business._process_profile_on_screen = MagicMock(return_value="done")

    assert pipeline.process("real_handle") == "done"
    _args, kwargs = pipeline.business._process_profile_on_screen.call_args
    assert kwargs["source_type"] == "NOTIFICATIONS"
    assert kwargs["source_name"] == "notifications_suggestions"
    assert kwargs["account_id"] == 7
