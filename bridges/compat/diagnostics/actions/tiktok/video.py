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


@action("tt.video.repost")
def repost_video(a, p):
    """Repost the video on screen onto our own profile. ACTS: it publishes.

    Reports "already reposted" apart from "reposted now": the two look the same to a caller that
    only reads success, and only one of them is an action the account just took.
    """
    from taktik.core.social_media.tiktok.actions.atomic.repost_actions import RepostActions

    actions = RepostActions(a.device)
    before = actions.is_reposted()
    if before is None:
        return {"success": False, "message": "no share sheet on this screen"}
    if before:
        return {"success": True, "message": "already reposted", "details": {"already": True}}

    done = actions.repost_video()
    logger.info(f"tt.video.repost: {done}")
    return {
        "success": done,
        "message": "reposted" if done else "the sheet does not read as reposted",
        "details": {"already": False},
    }


@action("tt.video.undo_repost")
def undo_repost(a, p):
    """Remove the repost of the video on screen. ACTS: it unpublishes."""
    from taktik.core.social_media.tiktok.actions.atomic.repost_actions import RepostActions

    done = RepostActions(a.device).undo_repost()
    logger.info(f"tt.video.undo_repost: {done}")
    return {"success": done, "message": "repost removed" if done else "still reads as reposted"}


@action("tt.video.is_reposted")
def is_reposted(a, p):
    """READS ONLY: does the share sheet say this video is already on our profile?

    None is reported as a failure rather than as False on purpose -- "we could not look" and
    "it is not reposted" lead to opposite actions.
    """
    from taktik.core.social_media.tiktok.actions.atomic.repost_actions import RepostActions

    state = RepostActions(a.device).is_reposted()
    return {
        "success": state is not None,
        "message": {True: "reposted", False: "not reposted"}.get(state, "sheet unreadable"),
        "details": {"reposted": state},
    }
