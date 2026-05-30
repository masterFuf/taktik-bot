"""Legacy device compatibility exports.

Canonical implementation owner:
    `taktik.core.shared.device`

This package keeps the historic `taktik.core.device` import path available for
bridges, scripts and tests that still expect the old static helper API.
"""

from .device import DeviceManager

__all__ = ['DeviceManager']
