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
    from taktik.core.social_media.tiktok.actions.atomic.interaction.post_link_actions import PostLinkActions

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
    from taktik.core.social_media.tiktok.actions.atomic.interaction.repost_actions import RepostActions

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
    from taktik.core.social_media.tiktok.actions.atomic.interaction.repost_actions import RepostActions

    done = RepostActions(a.device).undo_repost()
    logger.info(f"tt.video.undo_repost: {done}")
    return {"success": done, "message": "repost removed" if done else "still reads as reposted"}


@action("tt.video.is_reposted")
def is_reposted(a, p):
    """READS ONLY: does the share sheet say this video is already on our profile?

    None is reported as a failure rather than as False on purpose -- "we could not look" and
    "it is not reposted" lead to opposite actions.
    """
    from taktik.core.social_media.tiktok.actions.atomic.interaction.repost_actions import RepostActions

    state = RepostActions(a.device).is_reposted()
    return {
        "success": state is not None,
        "message": {True: "reposted", False: "not reposted"}.get(state, "sheet unreadable"),
        "details": {"reposted": state},
    }


@action("tt.sound.read")
def read_sound(a, p):
    """READS ONLY: the sound label of the video on screen, as the screen writes it."""
    from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions

    label = SoundActions(a.device).read_current_sound()
    return {"success": bool(label), "message": label or "no sound row on this screen"}


@action("tt.sound.open_page")
def open_sound_page(a, p):
    """Open the page of the sound this video uses, and report how many videos use it.

    The count is the point, not decoration: most sounds are somebody's own original audio with a
    handful of posts, and telling those from a trend is what makes harvesting worth its time.
    """
    from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions

    actions = SoundActions(a.device)
    if not actions.open_sound_page():
        return {"success": False, "message": "the sound page did not come up"}

    count = actions.sound_post_count()
    logger.info(f"tt.sound.open_page: {count} post(s)")
    return {
        "success": True,
        # None is reported as unreadable, never as zero -- they lead to opposite decisions.
        "message": f"{count} post(s)" if count is not None else "post count unreadable",
        "details": {"post_count": count},
    }


@action("tt.sound.collect_users")
def collect_sound_users(a, p):
    """From an OPEN sound page: the handles of the people who used this sound.

    Params: max (default 5). Each one costs a profile round trip -- a sound-page cell says
    "Vidéo" and names nobody, so the handle is only reachable by opening it.
    """
    from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions

    limit = int((p or {}).get("max") or 5)
    people = SoundActions(a.device).collect_sound_users(max_users=limit)
    logger.info(f"tt.sound.collect_users: {len(people)}")
    return {
        "success": bool(people),
        "message": f"{len(people)} user(s): " + ", ".join("@" + x["username"] for x in people[:6]),
        "details": {"users": people},
    }


@action("tt.feed.not_interested")
def not_interested(a, p):
    """Send the feed the explicit "less of this" signal. ACTS: it changes what TikTok serves.

    Reports the video BEFORE and AFTER, because the author changing is the only readable proof
    the signal left -- the tap succeeds whether or not it did.
    """
    from taktik.core.social_media.tiktok.actions.atomic.interaction.feed_training_actions import (
        FeedTrainingActions,
    )

    actions = FeedTrainingActions(a.device)
    before = actions._current_author()
    done = actions.mark_not_interested()
    after = actions._current_author()
    logger.info(f"tt.feed.not_interested: {before!r} -> {after!r} ({done})")
    return {
        "success": done,
        "message": f"{before!r} -> {after!r}" if done else f"still on {before!r}",
        "details": {"before": before, "after": after},
    }


@action("tt.feed.training_decision")
def feed_training_decision(a, p):
    """READS ONLY: what a training pass would do with the video on screen, and why.

    Params: keywords (comma-separated). Runs the real decision function against what the screen
    actually says, so a niche can be tuned without spending a session finding out.
    """
    from taktik.core.social_media.tiktok.actions.atomic.detection.sound_actions import SoundActions
    from taktik.core.social_media.tiktok.actions.atomic.detection.video_detector import VideoDetector
    from taktik.core.social_media.tiktok.services.feed.training import (
        normalise_keywords,
        training_decision,
    )

    raw_keywords = str((p or {}).get("keywords") or "")
    keywords = normalise_keywords(raw_keywords.split(","))
    if not keywords:
        return {"success": False, "message": "keywords are required (comma-separated)"}

    detector = VideoDetector(a.device)
    fields = {
        "description": detector.get_video_description() if hasattr(detector, "get_video_description") else "",
        "sound": SoundActions(a.device).read_current_sound(),
        "author": detector.get_video_author(),
    }
    decision = training_decision(list(fields.values()), keywords)
    logger.info(f"tt.feed.training_decision: {decision} on {fields}")
    return {
        "success": True,
        "message": f"{decision} (keywords: {', '.join(keywords)})",
        "details": {"decision": decision, "read": fields, "keywords": keywords},
    }
