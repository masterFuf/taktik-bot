"""Run the Taktik Agent from a terminal.

The Agent is the bot's autonomous Instagram path, and it was reachable only from the desktop app:
its bridge was the single caller, so a standalone user had no way to start it.

Nothing about the workflow required that. `TaktikAgentWorkflow` lives in `taktik/core/agent/`,
takes its device manager and its config by injection, and treats the notifier as optional. A run
goes through `run_instagram_agent`, the launcher the desktop bridge calls: the device is prepared
the way the bridge prepares it (clone-aware proxy, device facade, selector overrides of the
installed version) and Instagram gets the same clean restart. It used to be launched hot on the raw
device, on the official package whatever `packageName` said. The AI factory builds the same
provider as the bridge's, from `taktik/core/app/ai/`.

The Agent is AI by nature: its decisions are the model's. The OpenRouter key is therefore made sure
of before the phone is touched (`ai_key.py`): the environment, the key typed earlier, the saved
one, or asked for at a terminal; in a scripted run (a pipe, CI) a missing key stops the command
with exit code 2. Never from a flag: a key on the command line lands in the shell history and in
the process list.
"""
from __future__ import annotations

from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from taktik.cli.common.ai_key import MISSING_KEY_EXIT, MissingAIKeyError, ensure_ai_key, is_interactive

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

#: The Taktik Agent's workflow id, the one its handler is registered under.
AGENT_WORKFLOW_ID = "instagram.engagement.taktik_agent"


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
def run_agent(device_id: str | None, params: tuple[str, ...]) -> None:
    """Start an autonomous Agent session on Instagram."""
    from taktik.cli.commands.workflow_cmds import _coerce
    from taktik.cli.common.instagram_host import CliInstagramHost
    from taktik.core.shared.device.manager import DeviceManager
    from taktik.core.social_media.instagram.workflows.agent.agent_handler import run_instagram_agent

    config: dict[str, Any] = {}
    for pair in params:
        if "=" not in pair:
            raise click.BadParameter(f"expected key=value, got '{pair}'")
        key, _, raw = pair.partition("=")
        config[key.strip()] = _coerce(raw.strip())

    try:
        api_key = ensure_ai_key(AGENT_WORKFLOW_ID, config, interactive=is_interactive(), echo=console.print)
    except MissingAIKeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(MISSING_KEY_EXIT)

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

    from taktik.core.app.ai.factory import build_ai_service

    def ai_service_factory(*, api_key: str, ipc=None, vision_model=None, text_model=None):
        # Standalone CLI: no premium taxonomy to inject, the classifier stays free-form.
        return build_ai_service(api_key=api_key, ipc=ipc, vision_model=vision_model, text_model=text_model,
                                report_spend=False)

    config.setdefault("openrouter_api_key", api_key)

    effective = {**QUOTA_DEFAULTS, **{k: v for k, v in config.items() if k in QUOTA_DEFAULTS}}
    console.print(Panel.fit(
        "\n".join(f"[cyan]{k}:[/cyan] {v}" for k, v in effective.items()),
        title="[bold]Session quotas[/bold]", border_style="blue",
    ))

    workflows: list = []
    try:
        runtime = CliInstagramHost(manager, device_id).agent_runtime(config.get("packageName"))
        result = run_instagram_agent(
            config,
            device_manager=runtime.device_manager,
            restart=runtime.restart,
            ipc=_ConsoleNotifier(),
            ai_service_factory=ai_service_factory,
            on_workflow=workflows.append,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted; asking the agent to stop.[/yellow]")
        workflow = workflows[0] if workflows else None
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
    stats = getattr(workflows[0], "stats", None) if workflows else None
    if isinstance(stats, dict):
        for key, value in stats.items():
            console.print(f"  [cyan]{key}:[/cyan] {value}")


__all__ = ["agent"]
