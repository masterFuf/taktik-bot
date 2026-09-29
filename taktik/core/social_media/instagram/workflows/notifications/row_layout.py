"""Pure geometry helpers for pairing per-row controls on the activity surface.

On the follow-requests sub-screen each request row shows a username on the left
and Confirm/Delete buttons on the right, all on the same horizontal band. To act
on a specific username we pair its label box with the action button on the same
row by vertical-center proximity.

The primitives themselves now live in the shared owner
``taktik/core/shared/device/ui_dump.py`` — the same bounds parser had been copied
into several surfaces. This module keeps the notifications-facing import path so
existing callers and tests stay valid.
"""

from __future__ import annotations

from taktik.core.shared.device.ui_dump import (
    center,
    index_of_closest_row,
    parse_bounds,
    vertical_center,
)

__all__ = ["parse_bounds", "vertical_center", "center", "index_of_closest_row"]
