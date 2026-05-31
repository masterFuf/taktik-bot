import taktik.core as core_module

from taktik.core.shared.device.manager import DeviceManager as SharedDeviceManager
from taktik.core.shared.device.facade import Direction
from taktik.core.social_media.instagram.actions.core.device.facade import DeviceFacade


def test_core_lazy_exports_resolve_compat_symbols():
    assert core_module.get_device_facade() is DeviceFacade
    assert core_module.get_direction() is Direction
    assert core_module.get_device_manager() is SharedDeviceManager

    assert core_module.DeviceFacade is DeviceFacade
    assert core_module.Direction is Direction
    assert core_module.DeviceManager is SharedDeviceManager
