"""`taktik automation`: an Instagram automation run, through the launcher the desktop app runs."""
import json

import click
from rich.console import Console
from rich.panel import Panel

from taktik.core.shared.device.manager import DeviceManager
from taktik.cli.menus.instagram import select_target_type, generate_dynamic_workflow

console = Console()


@click.group()
def automation():
    """🤖 Instagram automation (workflows, hashtags, followers)."""
    pass


@automation.command("workflow")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--config', '-c', type=click.Path(exists=True),
              help="Fichier JSON du run, au format d'une page du desktop (workflowType, target, limits...)")
def workflow_instagram(device_id, config):
    """Run an Instagram automation through the automation handler, the desktop's launcher."""
    from taktik.cli.hosts.instagram import is_internal_workflow_format, run_instagram_payload

    console.print(Panel.fit("[bold green]Lancement du workflow Instagram[/bold green]"))

    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]Aucun appareil connecté.[/red]")
            return
        device_id = devices[0]['id']

    console.print(f"[blue]Utilisation de l'appareil: {device_id}[/blue]")

    if config:
        try:
            with open(config, 'r', encoding='utf-8-sig') as f:
                payload = json.load(f)
            console.print(f"[green]Configuration chargée depuis {config}[/green]")
        except Exception as e:
            console.print(f"[red]Erreur lors du chargement de la configuration: {e}[/red]")
            return
        # The old internal format bypassed the restart, the warmup caps and everything else the
        # launcher reads; it is refused rather than run on a second path.
        if is_internal_workflow_format(payload):
            console.print("[red]Ce fichier est au format interne du workflow (actions, session_settings), "
                          "qui n'est plus accepté.[/red] Écrivez le run comme une page du desktop : "
                          "workflowType, target, limits, probabilities, filters, session.")
            raise SystemExit(1)
        if not payload.get('workflowType'):
            console.print("[red]Le fichier doit nommer son workflowType (feed, target_followers, hashtags...).[/red]")
            raise SystemExit(1)
    else:
        target_type = select_target_type()
        if not target_type:
            console.print("[red]Aucune cible sélectionnée. Arrêt du workflow.[/red]")
            return
        payload = generate_dynamic_workflow(target_type)
        if not payload:
            console.print("[red]Erreur lors de la génération du workflow dynamique.[/red]")
            return

    device_manager = DeviceManager()
    if not device_manager.connect(device_id) or not device_manager.device:
        console.print(f"[red]Impossible de se connecter à l'appareil {device_id}[/red]")
        return

    try:
        run_instagram_payload(device_manager, device_id, payload)
    except Exception as exc:  # noqa: BLE001 - a failed run reports, not tracebacks
        console.print(f"[red]Workflow failed:[/red] {type(exc).__name__}: {exc}")
        raise SystemExit(1)
