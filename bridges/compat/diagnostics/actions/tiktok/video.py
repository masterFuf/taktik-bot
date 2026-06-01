"""Video actions for TikTok compat diagnostics."""

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

