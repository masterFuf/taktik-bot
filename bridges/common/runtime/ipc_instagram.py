"""Instagram-related IPC event helpers shared by bridge runtimes."""


class InstagramIpcMixin:
    """Emit Instagram events through the core IPC send primitive."""

    def instagram_stats(
        self,
        profiles_visited: int = 0,
        profiles_interacted: int = 0,
        profiles_filtered: int = 0,
        private_profiles: int = 0,
        likes: int = 0,
        follows: int = 0,
        comments: int = 0,
        stories_watched: int = 0,
        story_likes: int = 0,
        errors: int = 0,
    ) -> None:
        """Send comprehensive Instagram stats update."""
        self.send("instagram_stats", stats={
            "profiles_visited": profiles_visited,
            "profiles_interacted": profiles_interacted,
            "profiles_filtered": profiles_filtered,
            "private_profiles": private_profiles,
            "likes": likes,
            "follows": follows,
            "comments": comments,
            "stories_watched": stories_watched,
            "story_likes": story_likes,
            "errors": errors,
        })

    def instagram_action(self, action: str, username: str, details: dict = None) -> None:
        """Send Instagram action event."""
        data = {"action": action, "username": username}
        if details:
            data["details"] = details
        self.send("instagram_action", **data)

    def follow_event(self, username: str, success: bool = True, profile_data: dict = None) -> None:
        """Send follow event for real-time activity."""
        data = {"username": username, "success": success}
        if profile_data:
            data["profile_data"] = profile_data
        self.send("follow_event", **data)

    def like_event(self, username: str, likes_count: int = 1, profile_data: dict = None) -> None:
        """Send like event for real-time activity."""
        data = {"username": username, "likes_count": likes_count}
        if profile_data:
            data["profile_data"] = profile_data
        self.send("like_event", **data)

    def story_event(self, username: str, stories_watched: int = 1, stories_liked: int = 0,
                    profile_data: dict = None) -> None:
        """Send story watch/like event for real-time activity."""
        data = {"username": username, "stories_watched": stories_watched, "stories_liked": stories_liked}
        if profile_data:
            data["profile_data"] = profile_data
        self.send("story_event", **data)

    def unfollow_event(self, username: str, success: bool = True) -> None:
        """Send unfollow event."""
        self.send("unfollow_event", username=username, success=success)

    def profile_visit(self, username: str, followers: int = None, is_private: bool = False) -> None:
        """Send profile visit event."""
        self.send("instagram_profile_visit", username=username, followers=followers, is_private=is_private)

    def scraping_profile_visit(self, username: str, biography: str = None,
                               followers_count: int = None, following_count: int = None,
                               posts_count: int = None, full_name: str = None,
                               is_business: bool = False, business_category: str = None,
                               is_private: bool = False, is_verified: bool = False) -> None:
        """Signal that we've visited a profile during scraping."""
        data: dict = dict(
            username=username,
            is_business=is_business,
            is_private=is_private,
            is_verified=is_verified,
        )
        if biography is not None:
            data["biography"] = biography
        if followers_count is not None:
            data["followers_count"] = followers_count
        if following_count is not None:
            data["following_count"] = following_count
        if posts_count is not None:
            data["posts_count"] = posts_count
        if full_name is not None:
            data["full_name"] = full_name
        if business_category is not None:
            data["business_category"] = business_category
        self.send("scraping_profile_visit", **data)

    def scraping_dq_progress(self, username: str, count: int, max_count: int) -> None:
        """Emit live following-collection progress during deep qualify."""
        self.send("scraping_dq_progress", username=username, count=count, max_count=max_count)

    def post_skipped(self, author: str, reason: str = "already_processed", hashtag: str = None) -> None:
        """Send post skipped event."""
        self.send("post_skipped", author=author, reason=reason, hashtag=hashtag)

    def current_post(self, author: str, likes_count: int = None, comments_count: int = None,
                     caption: str = None, hashtag: str = None) -> None:
        """Send current post metadata for live panel."""
        self.send("current_post", author=author, likes_count=likes_count,
                  comments_count=comments_count,
                  caption=caption[:100] if caption else None,
                  hashtag=hashtag)
