"""IPC callback wiring for TikTok DM bridge workflow runners."""

from __future__ import annotations

from bridges.tiktok.runtime.ipc import (
    logger,
    send_dm_conversation,
    send_dm_progress,
    send_dm_sent,
    send_dm_stats,
)


def wire_dm_read_callbacks(workflow) -> None:
    """Wire stdout events for DM conversation reading."""

    def on_conversation(conv_data):
        send_dm_conversation(conv_data)
        logger.info(f"ðŸ“– Read conversation: {conv_data.get('name', 'unknown')}")

    def on_stats(stats_dict):
        send_dm_stats(stats_dict)

    def on_progress(current, total, name):
        send_dm_progress(current, total, name)

    workflow.set_on_conversation_callback(on_conversation)
    workflow.set_on_stats_callback(on_stats)
    workflow.set_on_progress_callback(on_progress)


def wire_dm_send_callbacks(workflow) -> None:
    """Wire stdout events for DM sending."""

    def on_message_sent(result):
        send_dm_sent(
            conversation=result.get("conversation", ""),
            success=result.get("success", False),
            error=result.get("error"),
        )

    def on_stats(stats_dict):
        send_dm_stats(stats_dict)

    def on_progress(current, total, name):
        send_dm_progress(current, total, name)

    workflow.set_on_message_sent_callback(on_message_sent)
    workflow.set_on_stats_callback(on_stats)
    workflow.set_on_progress_callback(on_progress)


__all__ = ["wire_dm_read_callbacks", "wire_dm_send_callbacks"]
