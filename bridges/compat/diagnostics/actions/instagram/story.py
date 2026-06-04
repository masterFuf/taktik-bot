"""Story actions for Instagram compat diagnostics."""

import time

from loguru import logger

from bridges.compat.diagnostics.actions.instagram import action


@action("story.like")
def like_story(a, p):
    return a.click.click_story_like_button()


@action("story.go_to_next")
def story_next(a, p):
    return a.nav.navigate_to_next_story()


@action("story.go_to_previous")
def story_prev(a, p):
    a.device.swipe_right()
    return True


@action("story.close")
def story_close(a, p):
    """Close the story viewer (swipe down; back press is unreliable on this version)."""
    a.click.close_story()
    time.sleep(0.4)
    if a.detection.is_story_viewer_open():
        a.device.press("back")
        time.sleep(0.4)
    closed = not a.detection.is_story_viewer_open()
    logger.info(f"Story closed: {closed}")
    return closed


@action("story.open_from_tray")
def story_open_from_tray(a, p):
    """Open a friend's story from the home feed tray (index 0 = first friend)."""
    index = int(p.get("story_index", 0))
    return a.click.click_feed_story(index)


@action("story.count_feed_tray")
def story_count_feed_tray(a, p):
    """Count the stories in the home feed tray (visible + total parsed from content-desc)."""
    visible = a.detection.count_visible_feed_stories()
    total = a.detection.get_feed_tray_total()
    if total and total >= visible:
        message = f"{visible} visibles / {total} au total"
    elif visible > 0:
        message = f"{visible} visibles"
    else:
        message = "aucune story au tray (sur le feed ?)"
    logger.info(f"Feed tray stories: {message}")
    return {"success": True, "message": message, "details": {"visible": visible, "total": total}}


@action("story.count_in_viewer")
def story_count_in_viewer(a, p):
    """Story counter inside the viewer: 'X of Y' content-desc, else progress-bar segments."""
    current, total = a.detection.get_story_count_from_viewer()
    if total == 0:
        meta = a.detection.get_story_viewer_metadata()
        current = current or int(meta.get("current_story") or 0)
        total = total or int(meta.get("total_stories") or 0)
    if total > 0:
        message = f"story {current}/{total}" if current else f"{total} stories"
    else:
        message = "compteur indisponible"
    logger.info(f"Story viewer counter: {message}")
    return {"success": True, "message": message, "details": {"current": current, "total": total}}


@action("story.reply")
def story_reply(a, p):
    """Reply (text) to the current story via the message composer."""
    text = p.get("text", "\U0001f525")
    if not a.click.open_story_reply_composer():
        logger.error("Story reply composer not found")
        return False
    if not a.kb.type_text(text):
        logger.error("Could not type story reply")
        return False
    return a.kb.press_enter()


@action("story.react")
def story_react(a, p):
    """React to the current story with a quick-reaction emoji (index 0-5)."""
    reaction = p.get("reaction")
    raw_index = p.get("emoji_index")
    emoji_index = int(raw_index) if raw_index not in (None, "") else None
    return a.click.react_to_story(reaction=reaction, emoji_index=emoji_index)


@action("story.is_open")
def story_is_open(a, p):
    """Whether the full-screen story viewer is currently open."""
    result = a.detection.is_story_viewer_open()
    logger.info(f"Story viewer open: {result}")
    return result


@action("story.metadata")
def story_metadata(a, p):
    """Username, posted time and 'N of M' counter of the current story (from content-desc)."""
    meta = a.detection.get_story_viewer_metadata()
    if meta.get("is_open"):
        prefix = "[PUB] " if meta.get("is_ad") else ""
        parts = [f"{prefix}@{meta.get('title') or '?'}"]
        if meta.get("timestamp"):
            parts.append(str(meta["timestamp"]))
        if meta.get("total_stories"):
            parts.append(f"{meta.get('current_story')}/{meta['total_stories']}")
        message = " - ".join(parts)
    else:
        message = "aucune story ouverte"
    logger.info(f"Story metadata: {message}")
    return {"success": bool(meta.get("is_open")), "message": message, "details": meta}


@action("story.is_ad")
def story_is_ad(a, p):
    """Whether the current story is a sponsored ad (workflows must skip, not interact)."""
    is_ad = a.detection.is_story_ad()
    logger.info(f"Story is ad: {is_ad}")
    return {
        "success": True,
        "message": "pub (sponsorisee)" if is_ad else "story normale",
        "details": {"is_ad": is_ad},
    }


@action("story.scroll_tray")
def story_scroll_tray(a, p):
    """Scroll the home feed story tray left to reveal more friends' stories."""
    return a.click.scroll_feed_stories_left()

