"""
Base Device Facade (compatibility shim)

Canonical location: taktik.core.shared.device.facade
This file re-exports for backward compatibility.
"""

from taktik.core.shared.device.facade import BaseDeviceFacade, Direction

__all__ = ['BaseDeviceFacade', 'Direction']
