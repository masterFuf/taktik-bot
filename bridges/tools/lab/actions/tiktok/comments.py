"""The TikTok comment sheet in the Lab: read it, read who commented, write on it.

Every action goes through the production class of the sheet, `CommentActions`: its gate (nothing
is read before the sheet says it is open: `title`, the id carrying the author, also resolves on the
inbox and the feed), its row-by-row reader, and the handle reader of the post URL workflow.

`tt.comment.read` and `tt.comment.read_commenter_handles` write nothing. `tt.comment.post` and
`tt.comment.reply` publish: a Lab action that comments on a stranger's video is a real comment.
"""

from loguru import logger

from bridges.tools.lab.actions.tiktok import action
from bridges.tools.lab.action_test.params import lab_int
from taktik.core.social_media.tiktok.actions.atomic.interaction.comment_actions import CommentActions


@action("tt.comment.read")
def read(a, p):
    """Read the comments on the open sheet: author, text, likes, each read within its own row.

    The production reader of the sheet (`CommentActions.read_comments`, on the rows
    `read_commenter_handles` walks). Gated on the sheet: polled, because it slides up over the video
    and a read right after the tap cannot tell "not there yet" from "the tap did nothing".
    """
    actions = CommentActions(a.device)
    if not actions._wait_for_sheet():
        logger.warning("tt.comment.read: the comment sheet is not open — refusing to read rows")
        return {"success": False, "message": "comment sheet not open", "details": {"sheetOpen": False}}

    rows = actions.read_comments()
    with_body = sum(1 for row in rows if row.get("text"))
    logger.info(f"tt.comment.read: {len(rows)} comment(s), {with_body} with a body")
    return {
        # Rows without a single body is the failure that matters: the sheet is there, the rows are
        # there, and the reader comes back with names and nothing said.
        "success": bool(rows) and with_body > 0,
        "message": f"{len(rows)} comment(s), {with_body} with a body",
        "details": {
            "sheetOpen": True,
            # The sheet's own total ("16 commentaires"); None when it cannot be read.
            "count": actions.comment_count(),
            # A like count is None, never 0, when the row shows none (no like, or 43.1.4).
            "comments": [
                {"author": row["author"], "text": (row.get("text") or "")[:120], "likeCount": row.get("like_count")}
                for row in rows[:15]
            ],
        },
    }


@action("tt.comment.read_commenter_handles")
def read_commenter_handles(a, p):
    """The people who commented on the video on screen, by their handle, as the post URL workflow
    reads them (`CommentActions.read_commenter_handles`): each row's profile opened to read the
    handle, Back to the sheet. About 13 seconds a commenter. Params: max_commenters (default 2),
    max_scrolls (default 1). Opens the sheet when it is closed; writes nothing.
    """
    rows = CommentActions(a.device).read_commenter_handles(
        max_commenters=lab_int(p, "max_commenters", 2),
        max_scrolls=lab_int(p, "max_scrolls", 1),
    )
    handles = [row["username"] for row in rows]
    logger.info(f"tt.comment.read_commenter_handles: {len(handles)} handle(s)")
    return {
        "success": bool(handles),
        "message": f"{len(handles)} commenter(s): {', '.join('@' + h for h in handles) or 'none'}",
        "details": {"commenters": [{"username": row["username"], "displayName": row.get("display_name")}
                                   for row in rows]},
    }


@action("tt.comment.post")
def post(a, p):
    """Post a comment on the video whose sheet is open. ACTS — this publishes.

    In the Lab alongside `tt.inbox.send_message`, which sends a real DM: the families that write
    belong here too, or the only capabilities ever tested are the harmless ones. The caller
    chooses the video; the action refuses to invent the text.

    Verified by the composer EMPTYING, never by the tap landing.
    """
    text = (p or {}).get("text") or ""
    if not text.strip():
        return {"success": False, "message": "no text given — refusing to post"}

    actions = CommentActions(a.device)
    if not actions.is_comment_sheet_open():
        return {"success": False, "message": "comment sheet not open"}

    before = len(actions.read_comments())
    posted = actions.post_comment(text)
    if not posted:
        actions.discard_draft()
    after = actions.read_comments()
    landed = any(text.strip() in (c.get("text") or "") for c in after)

    logger.info(f"tt.comment.post: posted={posted} visible={landed} ({before} -> {len(after)})")
    return {
        # Both halves: the composer emptied AND the text is readable back on the sheet. The first
        # alone is what "the click landed" looks like.
        "success": bool(posted and landed),
        "message": f"{'posted' if posted else 'refused'}, visible={landed}",
        "details": {"before": before, "after": len(after), "visible": landed},
    }


@action("tt.comment.reply")
def reply(a, p):
    """Reply under one comment. ACTS — this publishes.

    Params: author (required), text (required), toText (optional but recommended — one person
    often leaves several comments, and the author alone picks the first of them).
    """
    params = p or {}
    author = (params.get("author") or "").strip()
    text = (params.get("text") or "").strip()
    to_text = (params.get("toText") or "").strip() or None
    if not author or not text:
        return {"success": False, "message": "author and text are required"}

    actions = CommentActions(a.device)
    if not actions.is_comment_sheet_open():
        return {"success": False, "message": "comment sheet not open"}

    replied = actions.reply_to_comment(author, text, to_text=to_text)
    if not replied:
        actions.discard_draft()
    visible = any(text in (c.get("text") or "") for c in actions.read_comments())

    logger.info(f"tt.comment.reply: replied={replied} visible={visible}")
    return {
        # A reply can sit inside a collapsed thread ("Afficher N reponses"), so invisibility here
        # is not proof of failure — reported apart rather than folded into success.
        "success": bool(replied),
        "message": f"{'replied' if replied else 'refused'}, visible in the flat list={visible}",
        "details": {"visibleInFlatList": visible, "toText": to_text},
    }
