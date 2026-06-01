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
