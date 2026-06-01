"""JSON event helpers for the Instagram Smart Comment bridge."""

from bridges.instagram.runtime.ipc import send_message as send_event


def emit_comment_scraped(
    *,
    index: int,
    username: str,
    content: str,
    likes: int,
    is_author: bool,
    is_reply: bool,
    parent_username: str,
) -> None:
    send_event(
        "comment_scraped",
        index=index,
        username=username,
        content=content,
        likes=likes,
        is_author=is_author,
        is_reply=is_reply,
        parent_username=parent_username,
    )


def emit_scrape_progress(*, current: int, total: int, scroll: int) -> None:
    send_event("scrape_progress", current=current, total=total, scroll=scroll)


def emit_scrape_complete(*, total: int) -> None:
    send_event("scrape_complete", total=total)


__all__ = [
    "emit_comment_scraped",
    "emit_scrape_complete",
    "emit_scrape_progress",
]
