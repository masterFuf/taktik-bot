"""TikTok target-profiles workflow: interact with each profile of a chosen list."""

from taktik.core.social_media.tiktok.workflows.automation.target_profiles.workflow import (
    TargetProfilesConfig,
    TargetProfilesWorkflow,
)
from taktik.core.social_media.tiktok.workflows.automation.target_profiles.agent_handler import (
    TIKTOK_TARGET_PROFILES_WORKFLOW_ID,
    build_tiktok_target_profiles_handler,
    register_tiktok_target_profiles_handlers,
    run_tiktok_target_profiles,
)

__all__ = [
    "TIKTOK_TARGET_PROFILES_WORKFLOW_ID",
    "TargetProfilesConfig",
    "TargetProfilesWorkflow",
    "build_tiktok_target_profiles_handler",
    "register_tiktok_target_profiles_handlers",
    "run_tiktok_target_profiles",
]
