"""Registry-driven workflow commands for the standalone CLI.

Every capability the bot gained over the last months shipped as a bridge plus an Agent handler, so
the desktop app could reach it. The CLI menus were not extended, and the result was measurable: 40
workflows with a runnable handler, none reachable from a terminal by its canonical id — no TikTok,
no Threads, no Gmail, no YouTube at all.

These commands close that by going through the registry instead of restating each workflow. A new
platform handler becomes reachable here the day it is registered, with nothing to edit in this
file. That is the point: the previous approach — one hand-written menu branch per workflow — is
exactly why the CLI fell nine months behind.

Parameters are passed as `--param key=value` rather than guessed. Each workflow reads its own
config keys, and inventing a prompt per workflow would recreate the drift this replaces. `--json`
takes a whole config at once, which is what a scripted run wants anyway.
"""
from __future__ import annotations

import json
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from taktik.cli.common.registry_builder import build_registry

console = Console()


def _parse_params(pairs: tuple[str, ...], json_blob: str | None) -> dict[str, Any]:
    """Merge `--json` then `--param key=value`; explicit pairs win over the blob."""
    params: dict[str, Any] = {}

    if json_blob:
        try:
            loaded = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            raise click.BadParameter(f"invalid JSON: {exc}") from exc
        if not isinstance(loaded, dict):
            raise click.BadParameter("--json must be a JSON object")
        params.update(loaded)

    for pair in pairs:
        if "=" not in pair:
            raise click.BadParameter(f"expected key=value, got '{pair}'")
        key, _, raw = pair.partition("=")
        params[key.strip()] = _coerce(raw.strip())

    return params


def _coerce(raw: str) -> Any:
    """Turn a shell string into the type a workflow config expects.

    Workflow configs mix booleans, counts and lists; passing everything as a string would make
    `max_profiles=10` a string and silently break comparisons inside the workflow.
    """
    lowered = raw.lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "none", ""):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    if raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    if "," in raw:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return raw


def _report_failures(build) -> None:
    if not build.failures:
        return
    console.print("\n[yellow]Some platforms could not be registered:[/yellow]")
    for label, error in build.failures:
        console.print(f"  [yellow]{label}[/yellow]: {error}")


@click.group("workflows")
def workflows() -> None:
    """List and run any bot workflow, without the desktop app."""


@workflows.command("list")
@click.option("--platform", "-p", help="Only show one platform (instagram, tiktok, threads, gmail, youtube).")
def list_workflows(platform: str | None) -> None:
    """Show every workflow that has a runnable handler."""
    build = build_registry(device=None, device_id="")
    ids = build.ids_for(platform) if platform else build.workflow_ids

    if not ids:
        known = ", ".join(build.platforms) or "none"
        console.print(f"[red]No workflow for '{platform}'.[/red] Known platforms: {known}")
        _report_failures(build)
        return

    table = Table(title="Available workflows", show_lines=False)
    table.add_column("Platform", style="cyan")
    table.add_column("Workflow id", style="green")

    for workflow_id in ids:
        table.add_row(workflow_id.split(".", 1)[0], workflow_id)

    console.print(table)
    console.print(f"\n[dim]{len(ids)} workflow(s). Run one with:[/dim] "
                  f"[bold]taktik workflows run <id> --device <serial> --param key=value[/bold]")
    _report_failures(build)


@workflows.command("run")
@click.argument("workflow_id")
@click.option("--device", "-d", "device_id", help="ADB serial. Omitted: the only connected device.")
@click.option("--param", "params", multiple=True, help="Workflow parameter, key=value. Repeatable.")
@click.option("--json", "json_blob", help="Whole parameter object as JSON.")
@click.option("--dry-run", is_flag=True, help="Resolve and show the call without touching the device.")
def run_workflow(workflow_id: str, device_id: str | None, params: tuple[str, ...],
                 json_blob: str | None, dry_run: bool) -> None:
    """Run WORKFLOW_ID through the Agent registry."""
    from taktik.core.agent.kernel.contracts import WorkflowInvocation

    resolved_params = _parse_params(params, json_blob)

    if dry_run:
        # Resolution only: prove the id exists and show what would be sent, without a phone.
        build = build_registry(device=None, device_id=device_id or "")
        try:
            build.registry.resolve(workflow_id)
        except KeyError:
            _unknown_workflow(build, workflow_id)
            raise SystemExit(1)
        console.print(f"[green]{workflow_id}[/green] resolves.")
        console.print(f"[cyan]params:[/cyan] {json.dumps(resolved_params, indent=2, default=str)}")
        return

    device_manager, device_id = _connect(device_id)
    if device_manager is None:
        raise SystemExit(1)

    build = build_registry(
        device=device_manager.device,
        device_id=device_id,
        device_manager=device_manager,
    )

    try:
        handler = build.registry.resolve(workflow_id)
    except KeyError:
        _unknown_workflow(build, workflow_id)
        raise SystemExit(1)

    platform = workflow_id.split(".", 1)[0]
    invocation = WorkflowInvocation(platform=platform, workflow_id=workflow_id, params=resolved_params)

    console.print(f"[blue]Running[/blue] [bold]{workflow_id}[/bold] on [cyan]{device_id}[/cyan]")
    try:
        result = handler(invocation, dict(resolved_params))
    except Exception as exc:  # noqa: BLE001 - a failed run must report, not traceback at the user
        console.print(f"[red]Workflow failed:[/red] {type(exc).__name__}: {exc}")
        raise SystemExit(1)

    _print_result(result)


def _unknown_workflow(build, workflow_id: str) -> None:
    console.print(f"[red]Unknown workflow '{workflow_id}'.[/red]")
    platform = workflow_id.split(".", 1)[0]
    siblings = build.ids_for(platform)
    if siblings:
        console.print(f"\n[cyan]Available for {platform}:[/cyan]")
        for candidate in siblings:
            console.print(f"  {candidate}")
    else:
        console.print("\n[cyan]Run[/cyan] [bold]taktik workflows list[/bold] to see every id.")
    _report_failures(build)


def _connect(device_id: str | None):
    """Connect to `device_id`, or to the only connected device. Returns (manager, id)."""
    from taktik.core.shared.device.manager import DeviceManager

    manager = DeviceManager()
    devices = manager.list_devices()
    if not devices:
        console.print("[red]No device connected.[/red]")
        return None, ""

    if not device_id:
        if len(devices) > 1:
            console.print("[red]Several devices connected; pass --device <serial>.[/red]")
            for device in devices:
                console.print(f"  {device['id']} ({device['status']})")
            return None, ""
        device_id = devices[0]["id"]

    if not manager.connect(device_id) or not manager.device:
        console.print(f"[red]Cannot connect to {device_id}.[/red]")
        return None, ""

    return manager, device_id


def _print_result(result: Any) -> None:
    if not isinstance(result, dict):
        console.print(f"[green]Done.[/green] {result}")
        return

    success = result.get("success")
    if success is False:
        console.print(f"[red]Failed:[/red] {result.get('error') or result.get('message') or result}")
        raise SystemExit(1)

    console.print("[green]Done.[/green]")
    for key, value in result.items():
        if key in ("success",):
            continue
        console.print(f"  [cyan]{key}:[/cyan] {value}")


__all__ = ["workflows"]
