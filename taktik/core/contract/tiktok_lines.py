"""Lines every TikTok bridge may print besides its workflow's own.

`bot_profile` is the acting account, read on the phone by the session start
(`workflows/common/startup.py`) that every TikTok bridge runs. `ai_profile_done` is the AI
provider's verdict on a profile (`IPC.ai_profile_analyzed`, from `ai/providers/openrouter.py`),
printed when a run classifies profiles, and its copy for the base (`send_profile_classification`);
it is declared in `shared`, with the other AI lines. `ai_relevance` is the engagement verdict the
same qualification draws (`send_relevance`), printed by the runs that qualify the profiles they
visit and by the welcome pass.
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

#: `send_relevance` (`bridges/tiktok/common/ipc_video_events.py`), fed by `qualify_tiktok_profile`.
AI_RELEVANCE_EVENT = Event(
    "ai_relevance",
    doc="The AI's engagement verdict on a profile: worth it or not, and what to do.",
    fields=(
        Field("username", "string", "The profile, without @."),
        Field("relevant", "bool", "Relevant to the account."),
        Field("score", "number", "Relevance score, as the model gave it.", nullable=True),
        Field("reason", "string", "Why, in the app's language.", nullable=True),
        Field("follow", "bool", "Worth a follow."),
        Field("comment", "bool", "Worth a comment."),
        Field("like", "bool", "Worth a like."),
    ),
)

__all__ = ["AI_PROFILE_DONE_EVENT", "AI_RELEVANCE_EVENT", "BOT_PROFILE", "BOT_PROFILE_EVENT"]
