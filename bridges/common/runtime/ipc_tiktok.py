"""TikTok-related IPC event helpers shared by bridge runtimes."""


class TikTokIpcMixin:
    """Emit TikTok events through the core IPC send primitive."""

    def tiktok_stats(
        self,
        videos_watched: int = 0,
        videos_liked: int = 0,
        users_followed: int = 0,
        videos_favorited: int = 0,
        videos_skipped: int = 0,
        errors: int = 0,
    ) -> None:
        """Send TikTok stats update."""
        self.send("stats", stats={
            "videos_watched": videos_watched,
            "videos_liked": videos_liked,
            "users_followed": users_followed,
            "videos_favorited": videos_favorited,
            "videos_skipped": videos_skipped,
            "errors": errors,
        })

    def video_info(self, author: str, description: str = None, like_count: str = None,
                   is_liked: bool = False, is_followed: bool = False, is_ad: bool = False,
                   hashtags: list = None, sound: str = None,
                   author_pic: str = None) -> None:
        """Send current TikTok video info."""
        video: dict = {
            "author": author,
            "description": description,
            "like_count": like_count,
            "is_liked": is_liked,
            "is_followed": is_followed,
            "is_ad": is_ad,
        }
        if hashtags:
            video["hashtags"] = hashtags
        if sound:
            video["sound"] = sound
        if author_pic:
            video["author_pic"] = author_pic
        self.send("video_info", video=video)

    def action(self, action: str, target: str = "") -> None:
        """Send action event."""
        self.send("action", action=action, target=target)

    def pause(self, duration: int) -> None:
        """Send pause event."""
        self.send("pause", duration=duration)
