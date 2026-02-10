"""
Shared utility functions for bridge scripts.

Usage:
    from bridges.common.utils import parse_count

    parse_count("18.5K")  # -> 18500
    parse_count("1.2M")   # -> 1200000
    parse_count("424")    # -> 424
"""


def parse_count(text: str) -> int:
    """
    Parse count strings like '18.5K', '1.2M', '3B', '424' to integer.

    Handles comma separators and K/M/B suffixes (case-insensitive).
    Returns 0 on invalid input.
    """
    if not text:
        return 0

    text = text.strip().replace(',', '').replace(' ', '')

    multiplier = 1
    upper = text.upper()
    if upper.endswith('K'):
        multiplier = 1000
        text = text[:-1]
    elif upper.endswith('M'):
        multiplier = 1000000
        text = text[:-1]
    elif upper.endswith('B'):
        multiplier = 1000000000
        text = text[:-1]

    try:
        return int(float(text) * multiplier)
    except (ValueError, OverflowError):
        return 0
