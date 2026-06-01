"""Threads-related IPC event helpers shared by bridge runtimes."""


class ThreadsIpcMixin:
    """Emit Threads events through the core IPC send primitive."""

    def threads_stats(
        self,
        profiles_visited: int = 0,
        profiles_interacted: int = 0,
        profiles_filtered: int = 0,
        private_profiles: int = 0,
        likes: int = 0,
        follows: int = 0,
        reposts: int = 0,
        replies: int = 0,
        errors: int = 0,
    ) -> None:
        """Send comprehensive Threads stats update."""
        self.send("threads_stats", stats={
            "profiles_visited": profiles_visited,
            "profiles_interacted": profiles_interacted,
            "profiles_filtered": profiles_filtered,
            "private_profiles": private_profiles,
            "likes": likes,
            "follows": follows,
            "reposts": reposts,
            "replies": replies,
            "errors": errors,
        })

    def threads_action(self, action: str, username: str, details: dict = None) -> None:
        """Send Threads action event."""
        data = {"action": action, "username": username}
        if details:
            data["details"] = details
        self.send("threads_action", **data)

    def threads_profile_visit(self, username: str, followers: int = None, is_private: bool = False) -> None:
        """Send Threads profile visit event."""
        self.send("threads_profile_visit", username=username, followers=followers, is_private=is_private)
