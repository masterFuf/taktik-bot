"""`taktik tiktok`, also started on its own as `taktik-tiktok` (setup.py), and `taktik launch`."""
import click
from rich.console import Console
from rich.panel import Panel

from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.manager import InstagramManager
from taktik.core.social_media.tiktok.manager import TikTokManager
from taktik.cli.support import language
from taktik.cli.support.database import open_database

console = Console()


@click.group()
def tiktok():
    """TikTok automation.

    Configures the database itself. `taktik-tiktok` is its own console_script, so it enters
    HERE and never runs the `cli()` callback -- and without that call `get_db_service()`
    raises on the first query. Guarded so the normal `taktik tiktok ...` path, which has
    already configured it, does not build a second client.
    """
    from taktik.core import database as _database

    if getattr(_database, "db_service", None) is None:
        open_database()


@tiktok.command("launch")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
def launch_tiktok(device_id):
    """Launch TikTok on the given device."""
    current_translations = language.current_translations
    console.print(Panel.fit("[bold green]Lancement de TikTok[/bold green]"))
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]Utilisation de l'appareil: {device_id}[/blue]")
    tiktok = TikTokManager(device_id)
    if not tiktok.is_installed():
        console.print("[red]TikTok n'est pas installé sur cet appareil.[/red]")
        return
    console.print("[blue]Lancement de TikTok...[/blue]")
    success = tiktok.launch()
    if success:
        console.print(f"\n[green]{current_translations['hashtag_workflow_success']}[/green]")
    else:
        console.print("[red]Échec du lancement de TikTok.[/red]")


@click.command()
@click.option('--network', '-n', required=True, type=click.Choice(['instagram', 'tiktok']), help='Réseau social à lancer')
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
def launch(network, device_id):
    """Launch the chosen social app on the given device."""
    console.print(Panel.fit(f"[bold green]Lancement de {network.capitalize()}[/bold green]"))
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']
        console.print(f"[blue]Utilisation de l'appareil: {device_id}[/blue]")
    if network == 'instagram':
        manager = InstagramManager(device_id)
    elif network == 'tiktok':
        manager = TikTokManager(device_id)
    else:
        console.print("[red]Réseau social non supporté.[/red]")
        return
    if not manager.is_installed():
        console.print(f"[red]{network.capitalize()} n'est pas installé sur cet appareil.[/red]")
        return
    console.print(f"[blue]Lancement de {network.capitalize()}...[/blue]")
    success = manager.launch()
    if success:
        console.print(f"[green]{network.capitalize()} a été lancé avec succès ![/green]")
    else:
        console.print(f"[red]Échec du lancement de {network.capitalize()}.[/red]")
