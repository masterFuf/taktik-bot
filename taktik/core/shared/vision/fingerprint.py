"""Perceptual fingerprint of an image — "is this the same picture?", not "the same bytes?".

Two screenshots of the same ad are never byte-identical: the phone re-encodes, the frame
lands a pixel higher, a video creative is caught on a different frame. A cryptographic hash
would call those four different images and the corpus would count one creative as four.

`dhash` answers the useful question instead. It compares each pixel to its right-hand
neighbour on a 9x8 greyscale reduction, so it encodes the STRUCTURE of the image (where it
gets lighter and darker) and ignores scale, compression and small shifts in brightness.

Implemented on Pillow + numpy, both already required. A dedicated library (imagehash) would
add a dependency to an open-source repo for sixteen lines.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

log = logger.bind(module="vision-fingerprint")

# 8x8 comparisons -> 64 bits -> 16 hex chars. Enough to separate creatives without being so
# fine that a re-encode of the same image lands on a different value.
_HASH_SIZE = 8


def dhash(image, hash_size: int = _HASH_SIZE) -> Optional[str]:
    """Difference hash of a PIL image, as a hex string. ``None`` when it cannot be computed.

    Never raises: fingerprinting a screenshot must not be able to break the run that took it.
    """
    if image is None:
        return None
    try:
        import numpy as np

        # One extra column: N+1 pixels give N horizontal comparisons.
        small = image.convert("L").resize((hash_size + 1, hash_size))
        pixels = np.asarray(small, dtype=np.int16)
        diff = pixels[:, 1:] > pixels[:, :-1]
        bits = diff.flatten()
        value = 0
        for bit in bits:
            value = (value << 1) | int(bit)
        return f"{value:0{hash_size * hash_size // 4}x}"
    except Exception as exc:
        log.debug(f"Could not fingerprint image: {exc}")
        return None


def hamming_distance(left: Optional[str], right: Optional[str]) -> Optional[int]:
    """How many bits differ between two fingerprints. ``None`` if either is missing.

    Useful to group near-duplicates (a video creative caught on two frames usually lands
    within a few bits) rather than treating them as separate creatives.
    """
    if not left or not right or len(left) != len(right):
        return None
    try:
        return bin(int(left, 16) ^ int(right, 16)).count("1")
    except ValueError:
        return None
