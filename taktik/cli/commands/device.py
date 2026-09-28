"""`taktik device`: the phones ADB sees."""
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from taktik.core.shared.device.manager import DeviceManager

console = Console()


@click.group()
def device():
    pass


@device.command(name="list")
def list_devices():
    console.print(Panel.fit("[bold green]Liste des appareils connectés[/bold green]"))
    
    devices = DeviceManager.list_devices()
    
    if not devices:
        console.print("[yellow]Aucun appareil connecté.[/yellow]")
        console.print("[blue]Assurez-vous que l'appareil est connecté et que ADB est correctement configuré.[/blue]")
        return
    
    table = Table(title="Appareils connectés")
    table.add_column("ID", style="cyan")
    table.add_column("Statut", style="green")
    
    for i, device_info in enumerate(devices):
        device_id = device_info['id'] if isinstance(device_info, dict) else device_info
        table.add_row(device_id, "Connecté")
    
    console.print(table)
