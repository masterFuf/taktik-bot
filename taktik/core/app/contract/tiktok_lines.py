"""Lines every TikTok bridge may print besides its workflow's own.

`bot_profile` is the acting account, read on the phone by the session start
(`workflows/runtime/startup.py`) that every TikTok bridge runs. `ai_profile_done` is the AI
provider's verdict on a profile (`IPC.ai_profile_analyzed`, from `app/ai/providers/openrouter.py`),
printed when a run classifies profiles; it is declared in `shared`, with the other AI lines.
"""

from __future__ import annotations

from .schema import Event, Field, Shape
# The AI provider's verdict is the same line on every bridge: declared once, in `shared`.
from .shared import AI_PROFILE_DONE_EVENT

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

__all__ = ["AI_PROFILE_DONE_EVENT", "BOT_PROFILE", "BOT_PROFILE_EVENT"]
