import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from taktik.core.shared.device.manager import DeviceManager
from taktik.core.social_media.instagram.core.manager import InstagramManager

console = Console()


@click.group("management")
def management():
    """🔧 Gestion manuelle Instagram (auth, DM). Publishing: `taktik publish`."""
    pass

@management.group("auth")
def auth():
    """Authentication and account management."""
    pass

@auth.command("login")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--username', '-u', help="Nom d'utilisateur, email ou numéro de téléphone")
@click.option('--password', '-p', help="Mot de passe (sera demandé de manière sécurisée si non fourni)")
@click.option('--save-session/--no-save-session', default=True, help="Sauvegarder la session après connexion (système Taktik)")
@click.option('--save-instagram-login/--no-save-instagram-login', default=False, help="Sauvegarder les infos de login dans Instagram")
def login_instagram(device_id, username, password, save_session, save_instagram_login):
    """Log in to an Instagram account, as the desktop does (`instagram.account.login`)."""
    from getpass import getpass
    from taktik.cli.common.instagram_host import run_instagram_account_payload

    console.print(Panel.fit("[bold green]🔐 Connexion à Instagram[/bold green]"))

    manager, device_id = _dm_device(device_id)
    if not InstagramManager(device_id).is_installed():
        console.print("[red]❌ Instagram n'est pas installé sur cet appareil.[/red]")
        return

    if not username:
        username = Prompt.ask("[cyan]👤 Nom d'utilisateur, email ou numéro de téléphone[/cyan]")
    if not password:
        password = getpass("🔑 Mot de passe: ")
    if not username or not password:
        console.print("[red]❌ Username et password requis.[/red]")
        return

    console.print(f"\n[cyan]👤 Username:[/cyan] {username}")
    console.print(f"[cyan]💾 Save session (Taktik):[/cyan] {'Yes' if save_session else 'No'}")
    console.print(f"[cyan]💾 Save login info (Instagram):[/cyan] {'Yes' if save_instagram_login else 'No'}\n")

    payload = {
        "username": username,
        "password": password,
        "maxRetries": 3,
        "saveSession": save_session,
        "saveLoginInfoInstagram": save_instagram_login,
    }
    try:
        # Clean restart, then the login: the desktop's account launcher.
        with console.status("[bold yellow]🔄 Connexion en cours...[/bold yellow]", spinner="dots"):
            result = run_instagram_account_payload(manager, device_id, "instagram.account.login", payload)
    except Exception as e:  # noqa: BLE001 - a failed run reports, not tracebacks
        console.print(f"\n[bold red]❌ Erreur inattendue: {type(e).__name__}: {e}[/bold red]")
        return

    console.print()
    if result.get('success'):
        console.print(Panel.fit(
            f"[bold green]✅ Connexion réussie ![/bold green]\n\n"
            f"[cyan]👤 Username:[/cyan] {result.get('username', username)}\n"
            f"[cyan]🔄 Tentatives:[/cyan] {result.get('attempts', '?')}\n"
            f"[cyan]💾 Session sauvegardée:[/cyan] {'Oui' if result.get('session_saved') else 'Non'}",
            title="[bold green]Succès[/bold green]",
            border_style="green"
        ))
        return

    console.print(Panel.fit(
        f"[bold red]❌ Échec de la connexion[/bold red]\n\n"
        f"[cyan]👤 Username:[/cyan] {result.get('username', username)}\n"
        f"[cyan]🔄 Tentatives:[/cyan] {result.get('attempts', '?')}\n"
        f"[cyan]❌ Erreur:[/cyan] {result.get('message', '')}\n"
        f"[cyan]🏷️ Type d'erreur:[/cyan] {result.get('error_type') or 'unknown'}",
        title="[bold red]Échec[/bold red]",
        border_style="red"
    ))

    # Hints depending on the error type
    error_type = result.get('error_type')
    if error_type == 'credentials_error':
        console.print("\n[yellow]💡 Vérifiez vos identifiants et réessayez.[/yellow]")
    elif error_type == '2fa_required':
        console.print("\n[yellow]💡 2FA requis - Cette fonctionnalité sera bientôt disponible.[/yellow]")
    elif error_type == 'suspicious_login':
        console.print("\n[yellow]💡 Instagram a détecté une connexion inhabituelle.[/yellow]")
        console.print("[yellow]   Essayez de vous connecter manuellement d'abord.[/yellow]")

# ==================== DM GROUP ====================

@management.group("dm")
def dm():
    """Instagram direct messages, on the desktop's DM runtime (`instagram.engagement.dm_read` /
    `dm_send`)."""


