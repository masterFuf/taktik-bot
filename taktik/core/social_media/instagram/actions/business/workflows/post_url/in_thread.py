"""Engaging the comment thread of a post, rather than the people behind it.

The other family of Post URL actions walks AWAY from the post to visit profiles. This one
stays: it likes and answers comments where they were written. Nothing here navigates, so a
run in this mode leaves the post exactly once — at the end.

Two orthogonal intentions, each with its own budget:

  * LIKE a comment   — the cheapest signal there is, no text published, nothing to get wrong
    beyond tapping the right heart;
  * REPLY to one     — a published text under someone's name, so it goes through the AI's own
    "is this worth answering" gate before anything is typed.

Reading the thread is the expensive part (a Litho dump per screen), so each screen is read
ONCE and both intentions are served from that single read.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

DEFAULT_MAX_COMMENT_LIKES = 10
DEFAULT_MAX_COMMENT_REPLIES = 3
_MAX_SCREENS = 12


def engage_thread(
    workflow,
    effective_config: Dict[str, Any],
    stats: Dict[str, Any],
    reply_writer: Optional[Callable[[str, str], Optional[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Like and/or answer the comments of the post currently open.

    `reply_writer(username, their_comment)` returns `{comment, ...}` when the AI decided the
    comment deserves an answer, or None/falsy to skip it. Absent (standalone, or AI off), the
    run likes comments and publishes nothing — the mode degrades instead of inventing text.
    """
    like_enabled = bool(effective_config.get('like_comments'))
    reply_enabled = bool(effective_config.get('reply_to_comments')) and reply_writer is not None
    outcome = {'comment_likes': 0, 'replies': 0, 'seen': 0, 'skipped': 0}
    if not like_enabled and not reply_enabled:
        return outcome

    max_likes = int(effective_config.get('max_comment_likes') or DEFAULT_MAX_COMMENT_LIKES)
    max_replies = int(effective_config.get('max_comment_replies') or DEFAULT_MAX_COMMENT_REPLIES)
    # Never answer, or like, our own account: the operated account is usually the post author
    # or already present in its own thread.
    own = {str(effective_config.get('own_username') or '').strip().lower().lstrip('@')} - {''}

    comment_action = getattr(workflow, 'comment_business', None)
    if comment_action is None:
        workflow.logger.warning("In-thread mode: no comment action available, skipping")
        return outcome

    from taktik.core.social_media.instagram.workflows.common.comment_reading import (
        read_visible_comments,
    )

    handled: set = set()
    for _ in range(_MAX_SCREENS):
        if (not like_enabled or outcome['comment_likes'] >= max_likes) and \
           (not reply_enabled or outcome['replies'] >= max_replies):
            break
        if _session_stopped(workflow):
            break

        fresh = [c for c in read_visible_comments(workflow.device)
                 if _key(c) not in handled and c['username'].lower() not in own]
        if not fresh:
            if not _scroll_thread(workflow):
                break
            continue

        for comment in fresh:
            handled.add(_key(comment))
            outcome['seen'] += 1
            if _session_stopped(workflow):
                break

            if like_enabled and outcome['comment_likes'] < max_likes:
                result = comment_action.like_comment_in_thread(comment['username'])
                if result.get('success'):
                    outcome['comment_likes'] += 1
                elif result.get('skipped_reason'):
                    outcome['skipped'] += 1
                workflow._human_like_delay('click')

            if reply_enabled and outcome['replies'] < max_replies:
                try:
                    decision = reply_writer(comment['username'], comment['text'])
                except Exception as exc:
                    workflow.logger.warning(f"Reply generation failed for @{comment['username']}: {exc}")
                    decision = None
                text = (decision or {}).get('comment', '').strip() if decision else ''
                if not text:
                    outcome['skipped'] += 1
                    continue
                reply = comment_action.reply_to_comment_in_thread(
                    comment['username'], text,
                    reply_to_text=comment['text'],
                    ai_metadata=_reply_metadata(decision, effective_config),
                )
                if reply.get('success'):
                    outcome['replies'] += 1
                # Sending a reply closes the composer and can move the thread, so the next
                # screen is re-read from scratch rather than trusted from before the send.
                break

        if not _scroll_thread(workflow):
            break

    stats['comment_likes'] = stats.get('comment_likes', 0) + outcome['comment_likes']
    stats['comment_replies'] = stats.get('comment_replies', 0) + outcome['replies']
    workflow.logger.info(
        f"In-thread engagement: {outcome['comment_likes']} like(s), {outcome['replies']} reply(ies), "
        f"{outcome['seen']} comment(s) seen, {outcome['skipped']} skipped"
    )
    return outcome


def _reply_metadata(decision: Dict[str, Any], effective_config: Dict[str, Any]) -> Dict[str, Any]:
    """What only the AI knows, for the stored record: model, cost, why, and the post."""
    return {
        'source': 'ai',
        'model': decision.get('model'),
        'cost_usd': decision.get('cost_usd'),
        'reasoning': decision.get('reasoning'),
        'language': decision.get('language'),
        'post_url': effective_config.get('source'),
        'post_author': effective_config.get('post_author'),
    }


def _key(comment: Dict[str, Any]) -> str:
    """Identity of a comment across screens: who wrote it and the head of what they wrote.

    Deliberately not the username alone — one person can leave several comments under the
    same post, and collapsing them would silently drop all but the first.
    """
    return f"{comment.get('username', '')}:{(comment.get('text') or '')[:60]}"


def _session_stopped(workflow) -> bool:
    manager = getattr(workflow, 'session_manager', None)
    if manager is None:
        return False
    try:
        should_continue, reason = manager.should_continue()
    except Exception:
        return False
    if not should_continue:
        workflow.logger.warning(f"In-thread engagement stopped: {reason}")
        return True
    return False


def _scroll_thread(workflow) -> bool:
    """Reveal the next screen of comments. False when the thread is no longer showing."""
    try:
        if not workflow._is_comments_view_open():
            return False
        workflow.scroll_actions.scroll_down()
        time.sleep(0.6)
        return True
    except Exception:
        return False


__all__ = ["engage_thread", "DEFAULT_MAX_COMMENT_LIKES", "DEFAULT_MAX_COMMENT_REPLIES"]
