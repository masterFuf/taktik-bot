"""Publications with a bridge of their own: the YouTube upload and the TikTok post.

The Instagram publication (`publish_bridge`) has no manifest id nor launcher yet and is not
declared.
"""

from __future__ import annotations

from .schema import HOST, Event, Field, ListOf, OneOf, Refusal, WorkflowContract
from .shared import ERROR_EVENT, LOG_EVENT, STATUS_EVENT, device_field

_YOUTUBE = "taktik.core.social_media.youtube.workflows.publish"
_TIKTOK = "taktik.core.social_media.tiktok.workflows.publish"

# ------------------------------------------------------------------------------------ YouTube

YOUTUBE_UPLOAD = WorkflowContract(
    workflow_id="youtube.publish.upload_post",
    name="YouTubeUpload",
    bridge="youtube_upload_bridge",
    doc="Publish one video on YouTube, as a Short or a standard video.",
    launcher=f"{_YOUTUBE}.agent_handler:run_youtube_upload",
    reader=f"{_YOUTUBE}.payload:youtube_upload_request_from_payload",
    settings=(
        Field("localPath", "string", "The video file on this computer.", required=True,
              aliases=("local_path",), attr="local_path"),
        Field("title", "string", "Its title; a Short's is cut at 100 characters.", default="", attr="title"),
        Field("description", "string", "Its description.", default="", attr="description"),
        Field("uploadType", OneOf(("short", "video")), "A Short or a standard video.", default="short",
              aliases=("upload_type",), attr="upload_type"),
        Field("visibility", OneOf(("public", "unlisted", "private")), "Who can see it.", default="public",
              attr="visibility"),
    ),
    bridge_fields=(device_field("deviceId"),),
    refusals=(Refusal("localPath", doc="No file to upload."),),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        LOG_EVENT,
        Event("upload_result", doc="The upload is over.", fields=(
            Field("success", "bool", "The video was published."),
            Field("workflow", OneOf(("upload_post",)), "The workflow."),
            Field("upload_type", "string", "A Short or a standard video."),
            Field("message", "string", "What happened, for a person."),
            Field("error_type", "string", "Why it failed.", nullable=True),
        )),
    ),
)

# ------------------------------------------------------------------------------------- TikTok

TIKTOK_UPLOAD = WorkflowContract(
    workflow_id="tiktok.standalone.upload_post",
    name="TikTokUpload",
    bridge="tiktok_publish_bridge",
    doc="Publish on TikTok: a video from the gallery, or a text post.",
    launcher=f"{_TIKTOK}.agent_handler:run_tiktok_publish",
    reader=f"{_TIKTOK}.payload:publish_request_from_payload",
    settings=(
        Field("postType", OneOf(("video", "text")), "A video, or a text post; any other value is a video.",
              default="video", aliases=("post_type",), attr="post_type"),
        Field("localPath", "string", "The video or image file on this computer (video).", default="",
              aliases=("local_path",), attr="local_path"),
        Field("caption", "string", "The caption (video).", default="", attr="caption"),
        Field("hashtags", ListOf("string"), "Hashtags, without # (video); TikTok takes 5.", default=(),
              attr="hashtags"),
        Field("text", "string", "The text of a text post.", default="", attr="text"),
        Field("toStory", "bool", "Publish the text post to the story instead of the feed.", default=False,
              aliases=("to_story",), attr="to_story"),
        Field("packageName", "string", "The TikTok to publish with, for a clone; the official app when absent.",
              aliases=("package_name",), attr="package_name"),
        Field("botUsername", "string", "The operated account: a refused publication joins its health history.",
              aliases=("bot_username",), attr="bot_username", by=HOST),
    ),
    bridge_fields=(device_field("deviceId"),),
    refusals=(
        Refusal("localPath", when={"postType": "video"}, doc="A video without a file."),
        Refusal("text", when={"postType": "text"}, doc="A text post without text."),
    ),
    events=(
        STATUS_EVENT,
        ERROR_EVENT,
        LOG_EVENT,
        Event("upload_result", doc="The publication is over.", fields=(
            Field("success", "bool", "It was published."),
            Field("workflow", OneOf(("upload_post", "text_post")), "A video or a text post."),
            Field("message", "string", "What happened, for a person."),
            Field("error_type", "string", "Why it failed (for a text post, the step it stopped at).",
                  nullable=True),
        )),
    ),
)

CONTRACTS = (YOUTUBE_UPLOAD, TIKTOK_UPLOAD)

__all__ = ["CONTRACTS", "TIKTOK_UPLOAD", "YOUTUBE_UPLOAD"]
