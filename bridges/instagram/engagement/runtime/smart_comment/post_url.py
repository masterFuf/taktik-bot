"""Post URL extraction support for the Instagram Smart Comment bridge."""

from __future__ import annotations

import re
import time

from bridges.instagram.runtime.ipc import logger
from taktik.core.shared.device.adb import run_adb_shell_process
from taktik.core.social_media.instagram.ui.selectors.surfaces.post import POST_DETAIL_SELECTORS


class SmartCommentPostUrlMixin:
    """Extract the current Instagram post URL via share sheet and clipboard."""

    def extract_post_url(self) -> str:
        """Extract the current post's URL via Share -> Copy Link."""
        logger.info("Extracting post URL via Share -> Copy Link...")
        try:
            share_btn = None
            for resource_id in POST_DETAIL_SELECTORS.share_button_resource_ids:
                share_btn = self.device(resourceId=resource_id)
                if share_btn.exists:
                    break
            if not share_btn or not share_btn.exists:
                logger.warning("Share button not found")
                return ""

            share_btn.click()
            time.sleep(1.5)

            copy_link = None
            for label in POST_DETAIL_SELECTORS.copy_link_labels:
                elem = self.device(text=label)
                if elem.exists:
                    copy_link = elem
                    break

            if not copy_link:
                for label in POST_DETAIL_SELECTORS.copy_link_description_labels:
                    elem = self.device(description=label)
                    if elem.exists:
                        copy_link = elem
                        break

            if not copy_link:
                logger.warning("Copy link button not found in share sheet")
                self.device.press("back")
                time.sleep(0.5)
                return ""

            copy_link.click()
            time.sleep(1)

            for command_args, label in [
                (["am", "broadcast", "-a", "clipper.get"], "clipboard broadcast"),
                (["dumpsys", "clipboard"], "dumpsys clipboard"),
                (["content", "query", "--uri", "content://clipboard/clip"], "content provider"),
            ]:
                try:
                    result = run_adb_shell_process(
                        self.device_id,
                        command_args,
                        timeout=5,
                        encoding="utf-8",
                        errors="replace",
                    )
                    output = result.stdout.strip() if label == "clipboard broadcast" else result.stdout
                    url_match = re.search(r"(https?://(?:www\.)?instagram\.com/(?:p|reel)/[\w-]+/?)", output)
                    if url_match:
                        post_url = url_match.group(1)
                        logger.info(f"Post URL from {label}: {post_url}")
                        self.post_context.post_url = post_url
                        return post_url
                except Exception as e:
                    logger.debug(f"{label.capitalize()} failed: {e}")

            logger.warning("Could not read clipboard - post URL not captured")
            return ""

        except Exception as e:
            logger.error(f"Error extracting post URL: {e}")
            try:
                self.device.press("back")
                time.sleep(0.5)
            except Exception:
                pass
            return ""
