"""Run the Taktik Agent from a terminal.

The Agent is the bot's autonomous Instagram path, and it was reachable only from the desktop app:
its bridge was the single caller, so a standalone user had no way to start it.

Nothing about the workflow required that. `TaktikAgentWorkflow` lives in `taktik/core/agent/`,
takes its device manager and its config by injection, and treats the notifier as optional. The
bridge's AI factory is a three-line wrapper around `AIService` from `taktik/core/app/ai/`, so the
CLI builds the same provider without importing anything from `bridges/` — a module outside
`bridges/` must not depend on one.

The API key is read from the environment rather than a flag: a key on the command line lands in
the shell history and in the process list. Without a key the Agent still runs, with whatever its
own code does when no AI service is injected.
"""
from __future__ import annotations

import os
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

#: Quota keys the workflow reads, with the defaults it applies when they are absent. Declared here
#: so `--show-defaults` cannot drift from the workflow: both are checked by a test.
QUOTA_DEFAULTS: dict[str, int] = {
    "max_likes": 80,
    "max_comments": 15,
    "max_follows": 20,
    "max_profile_visits": 40,
    "max_posts_seen": 150,
    "session_duration_min": 25,
}

API_KEY_ENV = "OPENROUTER_API_KEY"


class _ConsoleNotifier:
    """Minimal stand-in for the bridge IPC: prints instead of emitting JSON on stdout.

    The workflow calls a notifier when one is injected. In standalone there is no desktop reading
    stdout, so events become readable lines. Unknown methods are absorbed rather than raising: the
    notifier is an optional collaborator, and a missing event helper must not stop a session.
    """

    def status(self, status: str, message: str = "") -> None:
        console.print(f"[blue]{status}[/blue] {message}")

    def error(self, message: str, error_code: str = "") -> None:
        suffix = f" [dim]({error_code})[/dim]" if error_code else ""
        console.print(f"[red]{message}[/red]{suffix}")

    def send(self, event_type: str, **payload: Any) -> None:
        console.print(f"[dim]{event_type}[/dim] {payload}")

    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            return None
        return _noop


@click.group("agent")
def agent() -> None:
    """Taktik Agent: autonomous Instagram session."""


@agent.command("defaults")
def show_defaults() -> None:
    """Show the quotas a run uses when nothing is passed."""
    table = Table(title="Taktik Agent quotas")
    table.add_column("Parameter", style="cyan")
    table.add_column("Default", style="green")
    for key, value in QUOTA_DEFAULTS.items():
        table.add_row(key, str(value))
    console.print(table)
    console.print(f"\n[dim]Override any of them with[/dim] [bold]--param {list(QUOTA_DEFAULTS)[0]}=40[/bold]")


@agent.command("run")
@click.option("--device", "-d", "device_id", help="ADB serial. Omitted: the only connected device.")
@click.option("--param", "params", multiple=True, help="Config entry, key=value. Repeatable.")
@click.option("--no-ai", is_flag=True, help="Run without an AI provider even if a key is set.")
def run_agent(device_id: str | None, params: tuple[str, ...], no_ai: bool) -> None:
    """Start an autonomous Agent session on Instagram."""
    from taktik.cli.commands.workflow_cmds import _coerce
    from taktik.core.agent.scenarios.instagram_feed_autopilot import TaktikAgentWorkflow
    from taktik.core.shared.device.manager import DeviceManager
    from taktik.core.social_media.instagram.core.manager import InstagramManager

    config: dict[str, Any] = {}
    for pair in params:
        if "=" not in pair:
            raise click.BadParameter(f"expected key=value, got '{pair}'")
        key, _, raw = pair.partition("=")
        config[key.strip()] = _coerce(raw.strip())

    manager = DeviceManager()
    devices = manager.list_devices()
    if not devices:
        console.print("[red]No device connected.[/red]")
        raise SystemExit(1)
    if not device_id:
        if len(devices) > 1:
            console.print("[red]Several devices connected; pass --device <serial>.[/red]")
            raise SystemExit(1)
        device_id = devices[0]["id"]
    if not manager.connect(device_id) or not manager.device:
        console.print(f"[red]Cannot connect to {device_id}.[/red]")
        raise SystemExit(1)

    instagram = InstagramManager(device_id)
    if not instagram.is_installed():
        console.print("[red]Instagram is not installed on this device.[/red]")
        raise SystemExit(1)
    console.print("[blue]Launching Instagram...[/blue]")
    if not instagram.launch():
        console.print("[red]Failed to launch Instagram.[/red]")
        raise SystemExit(1)

    api_key = "" if no_ai else os.environ.get(API_KEY_ENV, "")
    ai_service_factory = None
    if api_key:
        from taktik.core.app.ai.providers.openrouter import AIService

        def ai_service_factory(*, api_key: str, ipc=None, vision_model=None, text_model=None):  # noqa: F811
            return AIService(api_key=api_key, ipc=ipc, vision_model=vision_model, text_model=text_model)

        config.setdefault("openrouter_api_key", api_key)
    else:
        console.print(
            f"[yellow]No {API_KEY_ENV} in the environment: running without an AI provider.[/yellow]"
        )

    effective = {**QUOTA_DEFAULTS, **{k: v for k, v in config.items() if k in QUOTA_DEFAULTS}}
    console.print(Panel.fit(
        "\n".join(f"[cyan]{k}:[/cyan] {v}" for k, v in effective.items()),
        title="[bold]Session quotas[/bold]", border_style="blue",
    ))

    workflow = TaktikAgentWorkflow(
        manager,
        config,
        ipc=_ConsoleNotifier(),
        ai_service_factory=ai_service_factory,
    )

    try:
        result = workflow.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted; asking the agent to stop.[/yellow]")
        stop = getattr(workflow, "request_stop", None) or getattr(workflow, "stop", None)
        if callable(stop):
            stop()
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 - report at the operator, never a raw traceback
        console.print(f"[red]Agent failed:[/red] {type(exc).__name__}: {exc}")
        raise SystemExit(1)

    if isinstance(result, dict) and result.get("success") is False:
        console.print(f"[red]Failed:[/red] {result.get('error') or result.get('message') or result}")
        raise SystemExit(1)

    console.print("[green]Session finished.[/green]")
    stats = getattr(workflow, "stats", None)
    if isinstance(stats, dict):
        for key, value in stats.items():
            console.print(f"  [cyan]{key}:[/cyan] {value}")


__all__ = ["agent"]
