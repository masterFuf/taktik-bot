"""The per-profile production path, made injectable into the notifications workflow.

``NotificationsEngagementWorkflow`` knows only its device and its selectors: no
profile actions, no DB access, no session. Opening a suggestion needs exactly what
the target and hashtag runs already do — extract, qualify, persist, interact.

Nothing of that is reimplemented here. This module builds the production business
object and exposes the three gestures the workflow needs around it:

    wait_for_profile()   did the tap really open a profile?
    read_username()      the @handle, which the suggestions surface never exposes
    process()            the single extract -> filters -> AI -> follow -> DB pipeline

``process`` calls ``_process_profile_on_screen``, the same function the target run
uses. AI qualification is not called here: it is installed by
``install_instagram_ai_hooks``, so walking this pipeline is enough to trigger it once
a service has been injected.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from ....actions.core.base_business.profile_processing import ProfileProcessingResult

# This run is about ACQUISITION: the follow is certain and nothing else is attempted,
# since a like or a story on an unknown account would not serve acquisition.
#
# `filter_criteria` is deliberately EMPTY: this surface exposes no filter setting, and
# inventing thresholds here would reject suggestions silently. A caller with real
# criteria passes them in its own config.
DEFAULT_SUGGESTION_INTERACTION_CONFIG: Dict[str, Any] = {
    "follow_percentage": 100,
    "like_percentage": 0,
    "comment_percentage": 0,
    "story_watch_percentage": 0,
    "story_like_percentage": 0,
    "filter_criteria": {},
}

# Provenance written for every profile handled by this path. `source_type` follows the
# `_process_profile_on_screen` naming (HASHTAG / FOLLOWER / FEED / ...).
SUGGESTIONS_SOURCE_TYPE = "NOTIFICATIONS"
SUGGESTIONS_SOURCE_NAME = "notifications_suggestions"


class NotificationsProfilePipeline:
    """Thin adapter between the notifications workflow and the business object.

    It holds NO decision: filters, AI, interaction and DB writes all live in
    ``BaseBusinessAction``. Its only role is to fix the provenance once for the whole
    pass, so the caller does not repeat it per profile.
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
    # Screen proof / identity
    # ------------------------------------------------------------------
    def wait_for_profile(self, timeout: float = 8.0) -> bool:
        """Did the tap really land on a profile?

        Delegates to ``wait_for_profile_screen``, which requires the signatures
        specific to the profile surface rather than a broad pattern such as a follow
        button, which also exists in the feed and on a post. It polls, because the
        page loads over the network: an immediate check would conclude "not a profile"
        on a slow connection.
        """
        try:
            return bool(self.business.detection_actions.wait_for_profile_screen(timeout=timeout))
        except Exception as exc:  # noqa: BLE001 — never fatal for the pass
            self.logger.warning(f"Profile screen check failed: {exc}")
            return False

    def read_username(self) -> Optional[str]:
        """The @handle of the opened profile, or None.

        This is what the visit exists for: the suggestions zone shows only a display
        label, never the handle. Until it is read, there is no key to write or read
        this profile in the database.
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

        Calls ``_process_profile_on_screen`` directly: it is the single implementation
        of this pipeline, the one the target, hashtag and post-likers runs all walk. It
        is called on the business object rather than on ``self``, since this workflow is
        not a ``BaseBusinessAction`` — that is the only contact point, and it must not be
        duplicated.
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
        """Account the follows will be written under."""
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
    """Build the production pipeline on an already-connected device.

    ``device`` accepts both the raw uiautomator2 device and an existing
    ``DeviceFacade``, so two facades are never stacked on one another.

    Without an injected ``session_manager`` one is created: it carries the shared
    humanization mood and the session follow counter that ``_do_follow`` increments.
    Without it that counter, and therefore the session cap, would stay dead.

    ``session_id`` is the id of a persisted session opened by the caller. It is what
    attaches each follow to a session; without it the interactions exist in the
    database without belonging to anything.
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
        # Without an explicit account, `BaseBusinessAction` falls back to id 1 and the
        # follows would be written under an account other than the phone's. The caller
        # MUST resolve the account before reaching this point.
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
