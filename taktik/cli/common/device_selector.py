"""
Device Selector (Shared CLI utility)

Eliminates the 5+ duplications of device selection + connection logic in cli/main.py.
"""

import click
from rich.console import Console

console = Console()


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
        console.print(f"[bold]{idx}.[/bold] {device['id']} ({device['status']})")
    
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
