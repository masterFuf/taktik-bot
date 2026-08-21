"""Re-share a source account's stories from the account currently on the phone.

The shape this exists to prove: a TASK, not a workflow. It runs once, against no target
list, produces no live panel and holds the device for a few seconds. A workflow is this same
thing wrapped in a loop over targets — which is why forcing the relay into one meant either
building a run engine for five gestures or grafting it onto a crawl it has nothing to do
with.

Owns two things the screen sequence must not: the language setup, and the journal.

Language first, always. The relay reaches for "add to my story", whose only anchor is its
wording — the cell has the generic resource-id `button` and is labelled by content-desc. A
localized selector read before `detect_and_optimize` matches nothing, silently, which is the
failure mode the project rule about language detection exists to prevent.

The journal second. Instagram never hands out a story id, so the dedup key is the author plus
the posted-time label the viewer shows. Two passes twenty minutes apart read one story as one
signature; tomorrow's reads as a new one. Without it the relay re-shares the same story on
every tick, which every follower sees immediately.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger

from taktik.core.database.content_relays import ContentRelayService
from taktik.core.social_media.instagram.actions.business.actions.story_relay import (
    StoryRelayBusiness,
)
from taktik.core.social_media.instagram.ui.language import detect_and_optimize

log = logger.bind(module="instagram-story-relay")

#: Slides of the same author to consider in one pass. A story tray is short-lived; a source
#: posting more than this in one sitting is better served by the next tick than by a device
#: standing still.
DEFAULT_MAX_STORIES = 5


def _signature(author: Optional[str], timestamp: Optional[str], index: int) -> Optional[str]:
    """Dedup key for one story slide.

    The slide index is part of it: a source who posts three slides in the same hour shows the
    same author and the same "1 h" label on all three, and without the index the relay would
    treat slides two and three as already handled.
    """
    if not author:
        return None
    return f"{author}|{timestamp or '?'}|{index}"


def relay_source_stories(
    *,
    device,
    source_username: str,
    account_id: Optional[int] = None,
    max_stories: int = DEFAULT_MAX_STORIES,
    session_manager: Any = None,
    automation: Any = None,
) -> Dict[str, Any]:
    """Run one relay pass. Never raises: a relay must not be able to end a device session."""
    report: Dict[str, Any] = {
        "success": False,
        "source_username": source_username,
        "considered": 0,
        "relayed": 0,
        "already_handled": 0,
        "unavailable": 0,
        "failed": 0,
        "skipped_ads": 0,
        "reason": None,
        "outcomes": [],
    }

    if not source_username:
        report["reason"] = "no_source_username"
        return report

    relay = StoryRelayBusiness(device, session_manager, automation=automation)

    try:
        # Before ANY localized selector — see module docstring.
        detect_and_optimize(device)

        opened = relay.open_source_story(source_username)
        if not opened.get("opened"):
            report["reason"] = opened.get("reason") or "story_not_opened"
            log.info(f"No story to relay from @{source_username}: {report['reason']}")
            return report

        for index in range(max_stories):
            identity = relay.current_story_identity()
            if not identity["is_open"]:
                break

            if identity["is_ad"]:
                # Same guard every story path applies: a sponsored slide is never ours to
                # re-share, and interacting with it is a signal we do not want to send.
                report["skipped_ads"] += 1
                if not relay.advance_to_next_story():
                    break
                continue

            # The slide's own rank, as the viewer reports it ("story 2 of 5") — NOT the loop
            # counter. They diverge as soon as a sponsored slide is skipped, and the loop
            # counter would then both mis-key the signature and cut the pass short.
            position = identity["current_story"] or (index + 1)
            total = identity["total_stories"]
            if total and position > total:
                break

            report["considered"] += 1
            signature = _signature(identity["author"], identity["timestamp"], position)
            if not signature:
                report["failed"] += 1
                report["outcomes"].append({"index": position, "status": "failed",
                                           "reason": "unreadable_story_header"})
                if not relay.advance_to_next_story():
                    break
                continue

            if ContentRelayService.already_handled(
                account_id=account_id,
                source_username=source_username,
                media_signature=signature,
            ):
                report["already_handled"] += 1
                if not relay.advance_to_next_story():
                    break
                continue

            outcome = relay.push_current_story_to_mine()
            status = outcome["status"]
            report[status if status in ("relayed", "unavailable") else "failed"] += 1
            report["outcomes"].append({
                "index": position,
                "signature": signature,
                "status": status,
                "reason": outcome.get("reason"),
            })

            ContentRelayService.record(
                account_id=account_id,
                source_username=source_username,
                media_signature=signature,
                status=status,
                reason=outcome.get("reason"),
            )

            if status == "relayed":
                log.success(f"Relayed a story from @{source_username} ({signature})")
            elif status == "unavailable":
                # The product answering no, not a broken selector. Worth one clear line: it is
                # what tells the operator the source must mention us for this to work at all.
                log.info(
                    f"@{source_username} story {position}: Instagram does not offer "
                    f"'add to my story' — the story has to mention this account"
                )

            if not relay.advance_to_next_story():
                break

        report["success"] = True
        return report

    except Exception as exc:  # noqa: BLE001 - a relay must never take the session down
        log.error(f"Story relay failed for @{source_username}: {exc}")
        report["reason"] = f"{type(exc).__name__}: {exc}"
        return report
    finally:
        # Whatever happened, the phone must not be left sitting in a fullscreen viewer: the
        # next task would open onto a screen it did not expect.
        try:
            relay.leave_story_viewer()
        except Exception as exc:  # noqa: BLE001
            log.debug(f"Could not leave the story viewer: {exc}")


__all__ = ["relay_source_stories", "DEFAULT_MAX_STORIES"]
