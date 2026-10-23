"""`taktik automation`: an Instagram automation run, through the launcher the desktop app runs."""
import json

import click
from rich.console import Console
from rich.panel import Panel

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
    """Run an Instagram automation through the automation handler, the desktop's launcher.

    The phone is chosen, not connected: the launcher reads and validates the run, then connects it."""
    from taktik.cli.commands.workflows import _choose_phone
    from taktik.cli.hosts.ai_key import MissingAIKeyError, exit_without_key
    from taktik.cli.hosts.instagram import is_internal_workflow_format, run_instagram_payload
    from taktik.cli.hosts.phone import PhoneNotConnectedError

    console.print(Panel.fit("[bold green]Lancement du workflow Instagram[/bold green]"))

    phone = _choose_phone(device_id)
    if phone is None:
        raise SystemExit(1)

    console.print(f"[blue]Utilisation de l'appareil: {phone.device_id}[/blue]")

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

    try:
        run_instagram_payload(phone.device_manager, phone.device_id, payload)
    except MissingAIKeyError as exc:
        # The same cause ends the same way as in `taktik workflows run`, not as a failed run.
        exit_without_key(exc, console)
    except PhoneNotConnectedError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
    except Exception as exc:  # noqa: BLE001 - a failed run reports, not tracebacks
        console.print(f"[red]Workflow failed:[/red] {type(exc).__name__}: {exc}")
        raise SystemExit(1)
