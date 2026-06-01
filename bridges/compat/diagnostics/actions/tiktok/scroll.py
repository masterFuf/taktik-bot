"""Scroll actions for TikTok compat diagnostics."""

from bridges.compat.diagnostics.actions.tiktok import action


@action("tt.scroll.next_video")
def next_video(a, p):
    return a.scroll.scroll_to_next_video()


@action("tt.scroll.watch_video")
def watch_video(a, p):
    duration = float(p.get("duration", 3.0))
    return a.scroll.watch_video(duration=duration)


@action("tt.scroll.profile_down")
def scroll_profile_down(a, p):
    return a.scroll.scroll_profile_videos(direction="down")


@action("tt.scroll.profile_up")
def scroll_profile_up(a, p):
    return a.scroll.scroll_profile_videos(direction="up")

