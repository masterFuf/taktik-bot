"""Le chemin de production PAR PROFIL, rendu injectable au workflow Notifications.

``NotificationsEngagementWorkflow`` est volontairement maigre : il ne connait que son
device et ses selectors. Il n'a ni actions profil, ni acces DB, ni session. Or ouvrir
une suggestion demande exactement ce que font deja target et hashtag : extraire
(bio, photo, stats, langue), qualifier par l'IA, persister, puis interagir.

Ce module ne REIMPLEMENTE rien de tout cela. Il construit l'objet metier de
production — ``BaseBusinessAction`` avec ses modules metier — et expose les trois
gestes dont le workflow a besoin autour de lui :

    wait_for_profile()   le tap a-t-il VRAIMENT ouvert un profil ?
    read_username()      le @handle, que la surface des suggestions n'expose jamais
    process()            le pipeline unique extract -> filtres -> IA -> follow -> DB

``process`` appelle ``_process_profile_on_screen``, la seule et meme fonction que
``FollowerBusiness`` (target) et les likers utilisent. La qualification IA, elle,
n'est pas appelee ici : elle est installee par ``install_instagram_ai_hooks``, qui
patche ``InteractionEngineMixin._perform_interactions_on_profile`` — donc traverser
ce pipeline suffit a la declencher des lors que le lanceur a injecte un service IA.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from ....actions.core.base_business.profile_processing import ProfileProcessingResult

# Ce que ce run cherche : ACQUERIR. Le follow est donc certain et rien d'autre n'est
# tente — un like ou une story sur un compte inconnu ne servirait pas l'acquisition et
# multiplierait les gestes surveilles.
#
# `filter_criteria` reste VIDE volontairement : la page Notifications n'expose aucun
# reglage de filtre, et inventer des seuils ici rejetterait des suggestions en silence.
# Un lanceur qui a de vrais criteres (scheduler, Agent) les passe dans sa config.
DEFAULT_SUGGESTION_INTERACTION_CONFIG: Dict[str, Any] = {
    "follow_percentage": 100,
    "like_percentage": 0,
    "comment_percentage": 0,
    "story_watch_percentage": 0,
    "story_like_percentage": 0,
    "filter_criteria": {},
}

# Provenance ecrite en base pour chaque profil traite par ce chemin. `source_type` suit
# la nomenclature de `_process_profile_on_screen` (HASHTAG / FOLLOWER / FEED / ...).
SUGGESTIONS_SOURCE_TYPE = "NOTIFICATIONS"
SUGGESTIONS_SOURCE_NAME = "notifications_suggestions"


class NotificationsProfilePipeline:
    """Adaptateur mince entre le workflow Notifications et l'objet metier de production.

    Il ne contient AUCUNE decision : filtres, IA, interaction et ecritures DB vivent
    tous dans ``BaseBusinessAction``. Son unique role est de fixer la provenance
    (source_type / source_name / account_id) une fois pour toute la passe, pour que
    l'appelant n'ait pas a la repeter a chaque profil.
    """

    def __init__(
        self,
        business: Any,
        config: Dict[str, Any],
        *,
        source_type: str = SUGGESTIONS_SOURCE_TYPE,
        source_name: str = SUGGESTIONS_SOURCE_NAME,
    ):
        self.business = business
        self.config = config
        self.source_type = source_type
        self.source_name = source_name
        self.logger = logger.bind(module="instagram-notifications-pipeline")

    # ------------------------------------------------------------------
    # Preuves d'ecran / identite
    # ------------------------------------------------------------------
    def wait_for_profile(self, timeout: float = 8.0) -> bool:
        """A-t-on VRAIMENT atterri sur un profil ? (preuve de surface specifique)

        Delegue a ``wait_for_profile_screen``, qui exige les signatures propres a la
        surface profil (``profile_header_container`` / ``row_profile_header`` /
        ``profile_header_full_name``) et non un motif large comme un bouton "Suivre",
        present aussi dans le feed et sur un post. Poll, car la page se charge par le
        reseau : une verification immediate conclurait "pas un profil" sur une simple
        connexion lente.
        """
        try:
            return bool(self.business.detection_actions.wait_for_profile_screen(timeout=timeout))
        except Exception as exc:  # noqa: BLE001 — jamais fatal pour la passe
            self.logger.warning(f"Profile screen check failed: {exc}")
            return False

    def read_username(self) -> Optional[str]:
        """Le @handle du profil ouvert, ou None.

        C'est LA raison d'etre de la visite : la zone suggestions n'affiche qu'un
        libelle (souvent le nom complet), jamais le handle. Tant qu'on ne l'a pas lu,
        il n'existe aucune clef pour ecrire ou relire ce profil en base.
        """
        try:
            return self.business.detection_actions.get_username_from_profile()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"Username read failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Pipeline complet
    # ------------------------------------------------------------------
    def process(self, username: str) -> ProfileProcessingResult:
        """Extraction, filtres, qualification IA, interaction et persistance.

        Appel direct de ``_process_profile_on_screen`` : c'est l'unique implementation
        de ce pipeline dans le Bot, celle que target/hashtag/post-likers traversent.
        On l'appelle ici sur l'objet metier plutot que sur ``self`` (le workflow
        Notifications n'est pas un ``BaseBusinessAction``) — c'est le seul point de
        contact, et il ne doit pas etre double.
        """
        return self.business._process_profile_on_screen(
            username,
            self.config,
            source_type=self.source_type,
            source_name=self.source_name,
            account_id=self.business._get_account_id(),
            session_id=self.business._get_session_id(),
        )

    @property
    def account_id(self) -> Optional[int]:
        """Compte sous lequel les follows seront ecrits."""
        try:
            return self.business._get_account_id()
        except Exception:  # noqa: BLE001
            return None


def build_notifications_profile_pipeline(
    device: Any,
    *,
    config: Optional[Dict[str, Any]] = None,
    session_manager: Any = None,
    automation: Any = None,
    account_id: Optional[int] = None,
    session_id: Optional[int] = None,
    source_type: str = SUGGESTIONS_SOURCE_TYPE,
    source_name: str = SUGGESTIONS_SOURCE_NAME,
) -> NotificationsProfilePipeline:
    """Construire le pipeline de production sur un device deja connecte.

    ``device`` accepte aussi bien le device uiautomator2 brut (ce que passe le bridge)
    qu'un ``DeviceFacade`` deja construit (ce que passe le Lab sur sa session chaude) :
    on n'empile jamais deux facades l'une sur l'autre.

    Sans ``session_manager`` injecte, on en cree un : c'est lui qui porte l'humeur
    d'humanisation partagee et le compteur de follows de session que ``_do_follow``
    incremente. Sans lui, ce compteur — donc le plafond de session — resterait mort.

    ``session_id`` est l'id d'une session PERSISTEE ouverte par l'appelant. C'est lui
    qui rattache chaque follow a une session, donc aux chiffres montres au client :
    sans lui les interactions existent en base sans appartenir a rien.
    """
    from taktik.core.shared.device.facade import BaseDeviceFacade

    from ....actions.core.base_business import BaseBusinessAction
    from ....actions.core.device.facade import DeviceFacade
    from ..session import SessionManager

    config = dict(config or DEFAULT_SUGGESTION_INTERACTION_CONFIG)
    facade = device if isinstance(device, BaseDeviceFacade) else DeviceFacade(device)
    if session_manager is None:
        session_manager = SessionManager({"session_settings": config.get("session_settings", {})})
    if session_id:
        session_manager.session_id = session_id

    business = BaseBusinessAction(
        facade,
        session_manager=session_manager,
        automation=automation,
        module_name="notifications",
        init_business_modules=True,
    )
    if account_id:
        # Sans compte explicite, `BaseBusinessAction` retombe sur l'id 1 : les follows
        # seraient ecrits sous un autre compte que celui du telephone. L'appelant de
        # production DOIT donc resoudre le compte avant d'arriver ici.
        business.active_account_id = account_id

    return NotificationsProfilePipeline(
        business, config, source_type=source_type, source_name=source_name
    )


__all__ = [
    "DEFAULT_SUGGESTION_INTERACTION_CONFIG",
    "NotificationsProfilePipeline",
    "SUGGESTIONS_SOURCE_NAME",
    "SUGGESTIONS_SOURCE_TYPE",
    "build_notifications_profile_pipeline",
]
