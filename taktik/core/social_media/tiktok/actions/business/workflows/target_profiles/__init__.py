"""TikTok target-profiles workflow: interact with each profile of a chosen list."""

from .workflow import TargetProfilesConfig, TargetProfilesWorkflow
from .agent_handler import (
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
