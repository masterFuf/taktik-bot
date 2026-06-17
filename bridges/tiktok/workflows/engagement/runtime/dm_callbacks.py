"""IPC callback wiring for TikTok DM bridge workflow runners."""

from __future__ import annotations

from bridges.tiktok.runtime.ipc import (
    logger,
    send_dm_conversation,
    send_dm_progress,
    send_dm_sent,
    send_activity_notification,
    send_dm_stats,
    send_follow_back_result,
    send_message_request,
    send_new_follower,
    send_request_result,
    send_unreplied_conversation,
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


def wire_new_followers_read_callbacks(workflow) -> None:
    """Wire stdout events for new-followers scraping (inbox v2)."""

    def on_new_follower(follower):
        send_new_follower(follower)
        logger.info(f"👥 New follower listed: {follower.get('username', 'unknown')}")

    workflow.set_on_new_follower_callback(on_new_follower)


def wire_follow_back_callbacks(workflow) -> None:
    """Wire stdout events for follow-back execution (inbox v2)."""

    def on_result(result):
        send_follow_back_result(result)

    workflow.set_on_follow_back_result_callback(on_result)


def wire_unreplied_callbacks(workflow) -> None:
    """Wire stdout events for unreplied-conversations scraping (inbox v2 phase 2)."""

    def on_conversation(conversation):
        send_unreplied_conversation(conversation)
        logger.info(f"📨 Conversation: {conversation.get('username', 'unknown')} "
                    f"(unreplied={conversation.get('unreplied')})")

    workflow.set_on_unreplied_callback(on_conversation)


def wire_message_requests_read_callbacks(workflow) -> None:
    """Wire stdout events for message-requests scraping (inbox v2 phase 3)."""

    def on_request(request):
        send_message_request(request)
        logger.info(f"📥 Message request: {request.get('username', 'unknown')}")

    workflow.set_on_message_request_callback(on_request)


def wire_request_decision_callbacks(workflow) -> None:
    """Wire stdout events for message-request decisions (accept/decline/reply, inbox v2 phase 3)."""

    def on_result(result):
        send_request_result(result)

    workflow.set_on_request_result_callback(on_result)


def wire_notifications_read_callbacks(workflow) -> None:
    """Wire stdout events for activity/system notifications reading (inbox v2 phase 4)."""

    def on_notification(notification):
        send_activity_notification(notification)
        logger.info(f"🔔 Notification: {notification.get('category')} - {notification.get('title', '')}")

    workflow.set_on_notification_callback(on_notification)


__all__ = [
    "wire_dm_read_callbacks",
    "wire_dm_send_callbacks",
    "wire_new_followers_read_callbacks",
    "wire_follow_back_callbacks",
    "wire_unreplied_callbacks",
    "wire_message_requests_read_callbacks",
    "wire_request_decision_callbacks",
    "wire_notifications_read_callbacks",
]
