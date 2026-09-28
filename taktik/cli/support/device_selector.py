"""
Device Selector (Shared CLI utility)

Eliminates the 5+ duplications of device selection + connection logic in cli/main.py.
"""

import click
from rich.console import Console

console = Console()


def _describe_device(device_id: str) -> str:
    """One line of context read over ADB: Instagram version and system locale.

    Picking a phone by its serial alone tells the operator nothing about what the
    run will face. The Instagram version decides which selector catalog actually
    applies (baseline, or version overrides — see `taktik.core.compat.selectors`),
    so the list says it up front, with a marker when overrides will kick in. The
    locale shown is the SYSTEM one (`persist.sys.locale`): the app's own language
    needs Instagram open on screen, which a device list must not do.

    Best-effort: a phone that answers nothing is still selectable.
    """
    parts = []
    try:
        from taktik.core.shared.device.app_inspection import get_installed_app_version
        from taktik.core.compat.selectors.setup import (
            INSTAGRAM_TARGET_VERSION,
            TIKTOK_TARGET_VERSION,
        )

        # Both platforms, because the pick happens before the workflow choice: the
        # operator must see what EITHER run would face on this phone.
        for label, package, platform, baseline in (
            ("IG", "com.instagram.android", "instagram", INSTAGRAM_TARGET_VERSION),
            ("TT", "com.zhiliaoapp.musically", "tiktok", TIKTOK_TARGET_VERSION),
        ):
            version = get_installed_app_version(device_id, package, platform)
            if version:
                marker = "baseline" if version == baseline else "overrides"
                parts.append(f"{label} {version} [{marker}]")
            else:
                parts.append(f"{label} absent")
    except Exception:
        pass
    try:
        from taktik.core.shared.device.adb import run_adb_shell

        locale = (run_adb_shell(device_id, "getprop persist.sys.locale") or "").strip()
        if locale:
            parts.append(locale)
    except Exception:
        pass
    return " · ".join(parts)


def select_device(device_manager, translations: dict) -> str:
    """Show device list and let user pick one.
    
    Args:
        device_manager: DeviceManager instance
        translations: Current translations dict
    
    Returns:
        device_id string, or None if no device available
    """
    devices = device_manager.list_devices()
    if not devices:
        console.print(f"[red]{translations.get('no_device_connected', '❌ No device connected')}[/red]")
        return None
    
    console.print(f"\n[bold cyan]{translations.get('select_device', '📱 Select device')}[/bold cyan]")
    for idx, device in enumerate(devices, 1):
        detail = _describe_device(device['id'])
        suffix = f" [dim]- {detail}[/dim]" if detail else ""
        console.print(f"[bold]{idx}.[/bold] {device['id']} ({device['status']}){suffix}")
    
    selected = click.prompt(
        f"\n[bold]{translations.get('prompt_choice', 'Your choice')}[/bold]",
        type=click.IntRange(1, len(devices)),
        show_choices=False
    )
    
    device_id = devices[selected - 1]['id']
    console.print(f"[blue]{translations.get('device_selected', '📱 Device selected: {}').format(device_id)}[/blue]")
    return device_id


def connect_device(device_manager, device_id: str, translations: dict) -> bool:
    """Connect to a device and verify it's ready.
    
    Args:
        device_manager: DeviceManager instance
        device_id: Device serial/ID
        translations: Current translations dict
    
    Returns:
        True if connected and ready, False otherwise
    """
    if not device_manager.connect(device_id):
        console.print(f"[red]{translations.get('cannot_connect_device', '❌ Cannot connect to {}').format(device_id)}[/red]")
        return False
    
    if not device_manager.device:
        console.print(f"[red]{translations.get('device_init_error', '❌ Device initialization error')}[/red]")
        return False
    
    return True


def select_and_connect_device(device_manager, translations: dict) -> str:
    """Combined: select a device from list, then connect to it.
    
    Returns:
        device_id string if connected, None otherwise
    """
    device_id = select_device(device_manager, translations)
    if not device_id:
        return None
    
    if not connect_device(device_manager, device_id, translations):
        return None
    
    return device_id