def _dm_device(device_id):
    """(device manager, serial) of the named device, or of the only one connected."""
    manager = DeviceManager()
    if not device_id:
        devices = DeviceManager.list_devices()
        if not devices:
            console.print("[red]❌ Aucun appareil connecté.[/red]")
            raise SystemExit(1)
        device_id = devices[0]['id']
        console.print(f"[blue]📱 Utilisation de l'appareil: {device_id}[/blue]")
    if not manager.connect(device_id) or not getattr(manager, "device", None):
        console.print(f"[red]❌ Connexion impossible à {device_id}.[/red]")
        raise SystemExit(1)
    return manager, device_id


def _run_dm(device_id, workflow_id, payload) -> dict:
    """One DM command through its handler, the path of the desktop's DM bridge."""
    from taktik.cli.common.instagram_host import run_instagram_dm_payload

    manager, device_id = _dm_device(device_id)
    try:
        result = run_instagram_dm_payload(manager, device_id, workflow_id, payload)
    except Exception as exc:  # noqa: BLE001 - a failed run reports, not tracebacks
        console.print(f"[red]❌ {type(exc).__name__}: {exc}[/red]")
        raise SystemExit(1)
    if not result.get("success"):
        console.print(f"[red]❌ {result.get('error') or 'Échec'}[/red]")
        raise SystemExit(1)
    return result


def _read_inbox(device_id, limit, requests_folder, to_answer, with_messages):
    payload = {"command": "read_requests" if requests_folder else "read", "limit": limit}
    result = _run_dm(device_id, "instagram.engagement.dm_read", payload)
    conversations = result.get("conversations") or []
    if to_answer:
        conversations = [conv for conv in conversations if conv.get("can_reply")]

    account = result.get("account_username")
    title = "Demandes de messages" if requests_folder else "Boîte de réception"
    table = Table(title=f"{title}{f' de @{account}' if account else ''}")
    table.add_column("Conversation", style="cyan")
    table.add_column("Messages lus", justify="right")
    table.add_column("À répondre", justify="center")
    table.add_column("Dernier message", style="dim")
    for conv in conversations:
        messages = conv.get("messages") or []
        last = (messages[-1].get("text") or "") if messages else ""
        state = "à jour" if conv.get("up_to_date") else ""
        table.add_row(conv.get("username") or "?", str(len(messages)),
                      "oui" if conv.get("can_reply") else "non", (last[:60] or state))
    console.print(table)

    if with_messages:
        for conv in conversations:
            messages = conv.get("messages") or []
            if not messages:
                continue
            console.print(f"\n[bold cyan]@{conv.get('username')}[/bold cyan]")
            for message in messages:
                who = "moi" if message.get("is_sent") else conv.get("username")
                console.print(f"  [dim]{message.get('timestamp') or ''}[/dim] {who}: {message.get('text') or ''}")


@dm.command("inbox")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--limit', '-l', default=20, help="Nombre de conversations à lire (0 : toute la boîte)")
@click.option('--requests', 'requests_folder', is_flag=True, help="Lire le dossier des demandes de messages")
@click.option('--to-answer', '-u', is_flag=True, help="Seulement les conversations qui attendent notre réponse")
def dm_inbox(device_id, limit, requests_folder, to_answer):
    """Lire la boîte de réception comme le desktop : redémarrage, compte, conversations, base."""
    _read_inbox(device_id, limit, requests_folder, to_answer, with_messages=False)


@dm.command("read-all")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--limit', '-l', default=10, help="Nombre de conversations à lire (0 : toute la boîte)")
@click.option('--requests', 'requests_folder', is_flag=True, help="Lire le dossier des demandes de messages")
def dm_read_all(device_id, limit, requests_folder):
    """Lire les conversations et afficher leurs messages (même lecture que `dm inbox`)."""
    _read_inbox(device_id, limit, requests_folder, False, with_messages=True)


@dm.command("send")
@click.option('--device-id', '-d', help="ID de l'appareil (ex: emulator-5566)")
@click.option('--to', '-t', required=True, help="Username de la conversation")
@click.option('--message', '-m', required=True, help="Message à envoyer")
def dm_send(device_id, to, message):
    """Répondre dans une conversation de la boîte, comme le desktop (réponse enregistrée en base).

    Pour écrire à quelqu'un qui n'est pas dans la boîte : le DM à froid
    (`taktik workflows run instagram.engagement.coldDm`)."""
    result = _run_dm(device_id, "instagram.engagement.dm_send", {"username": to, "message": message})
    console.print(Panel(
        f"[green]✅ Message envoyé[/green]\n[cyan]Conversation:[/cyan] @{result.get('username')}",
        title="[bold green]Succès[/bold green]",
        border_style="green",
    ))
