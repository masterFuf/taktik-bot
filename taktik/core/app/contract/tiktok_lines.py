"""Lines every TikTok bridge may print besides its workflow's own.

`bot_profile` is the acting account, read on the phone by the session start
(`workflows/runtime/startup.py`) that every TikTok bridge runs. `ai_profile_done` is the AI
provider's verdict on a profile (`IPC.ai_profile_analyzed`, from `app/ai/providers/openrouter.py`),
printed when a run classifies profiles.
"""

from __future__ import annotations

from .schema import Event, Field, Shape

BOT_PROFILE = Shape(
    name="TikTokBotProfile",
    doc="The acting account, read off its own profile at the start of the session.",
    fields=(
        Field("username", "string", "Its handle, without @."),
        Field("display_name", "string", "Its display name.", nullable=True),
        Field("followers_count", "int", "Its followers."),
        Field("following_count", "int", "The accounts it follows."),
        Field("likes_count", "int", "Its likes."),
        Field("bio", "string", "Its bio.", nullable=True),
        Field("profile_pic_base64", "string", "Its picture, a data URI.", nullable=True),
    ),
)

BOT_PROFILE_EVENT = Event(
    "bot_profile",
    doc="The acting account, once per session.",
    fields=(Field("profile", BOT_PROFILE, "The profile."),),
)

AI_PROFILE_DONE_EVENT = Event(
    "ai_profile_done",
    doc="The AI verdict on one profile.",
    fields=(
        Field("username", "string", "The profile's handle."),
        Field("target_username", "string", "The same."),
        Field("result", "string", "The verdict, for a person."),
        Field("duration_ms", "int", "How long the call took."),
        Field("model", "string", "The model that answered.", nullable=True),
        Field("provider", "string", "The provider.", nullable=True),
        Field("workflow_type", "string", "The family of the run."),
        Field("event_id", "string", "The card this verdict closes.", optional=True),
        Field("cost_usd", "number", "What the call cost.", optional=True),
        Field("classification", "json", "What the model returned (niche, category, scores, engagement...).",
              optional=True),
        Field("screenshot", "string", "The profile screenshot sent, a data URI.", optional=True, nullable=True),
        Field("persist_only", "bool", "A re-send only for the app to store the verdict.", optional=True),
    ),
)

__all__ = ["AI_PROFILE_DONE_EVENT", "BOT_PROFILE", "BOT_PROFILE_EVENT"]
