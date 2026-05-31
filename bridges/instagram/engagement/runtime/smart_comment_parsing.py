"""Parsing helpers for the Instagram Smart Comment bridge."""

from __future__ import annotations

import re
from typing import Any

from bridges.instagram.base import logger


def parse_litho_comments(dumpsys_output: str) -> list[dict[str, Any]]:
    """Parse Instagram Litho dumpsys output into visible comment records."""
    comments: list[dict[str, Any]] = []

    patterns = {
        "username": re.compile(
            r'text="([\w][\w.]{0,29})"\s+props="\{"synthetic":true\}"'
        ),
        "comment": re.compile(
            r'row_comment_textview_comment\s+text="([^"]+)"'
        ),
        "likes": re.compile(
            r'row_comment_textview_like_count\s+text="(\d+)"'
        ),
        "like_button": re.compile(
            r"row_comment_like_button"
        ),
        "view_replies": re.compile(
            r'text="(?:View|Voir|Afficher)\s+\d+\s+(?:more\s+)?(?:repl|réponse)'
        ),
    }

    events = []
    for name, pattern in patterns.items():
        for match in pattern.finditer(dumpsys_output):
            value = match.group(1) if match.lastindex else ""
            events.append((match.start(), name, value))

    events.sort(key=lambda x: x[0])

    n_usernames = sum(1 for _, event_type, _ in events if event_type == "username")
    n_comments = sum(1 for _, event_type, _ in events if event_type == "comment")
    logger.debug(f"Litho parse: {n_usernames} usernames, {n_comments} comment texts")

    if n_comments == 0:
        return comments

    current_username = None

    for _, event_type, value in events:
        if event_type == "username":
            current_username = value

        elif event_type == "likes":
            like_count = int(value) if value else 0
            if comments and like_count > 0:
                comments[-1]["likes"] = like_count

        elif event_type == "view_replies":
            pass

        elif event_type == "comment":
            if not current_username:
                continue

            comment_text = value.strip()
            if not comment_text:
                continue

            is_reply = False
            parent_username = None
            if comment_text.startswith("@"):
                is_reply = True
                mention_match = re.match(r"@([\w][\w.]{0,29})", comment_text)
                if mention_match:
                    parent_username = mention_match.group(1)

            comments.append({
                "username": current_username,
                "text": comment_text,
                "likes": 0,
                "is_reply": is_reply,
                "parent_username": parent_username,
                "position_top": 0,
            })
            current_username = None

        elif event_type == "like_button":
            pass

    return comments
