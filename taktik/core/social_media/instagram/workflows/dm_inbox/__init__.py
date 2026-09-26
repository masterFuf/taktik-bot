"""The Instagram DM inbox: read it, read its requests folder, reply in a conversation.

One runtime (`runtime.DMRuntime`) and one launcher (`agent_handler.run_instagram_dm`) for the
desktop bridge, the CLI and the Cartography Lab.
"""

from taktik.core.social_media.instagram.workflows.dm_inbox.agent_handler import (
    INSTAGRAM_DM_READ_WORKFLOW_ID,
    INSTAGRAM_DM_SEND_WORKFLOW_ID,
    register_instagram_dm_handlers,
    run_instagram_dm,
)
from taktik.core.social_media.instagram.workflows.dm_inbox.runtime import DMRuntime

__all__ = [
    "DMRuntime",
    "INSTAGRAM_DM_READ_WORKFLOW_ID",
    "INSTAGRAM_DM_SEND_WORKFLOW_ID",
    "register_instagram_dm_handlers",
    "run_instagram_dm",
]
