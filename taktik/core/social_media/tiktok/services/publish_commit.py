"""State machine used to wait for TikTok publish completion."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional


LogFn = Callable[[str, str], None]


@dataclass(frozen=True)
class PublishCommitCallbacks:
    """UI probes/actions required by the publish commit wait loop."""

    handle_publish_confirmation: Callable[[], bool]
    dismiss_popups: Callable[[], None]
    get_progress_percent: Callable[[], Optional[int]]
    is_on_post_screen: Callable[[], bool]
    has_success_indicator: Callable[[], bool]


def _noop_log(_level: str, _message: str) -> None:
    return None


def wait_for_publish_commit(
    callbacks: PublishCommitCallbacks,
    timeout: float = 120.0,
    min_grace: float = 8.0,
    settle_after_progress_gone: float = 3.0,
    clock: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
    log: LogFn | None = None,
) -> bool:
    """Wait until TikTok has likely finished committing the publication."""
    logger = log or _noop_log
    start = clock()
    last_logged_second = -1
    last_progress: Optional[int] = None
    progress_seen = False
    progress_gone_since: Optional[float] = None

    logger("info", "[publishing] waiting for TikTok to finish upload...")

    while clock() - start < timeout:
        elapsed = clock() - start

        if callbacks.handle_publish_confirmation():
            sleep(1.0)
            continue

        callbacks.dismiss_popups()

        progress = callbacks.get_progress_percent()
        if progress is not None:
            progress_seen = True
            progress_gone_since = None
            if progress != last_progress:
                last_progress = progress
                logger("info", f"[publishing] TikTok upload progress: {progress}%")
            sleep(1.2)
            continue

        if progress_seen and progress_gone_since is None:
            progress_gone_since = clock()
            logger("info", "[publishing] TikTok upload badge disappeared, verifying completion...")

        if elapsed < min_grace:
            current_second = int(elapsed)
            if current_second != last_logged_second and current_second in (2, 4, 6):
                last_logged_second = current_second
                logger("debug", f"[publishing] grace period... {current_second}s")
            sleep(1.0)
            continue

        if callbacks.is_on_post_screen():
            current_second = int(elapsed)
            if current_second != last_logged_second:
                last_logged_second = current_second
                logger("info", f"[publishing] still on caption screen after {current_second}s, waiting...")
            sleep(1.2)
            continue

        if callbacks.has_success_indicator():
            logger("info", "[publishing] TikTok success indicator detected")
            sleep(2.0)
            return True

        if progress_gone_since is not None:
            clear_elapsed = clock() - progress_gone_since
            if clear_elapsed < settle_after_progress_gone:
                current_second = int(elapsed)
                if current_second != last_logged_second:
                    last_logged_second = current_second
                    logger(
                        "debug",
                        f"[publishing] upload badge cleared; settling {clear_elapsed:.1f}/{settle_after_progress_gone:.1f}s",
                    )
                sleep(1.0)
                continue

        logger("info", f"[publishing] publish flow stabilized after {elapsed:.1f}s")
        sleep(2.0)
        return True

    if last_progress is not None:
        logger("warning", f"[publishing] commit wait timed out (last seen progress: {last_progress}%)")
    else:
        logger("warning", "[publishing] commit wait timed out")
    return False
