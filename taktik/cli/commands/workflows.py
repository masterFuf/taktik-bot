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

A run that uses AI needs an AI key (OpenRouter or Anthropic) before the phone is touched (`ai_key.py`): asked for at
a terminal, refused with exit code 2 in a scripted run (`--json`, a pipe, CI). A manual run needs
none and never reaches an AI client.

`run` chooses the phone but does not connect to it (`hosts/phone.py`): the launcher reads and
validates its payload, then calls the `connect` the CLI host gave it, and the phone connects there.
A payload the reader refuses (a setting out of its bounds, a scraping with no source) ends with
exit code 1 and nothing connected, as from the desktop bridges. A key the workflow's declaration does
not have (`maxProfiles` at the root, where the feed reads `limits.maxProfiles`) is refused before
that, dry run included, with exit code 2: the key, and where the declaration has it
(`taktik/core/contract/settings_keys.py`, the declaration the app's tools are checked against). So does a phone without network:
the launcher's network door refuses it (`NETWORK_UNREACHABLE` in the message) before the app starts.
"""
from __future__ import annotations

import json
from typing import Any

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from taktik.cli.hosts.ai_key import (
    MissingAIKeyError,
    ensure_ai_key,
    exit_without_key,
    is_interactive,
    resolve_cli_credential,
)
from taktik.cli.hosts.phone import CliPhone, PhoneNotConnectedError
from taktik.cli.hosts.registry import build_registry, handler_on_phone
from taktik.core.contract.ai_request import asks_for_ai
from taktik.core.contract.registry import contracts_by_id
from taktik.core.contract.settings_keys import undeclared_settings

console = Console()

#: Workflows whose name does not say they log the account out, and what they do to it. The CLI
#: warns, then runs one only once the operator said yes: at a terminal, or `--yes` in a script.
LOGS_THE_ACCOUNT_OUT = {
    "instagram.account.list_saved_accounts": (
        "logs the account out: the only screen that lists every saved account is the logged-out "
        "account picker, and the phone is left on it"
    ),
}


#: What this host puts in every payload itself, the serial, under the two names the launchers read: an
#: explicit `--param` of the same name wins, so they are no unknown keys.
HOST_PAYLOAD_KEYS = ("deviceId", "device_id")


def _refuse_undeclared_settings(workflow_id: str, params: dict[str, Any]) -> None:
    """Exit with code 2, every key named, when `params` holds a key the declaration of `workflow_id`
    does not read. An id no declaration serves is left to the registry, which says it is unknown."""
    if workflow_id not in contracts_by_id():
        return
    undeclared = undeclared_settings(workflow_id, params, HOST_PAYLOAD_KEYS)
    if not undeclared:
        return
    console.print(f"[red]Not run:[/red] {len(undeclared)} key(s) {workflow_id} does not read.")
    for item in undeclared:
        console.print(f"  {item.sentence(workflow_id)}")
    raise SystemExit(2)


def _warn_if_it_logs_out(workflow_id: str) -> bool:
    """Say that `workflow_id` logs the account out; True when it does."""
    effect = LOGS_THE_ACCOUNT_OUT.get(workflow_id)
    if effect is not None:
        console.print(f"[yellow]Warning:[/yellow] {workflow_id} {effect}.")
    return effect is not None


def _confirmed(workflow_id: str, yes: bool, scripted: bool) -> bool:
    """Warn about a workflow that logs the account out; True once the operator agreed."""
    if not _warn_if_it_logs_out(workflow_id):
        return True
    if yes:
        return True
    if not is_interactive(scripted=scripted):
        console.print("[red]Not run:[/red] pass --yes to run it without a question.")
        return False
    return Confirm.ask("Run it?", default=False)


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
@click.option("--yes", "-y", is_flag=True, help="Run a workflow that logs the account out without asking.")
def run_workflow(workflow_id: str, device_id: str | None, params: tuple[str, ...],
                 json_blob: str | None, dry_run: bool, yes: bool) -> None:
    """Run WORKFLOW_ID through the Agent registry."""
    from taktik.core.kernel.contracts import WorkflowInvocation

    resolved_params = _parse_params(params, json_blob)
    _refuse_undeclared_settings(workflow_id, resolved_params)

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
        if asks_for_ai(workflow_id, resolved_params):
            credential = resolve_cli_credential()
            found = f"{credential.provider} key found" if credential else "no AI key found"
            console.print(f"[cyan]AI:[/cyan] this run uses AI, {found}")
        if _warn_if_it_logs_out(workflow_id):
            console.print("A run asks first, or takes --yes.")
        return

    if not _confirmed(workflow_id, yes, scripted=json_blob is not None):
        raise SystemExit(1)

    try:
        ensure_ai_key(workflow_id, resolved_params,
                      interactive=is_interactive(scripted=json_blob is not None), echo=console.print)
    except MissingAIKeyError as exc:
        exit_without_key(exc, console)

    # The phone is chosen, not connected: the launcher connects it once it has read its payload.
    phone = _choose_phone(device_id)
    if phone is None:
        raise SystemExit(1)
    device_id = phone.device_id

    build = build_registry(device_manager=phone.device_manager, device_id=device_id)

    try:
        handler = build.registry.resolve(workflow_id)
    except KeyError:
        _unknown_workflow(build, workflow_id)
        raise SystemExit(1)

    platform = workflow_id.split(".", 1)[0]
    invocation = WorkflowInvocation(platform=platform, workflow_id=workflow_id, params=resolved_params)

    # The serial belongs in the payload, the way the bridges send it: several handlers read
    # `deviceId` from there to build their own device startup, and without it they fall back to
    # a placeholder and connect to nothing. An explicit --param wins over what we inject.
    payload = {**{key: device_id for key in HOST_PAYLOAD_KEYS}, **dict(resolved_params)}

    console.print(f"[blue]Running[/blue] [bold]{workflow_id}[/bold] on [cyan]{device_id}[/cyan]")
    try:
        # A launcher that takes the connected device, not a `connect`, gets it now and reads after.
        handler = handler_on_phone(build, workflow_id, phone)
        result = handler(invocation, payload)
    except PhoneNotConnectedError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1)
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


def _choose_phone(device_id: str | None) -> CliPhone | None:
    """The phone `device_id` names, or the only one adb lists, not connected yet; None (said) when
    adb lists none, or several and none was named."""
    from taktik.core.shared.device.manager import DeviceManager

    manager = DeviceManager()
    devices = manager.list_devices()
    if not devices:
        console.print("[red]No device connected.[/red]")
        return None

    if not device_id:
        if len(devices) > 1:
            console.print("[red]Several devices connected; pass --device <serial>.[/red]")
            for device in devices:
                console.print(f"  {device['id']} ({device['status']})")
            return None
        device_id = devices[0]["id"]

    return CliPhone(manager, device_id)


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
