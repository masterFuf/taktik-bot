import sys

# Windows consoles default to cp1252 while the banner, the menus and the workflow labels use
# box-drawing characters and emoji. Attached to a terminal that is fine, but as soon as stdout is
# redirected — a log file, a pipe, a scheduled run — encoding raised before a single line was
# printed. Standalone use is precisely those cases, so make the stream tolerant instead.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - stream already detached
            pass

import click
import logging

from taktik.cli.commands.instagram.management import management
from taktik.cli.menus.main_menu import run_main_menu
from taktik.cli.support.banner import display_banner
from taktik.cli.support.database import open_database
from taktik.cli.support.language import select_language, set_language

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group(invoke_without_command=True)
@click.option('--lang', '-l', type=click.Choice(['fr', 'en']), help='Language (fr/en)')
@click.pass_context
def cli(ctx, lang=None):
    # Only ask when we are about to show the interactive menu. Asking first made every
    # sub-command block on a prompt, which is fine at a keyboard and fatal in a script or a
    # cron job — the standalone use the bot is supposed to support.
    if not lang:
        lang = select_language() if ctx.invoked_subcommand is None else 'en'

    set_language(lang)
    
    open_database()
    
    if ctx.invoked_subcommand is None:
        display_banner()
        run_main_menu()


# Registry-driven access to every workflow that has a runnable handler, including the platforms
# that never got a menu branch (TikTok, Threads, Gmail, YouTube). Registered as a group rather
# than woven into the interactive menu so a new platform needs no edit here.
from taktik.cli.commands.workflows import workflows as _workflows_group

cli.add_command(_workflows_group)

# Instagram publishing, on the workflow the desktop's publish bridge runs.
from taktik.cli.commands.instagram.publish import publish as _publish_group

cli.add_command(_publish_group)

# The autonomous Agent, previously reachable only through its desktop bridge.
from taktik.cli.commands.instagram.agent import agent as _agent_group

cli.add_command(_agent_group)

# The phones, the Instagram automation, TikTok and `launch`. `taktik-tiktok` enters on `tiktok`
# (setup.py names `taktik.cli.main:tiktok`): the name stays here.
from taktik.cli.commands.device import device
from taktik.cli.commands.instagram.automation import automation
from taktik.cli.commands.tiktok import launch, tiktok

cli.add_command(device)
cli.add_command(automation)
cli.add_command(tiktok)
cli.add_command(launch)

# ==================== MANAGEMENT GROUP ====================
cli.add_command(management)

if __name__ == "__main__":
    cli()
