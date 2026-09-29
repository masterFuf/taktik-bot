"""Throwaway media for a publish rehearsal.

The publish workflow needs a real file on disk: it pushes it to the device and picks the most
recent gallery item. The bench has nothing to publish, and shipping a fixture image into a public
repository for the sake of a diagnostic is not worth it, so the file is generated.

Written as a plain PNG encoder rather than through Pillow because the bot does not otherwise
depend on it, and a diagnostic must not be the reason a dependency appears.

The image is deliberately 1080x1080: Instagram rejects or reframes very small or oddly shaped
media, and a rehearsal that fails on the aspect ratio would say nothing about the navigation.
"""
from __future__ import annotations

import os
import struct
import tempfile
import zlib


def _chunk(tag: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def make_rehearsal_image(size: int = 1080, rgb: tuple = (32, 34, 42)) -> str:
    """Write a solid-colour PNG to a temp file and return its path. Caller deletes it."""
    row = bytes(rgb) * size
    raw = b"".join(b"\x00" + row for _ in range(size))  # filter byte 0 per scanline

    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))  # 8-bit truecolour
    png += _chunk(b"IDAT", zlib.compress(raw, 6))
    png += _chunk(b"IEND", b"")

    fd, path = tempfile.mkstemp(prefix="taktik_rehearsal_", suffix=".png")
    with os.fdopen(fd, "wb") as handle:
        handle.write(png)
    return path


def discard(path: str) -> None:
    """Remove the generated file, ignoring an already-gone one."""
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


__all__ = ["make_rehearsal_image", "discard"]
