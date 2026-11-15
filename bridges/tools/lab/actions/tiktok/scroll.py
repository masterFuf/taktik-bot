"""Scroll actions for TikTok compat diagnostics."""

from bridges.tools.lab.actions.tiktok import action


@action("tt.scroll.next_video")
def next_video(a, p):
    """The production advance of the feed, and where its finger went down.

    `gesture_start` is the touch-down of the last swipe: the point sampled, the final one, and
    what placed it (`source`): `ui_bounds` when it was moved off a button of the video read on
    screen, `ui_bounds_clear` when it touched none, `fallback_band` when the screen could not be
    read. A run of these is what proves on a phone that no advance opens a profile or a button."""
    moved = a.scroll.scroll_to_next_video()
    start = a.scroll.device.last_gesture_start()
    return {
        "success": bool(moved),
        "message": (f"next video, touch-down {start.get('final')} ({start.get('source')})" if moved
                    else "same video after the swipes: the pager snapped back"),
        "details": {"gesture_start": start},
    }


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

