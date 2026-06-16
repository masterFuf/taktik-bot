"""DM-related IPC event helpers shared by bridge runtimes."""


class DMIpcMixin:
    """Emit direct-message events through the core IPC send primitive."""

    def dm_conversation(self, conversation: dict) -> None:
        """Send conversation data to desktop app."""
        self.send("dm_conversation", conversation=conversation)

    def dm_progress(self, current: int, total: int, name: str) -> None:
        """Send DM reading progress."""
        self.send("dm_progress", current=current, total=total, name=name)

    def dm_stats(self, stats: dict) -> None:
        """Send DM workflow stats."""
        self.send("dm_stats", stats=stats)

    def dm_sent(self, conversation: str, success: bool, error: str = None) -> None:
        """Send DM sent result."""
        self.send("dm_sent", conversation=conversation, success=success, error=error)

    def new_follower(self, follower: dict) -> None:
        """Send a scraped new-follower item (inbox v2)."""
        self.send("new_follower", follower=follower)

    def follow_back_result(self, result: dict) -> None:
        """Send a follow-back execution result (inbox v2)."""
        self.send("follow_back_result", result=result)

    def unreplied_conversation(self, conversation: dict) -> None:
        """Send a scraped conversation with its unreplied flag (inbox v2 phase 2)."""
        self.send("unreplied_conversation", conversation=conversation)

    def message_request(self, request: dict) -> None:
        """Send a scraped message request (inbox v2 phase 3)."""
        self.send("message_request", request=request)

    def request_result(self, result: dict) -> None:
        """Send a message-request decision result (accept/decline/reply) (inbox v2 phase 3)."""
        self.send("request_result", result=result)
