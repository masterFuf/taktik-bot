"""Comment-sheet READ action for TikTok compat diagnostics.

Opening and closing the sheet already exist (`tt.video.click_comment`,
`tt.popups.{has,close}_comments`); what was missing is the only question that matters for the
catalogue — can we READ what is in it.

Read-only: no comment is posted and no reply sent. Writing on the sheet is a product capability
still to be prioritised, and a Lab action that comments on a stranger's video is a real comment.
"""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.tiktok import action
from taktik.core.social_media.tiktok.actions.core.utils import first_matching
from taktik.core.social_media.tiktok.actions.atomic.comment_actions import CommentActions
from taktik.core.social_media.tiktok.ui.selectors.surfaces.video.comments import COMMENT_SELECTORS


def _raw(a):
    device = getattr(a, "device", None)
    return getattr(device, "_device", None) or device


def _wait_for_sheet(device, timeout: float = 6.0) -> bool:
    """True once the comment sheet has actually drawn."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if first_matching(device, COMMENT_SELECTORS.sheet_indicator):
            time.sleep(0.4)
            return True
        time.sleep(0.4)
    return False


@action("tt.comment.read")
def read(a, p):
    """Read the comments on the open sheet: author, text, likes.

    Gated on `sheet_indicator` and the gate is the point. `title`, the id carrying the author,
    is NOT comment-specific — it resolves on the inbox and on the feed too — so reading rows
    without first proving the sheet is open would return one confident, wrong "comment" from
    whatever screen happens to be up. Measured 2026-08-29: the indicator reads 3 and 5 on the two
    versions' sheets and zero on every other captured screen.
    """
    device = _raw(a)

    # Poll rather than read once. The sheet slides up over the video and takes a beat: read
    # immediately after the tap and it is genuinely not there yet, which is indistinguishable
    # from "the tap did nothing" — measured on 43.1.4, where the same sequence failed on the
    # first read and passed three seconds later.
    if not _wait_for_sheet(device):
        logger.warning("tt.comment.read: the comment sheet is not open — refusing to read rows")
        return {
            "success": False,
            "message": "comment sheet not open",
            "details": {"sheetOpen": False},
        }

    def _texts(selectors):
        found = []
        for element in first_matching(device, selectors):
            text = (getattr(element, "text", "") or "").strip()
            if text:
                found.append(text)
        return found

    authors = _texts(COMMENT_SELECTORS.comment_author)
    bodies = _texts(COMMENT_SELECTORS.comment_text)
    likes = _texts(COMMENT_SELECTORS.comment_like_count)
    header = _texts(COMMENT_SELECTORS.comment_count_header)

    logger.info(
        f"tt.comment.read: {len(authors)} author(s), {len(bodies)} text(s), "
        f"{len(likes)} like count(s)"
    )
    return {
        # Authors without texts is the failure that matters: the sheet is there, the rows are
        # there, and the reader comes back with names and nothing said.
        "success": bool(authors and bodies),
        "message": f"{len(authors)} comment(s), {len(bodies)} with a body",
        "details": {
            "sheetOpen": True,
            "header": header[0] if header else "",
            "authors": authors[:15],
            "texts": [t[:120] for t in bodies[:15]],
            # Absent on 43.1.4 and on comments with no like: an empty list here is not a dead
            # anchor, which is why it is reported apart rather than folded into the total.
            "likeCounts": likes[:15],
        },
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
