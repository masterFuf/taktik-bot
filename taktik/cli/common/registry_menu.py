"""Interactive workflow picker driven by the Agent registry.

The TikTok menu used to be nine "Coming soon" entries, one of which promised that "the
architecture is ready, workflows will be implemented in the next update" — while fifteen TikTok
workflows were running in production from the desktop app every day. The menu was not behind the
code; it had simply never been connected to it.

Rather than write one branch per workflow, which is exactly how the CLI fell behind, the menu is
generated from what the registry actually holds. A platform gains a menu entry the day its handler
is registered.

Parameters are typed in as `key=value` instead of prompted one by one. A per-workflow prompt list
would be a second place to keep in step with each workflow's config, and it is the drift this
module exists to remove. The operator can also start with none: several workflows carry usable
defaults, and the ones that do not report the missing key themselves.
"""
from __future__ import annotations

from typing import Any

import click
from rich.console import Console

from taktik.cli.commands.workflow_cmds import _coerce
from taktik.cli.common.registry_builder import build_registry

console = Console()


def _prompt_params() -> dict[str, Any]:
    """Collect `key=value` lines until an empty one."""
    console.print(
        "\n[cyan]Parameters[/cyan] [dim]key=value, one per line, empty line to finish. "
        "Leave empty to use the workflow defaults.[/dim]"
    )
    params: dict[str, Any] = {}
    while True:
        raw = click.prompt("  param", default="", show_default=False)
        raw = raw.strip()
        if not raw:
            return params
        if "=" not in raw:
            console.print("  [yellow]expected key=value[/yellow]")
            continue
        key, _, value = raw.partition("=")
        params[key.strip()] = _coerce(value.strip())
        console.print(f"  [green]{key.strip()}[/green] = {params[key.strip()]!r}")


def run_registry_menu(platform: str, device_manager, device_id: str) -> None:
    """Show every registered workflow for `platform` and run the chosen one.

    `device_manager` must already be connected: the handlers receive the device, they never open
    the connection themselves.
    """
    from taktik.core.agent.kernel.contracts import WorkflowInvocation

    build = build_registry(
        device=getattr(device_manager, "device", None),
        device_id=device_id,
        device_manager=device_manager,
    )

    if build.failures:
        console.print("\n[yellow]Some platforms could not be registered:[/yellow]")
        for label, error in build.failures:
            console.print(f"  [yellow]{label}[/yellow]: {error}")

    workflow_ids = build.ids_for(platform)
    if not workflow_ids:
        console.print(f"\n[red]No workflow registered for {platform}.[/red]")
        input("\nPress Enter to continue...")
        return

    console.print(f"\n[bold cyan]{platform.capitalize()} workflows[/bold cyan]")
    for index, workflow_id in enumerate(workflow_ids, 1):
        # The platform prefix is already in the title; show what distinguishes the entries.
        console.print(f"[bold]{index}.[/bold] {workflow_id.split('.', 1)[1]}  [dim]{workflow_id}[/dim]")
    back = len(workflow_ids) + 1
    console.print(f"[bold]{back}.[/bold] ← Back")

    choice = click.prompt("\n[bold]Your choice[/bold]", type=click.IntRange(1, back), show_choices=False)
    if choice == back:
        return

    workflow_id = workflow_ids[choice - 1]
    params = _prompt_params()

    console.print(f"\n[blue]Running[/blue] [bold]{workflow_id}[/bold] on [cyan]{device_id}[/cyan]")
    handler = build.registry.resolve(workflow_id)
    invocation = WorkflowInvocation(platform=platform, workflow_id=workflow_id, params=params)

    try:
        result = handler(invocation, dict(params))
    except Exception as exc:  # noqa: BLE001 - report at the operator, never a raw traceback
        console.print(f"[red]Workflow failed:[/red] {type(exc).__name__}: {exc}")
        input("\nPress Enter to continue...")
        return

    if isinstance(result, dict) and result.get("success") is False:
        console.print(f"[red]Failed:[/red] {result.get('error') or result.get('message') or result}")
    else:
        console.print("[green]Done.[/green]")
        if isinstance(result, dict):
            for key, value in result.items():
                if key != "success":
                    console.print(f"  [cyan]{key}:[/cyan] {value}")

    input("\nPress Enter to continue...")


__all__ = ["run_registry_menu"]
