"""Timing helpers for Instagram DM bridge interactions."""

import random


def calculate_dm_typing_delay(text: str) -> float:
    """Calculate a human-looking typing delay without typing character by character."""
    char_count = len(text)
    base_time = char_count * random.uniform(0.03, 0.05)
    thinking_time = random.uniform(0.5, 1.5)
    return min(base_time + thinking_time, 5.0)


__all__ = ["calculate_dm_typing_delay"]
