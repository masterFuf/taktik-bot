"""Reply button discovery support for Instagram Smart Comment."""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET

from bridges.instagram.runtime.ipc import logger
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_COMMENTS_SELECTORS


class SmartCommentReplyFinderMixin:
    """Find a target comment and click its Reply button."""

    def _find_and_click_reply(self, username: str, content_prefix: str) -> bool:
        """Scroll through comments to find a specific one and click its Reply button."""
        max_scrolls = 30
        username_lower = username.lower()
        logger.info(f"Searching for @{username} in comments (max {max_scrolls} scrolls)...")

        for scroll in range(max_scrolls):
            try:
                xml = self.device.dump_hierarchy()
                if not xml:
                    logger.warning(f"Scroll {scroll}: empty XML dump")
                    self._scroll_comments_down()
                    time.sleep(0.8)
                    continue

                root = ET.fromstring(xml)

                recycler = root
                for elem in root.iter():
                    rid = elem.get("resource-id", "") or ""
                    if POST_COMMENTS_SELECTORS.comments_list_resource_key in rid:
                        recycler = elem
                        break

                reply_bounds = None
                found_username = False

                for vg in recycler.iter():
                    if vg.get("class", "") != "android.view.ViewGroup":
                        continue

                    has_target_user = False
                    reply_btn = None

                    for child in vg:
                        child_class = child.get("class", "") or ""
                        child_text = (child.get("text", "") or "").strip().lower()
                        child_desc = (child.get("content-desc", "") or "").strip().lower()

                        if (
                            child_text == username_lower
                            or child_desc == username_lower
                            or child_text == username_lower + " "
                            or child_desc == username_lower + " "
                        ):
                            has_target_user = True

                        if child_class == "android.widget.Button" and child_text in POST_COMMENTS_SELECTORS.reply_button_labels:
                            reply_btn = child

                    if has_target_user and reply_btn is not None:
                        reply_bounds = reply_btn.get("bounds", "")
                        found_username = True
                        break
                    if has_target_user:
                        found_username = True
                        children_info = []
                        for c in vg:
                            ct = (c.get("text", "") or "").strip()
                            cc = (c.get("class", "") or "").split(".")[-1]
                            cb = c.get("bounds", "")
                            children_info.append(f"{cc}('{ct}' {cb})")
                        logger.debug(f"Scroll {scroll}: found @{username} but no Reply sibling. Children: {children_info}")

                if reply_bounds:
                    match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", reply_bounds)
                    if match:
                        x1, y1, x2, y2 = (
                            int(match.group(1)),
                            int(match.group(2)),
                            int(match.group(3)),
                            int(match.group(4)),
                        )
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        logger.info(f"Clicking Reply for @{username} at ({cx}, {cy}) bounds={reply_bounds}")
                        self.device.click(cx, cy)
                        time.sleep(1)
                        return True
                    logger.warning(f"Could not parse Reply bounds: {reply_bounds}")

                if found_username:
                    logger.debug(f"Scroll {scroll}: @{username} visible but Reply button not found yet, scrolling...")
                else:
                    visible = []
                    for elem in recycler.iter():
                        cd = (elem.get("content-desc", "") or "").strip()
                        if (
                            cd
                            and re.match(r"^[\w][\w.]{0,29}\s*$", cd)
                            and cd.strip().lower() not in POST_COMMENTS_SELECTORS.reply_search_ignored_usernames
                        ):
                            visible.append(cd.strip())
                    logger.debug(f"Scroll {scroll}: visible usernames = {visible}")

            except Exception as e:
                logger.warning(f"Error finding reply button (scroll {scroll}): {e}")

            self._scroll_comments_down()
            time.sleep(0.8)

        logger.error(f"Could not find @{username} after {max_scrolls} scrolls")
        return False
