import taktik.core as core_module

from taktik.core.shared.device.manager import DeviceManager as SharedDeviceManager
from taktik.core.shared.device.facade import Direction


def test_core_lazy_exports_resolve_compat_symbols():
    assert core_module.get_direction() is Direction
    assert core_module.get_device_manager() is SharedDeviceManager

    assert core_module.Direction is Direction
    assert core_module.DeviceManager is SharedDeviceManager
    assert not hasattr(core_module, "DeviceFacade")
