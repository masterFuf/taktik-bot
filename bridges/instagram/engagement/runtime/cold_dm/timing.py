"""Timing helpers for the Instagram Cold DM bridge."""

from __future__ import annotations

import random
import time

from bridges.instagram.runtime.ipc import logger


def wait_before_next_cold_dm(*, index: int, total: int, delay_min: int, delay_max: int) -> None:
    if index >= total - 1:
        return

    delay = random.uniform(delay_min, delay_max)
    logger.info(f"Waiting {delay:.1f}s before next DM...")
    time.sleep(delay)
