"""Timing helpers for Instagram DM bridge interactions."""

import random

from taktik.core.shared.behavior.sampling import sample_within


def calculate_dm_typing_delay(text: str) -> float:
    """Calculate a human-looking typing delay without typing character by character.

    Capped at 5 s. A delay over the cap is drawn again, and a message too long for any draw to
    fit takes a delay in the last second under the cap -- not 5.0 s every time, which most
    messages over ~90 characters used to get."""
    char_count = len(text)

    def draw() -> float:
        base_time = char_count * random.uniform(0.03, 0.05)
        thinking_time = random.uniform(0.5, 1.5)
        return base_time + thinking_time

    return sample_within(draw, 0.0, 5.0, edge_band=1.0)


__all__ = ["calculate_dm_typing_delay"]
