"""Instagram publishing from the terminal, on the production path.

These commands, and the interactive menu's "Post Content" / "Post Story", call
`InstagramPostWorkflow`, the workflow the publish bridge runs, so the CLI and the desktop publish
through the same code. It is the only publishing engine: the older `ContentWorkflow` and its
`management content post|post-bulk|story` commands are gone. That engine had drifted (its
`post-bulk` published N separate posts, not a carousel; no reels; none of the production fixes on
slide order and on reclaiming pushed media).
"""
from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


def _resolve_device(device_id: str | None):
    """Connect to `device_id`, or to the only connected device. Returns (device, device_id)."""
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

    return manager.device, device_id


def _run(post_type: str, device_id: str | None, media: tuple[str, ...], caption: str,
         hashtags: str, story_via_feed: bool = False, rehearse: bool = False) -> None:
    from taktik.core.social_media.instagram.workflows.publish.post_workflow import (
        InstagramPostWorkflow,
    )

    paths = [str(Path(p)) for p in media]
    missing = [p for p in paths if not Path(p).is_file()]
    if missing:
        console.print(f"[red]File not found:[/red] {', '.join(missing)}")
        raise SystemExit(1)

    device, device_id = _resolve_device(device_id)
    if device is None:
        raise SystemExit(1)

    tags = [t.strip().lstrip("#") for t in hashtags.split()] if hashtags else []

    def _log(level: str, message: str) -> None:
        colour = {"error": "red", "warning": "yellow"}.get(level, "dim")
        console.print(f"[{colour}]{message}[/{colour}]")

    def _status(status: str, message: str = "") -> None:
        console.print(f"[blue]{status}[/blue] {message}")

    workflow = InstagramPostWorkflow(
        device,
        device_id,
        log=_log,
        status=_status,
        post_type=post_type,
        story_via_feed=story_via_feed,
    )

    result = workflow.execute(
        caption=caption or "",
        hashtags=tags,
        media_paths=paths,
        stop_before_share=rehearse,
    )

    if result.get("success"):
        console.print(Panel.fit(f"[bold green]{result.get('message', 'Published')}[/bold green]",
                                border_style="green"))
        return

    console.print(Panel.fit(
        f"[bold red]{result.get('message', 'Failed')}[/bold red]\n"
        f"[cyan]error_type:[/cyan] {result.get('error_type')}",
        border_style="red",
    ))
    raise SystemExit(1)


def run_publish(post_type: str, device_id: str | None, media: tuple[str, ...], caption: str = "",
                hashtags: str = "", *, story_via_feed: bool = False) -> bool:
    """One publish from the interactive menu: the same run as the commands, reporting a failure
    instead of leaving the terminal."""
    try:
        _run(post_type, device_id, media, caption, hashtags, story_via_feed=story_via_feed)
    except SystemExit as exc:
        return exc.code in (0, None)
    return True


_DEVICE = click.option("--device", "-d", "device_id", help="ADB serial. Omitted: the only connected device.")
_CAPTION = click.option("--caption", "-c", default="", help="Caption text.")
_HASHTAGS = click.option("--hashtags", "-h", default="", help="Space-separated hashtags.")
_REHEARSE = click.option(
    "--rehearse", is_flag=True,
    help="Walk the whole flow and stop on the share screen WITHOUT publishing.",
)


@click.group("publish")
def publish() -> None:
    """Publish to Instagram through the same workflow the desktop app uses."""


@publish.command("post")
@click.argument("image", type=click.Path(exists=True))
@_DEVICE
@_CAPTION
@_HASHTAGS
@_REHEARSE
def publish_post(image, device_id, caption, hashtags, rehearse):
    """Publish a single photo."""
    _run("post", device_id, (image,), caption, hashtags, rehearse=rehearse)


@publish.command("carousel")
@click.argument("images", nargs=-1, required=True, type=click.Path(exists=True))
@_DEVICE
@_CAPTION
@_HASHTAGS
@_REHEARSE
def publish_carousel(images, device_id, caption, hashtags, rehearse):
    """Publish several photos as ONE carousel, in the order given."""
    if len(images) < 2:
        console.print("[red]A carousel needs at least two media.[/red] "
                      "For one, use [bold]publish post[/bold].")
        raise SystemExit(1)
    if len(images) > 10:
        console.print("[red]Instagram accepts at most 10 media in a carousel.[/red]")
        raise SystemExit(1)
    _run("carousel", device_id, images, caption, hashtags, rehearse=rehearse)


@publish.command("reel")
@click.argument("video", type=click.Path(exists=True))
@_DEVICE
@_CAPTION
@_HASHTAGS
@_REHEARSE
def publish_reel(video, device_id, caption, hashtags, rehearse):
    """Publish a video as a reel."""
    _run("reel", device_id, (video,), caption, hashtags, rehearse=rehearse)


@publish.command("story")
@click.argument("media", type=click.Path(exists=True))
@_DEVICE
@click.option("--via-feed", is_flag=True,
              help="Enter through the feed story tray instead of the create button.")
@_REHEARSE
def publish_story(media, device_id, via_feed, rehearse):
    """Publish a photo or video as a story."""
    _run("story", device_id, (media,), "", "", story_via_feed=via_feed, rehearse=rehearse)


__all__ = ["publish", "run_publish"]
