"""Instagram tasks — one-shots that run against no target list.

The family exists because the two-level model (action, then workflow) had no room for a
capability that is neither a single gesture nor a run: the story relay is five gestures with
a trigger, and forcing it into a workflow would have meant building a run engine for it or
grafting it onto a crawl it has nothing to do with.

A workflow is a task in a loop over targets. `account` and `publish` were already tasks
wearing workflow clothes; they can move here once this family has proved itself.
"""

from taktik.core.social_media.instagram.workflows.tasks.agent_handler import (
    INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID,
    INSTAGRAM_TASK_WORKFLOW_IDS,
    build_instagram_task_handler,
    register_instagram_task_handlers,
)
from taktik.core.social_media.instagram.workflows.tasks.story_relay import (
    DEFAULT_MAX_STORIES,
    relay_source_stories,
)

__all__ = [
    "DEFAULT_MAX_STORIES",
    "INSTAGRAM_TASK_STORY_RELAY_WORKFLOW_ID",
    "INSTAGRAM_TASK_WORKFLOW_IDS",
    "build_instagram_task_handler",
    "register_instagram_task_handlers",
    "relay_source_stories",
]
