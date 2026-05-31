"""YouTube account workflows."""

from taktik.core.social_media.youtube.workflows.account.account_workflow import (
    YouTubeAccountWorkflow,
)
from taktik.core.social_media.youtube.workflows.account.agent_handler import (
    YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID,
    YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID,
    YOUTUBE_ACCOUNT_WORKFLOW_IDS,
    register_youtube_account_handlers,
)

__all__ = [
    "YOUTUBE_ACCOUNT_LOGIN_WORKFLOW_ID",
    "YOUTUBE_ACCOUNT_LOGOUT_WORKFLOW_ID",
    "YOUTUBE_ACCOUNT_WORKFLOW_IDS",
    "YouTubeAccountWorkflow",
    "register_youtube_account_handlers",
]
