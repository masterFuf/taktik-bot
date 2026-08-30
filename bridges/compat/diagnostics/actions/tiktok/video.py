"""Video actions for TikTok compat diagnostics."""

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.video.like")
def like_video(a, p):
    return a.video.click_like_button()


@action("tt.video.double_tap_like")
def double_tap_like(a, p):
    return a.video.double_tap_like()


@action("tt.video.click_comment")
def click_comment(a, p):
    return a.video.click_comment_button()


@action("tt.video.click_share")
def click_share(a, p):
    return a.video.click_share_button()


@action("tt.video.click_favorite")
def click_favorite(a, p):
    return a.video.click_favorite_button()


@action("tt.video.follow")
def follow_author(a, p):
    return a.video.click_video_follow_button()

@action("tt.video.collect_post")
def collect_post(a, p):
    """Read the link AND the identity of the video on screen. ACTS lightly: it opens the share
    sheet and taps Copy link, then closes it — nothing is published.

    The two halves are reported apart on purpose. A link that comes back without a key means the
    author could not be read, and such a post must NOT be stored: TikTok mints a new short link on
    every copy, so a row keyed on the URL would be created afresh on every visit.
    """
    from taktik.core.social_media.tiktok.actions.atomic.post_link_actions import PostLinkActions

    collected = PostLinkActions(a.device).collect_post()
    if not collected:
        return {"success": False, "message": "no link or no identity for this video"}

    logger.info(
        f"tt.video.collect_post: {collected['post_key']} -> {collected['post_url']}"
    )
    return {
        "success": True,
        "message": f"{collected['post_key']} -> {collected['post_url']}",
        "details": collected,
    }
