"""The database a CLI run writes to, said on stderr before anything uses it."""
import os

import click

from taktik.core.database import configure_db_service
from taktik.core.database.local.versions.opening import (
    UPGRADE_CONSENT_ENV,
    SchemaNotReady,
    SchemaUpgradeNeedsConsent,
)
from taktik.cli.support import language

_HELP_REQUESTED = "taktik.cli.help_requested"


class OpensNoDatabaseForHelp(click.Group):
    """A group that remembers `--help` is on its command line.

    A group's callback runs before its sub-command reads its own arguments, so `taktik device --help`
    reached `open_database()`: a text to print is no reason to open a base, or to refuse one.
    """

    def parse_args(self, ctx, args):
        if "--help" in args:
            ctx.meta[_HELP_REQUESTED] = True
        return super().parse_args(ctx, args)


def open_database():
    """Configure the database and say which file it is, on stderr: stdout stays a script's."""
    context = click.get_current_context(silent=True)
    if context is not None and context.meta.get(_HELP_REQUESTED):
        return
    current_translations = language.current_translations
    try:
        path = configure_db_service().local_db.db_path
    except SchemaUpgradeNeedsConsent as refusal:
        raise click.ClickException(current_translations['database_upgrade_needs_consent'].format(
            path=refusal.db_path, current=refusal.user_version, target=refusal.target_version,
            consent_env=UPGRADE_CONSENT_ENV)) from refusal
    except SchemaNotReady as refusal:
        raise click.ClickException(str(refusal)) from refusal
    click.echo(current_translations['database_in_use'].format(path), err=True)
    if not os.environ.get('TAKTIK_DB_PATH'):
        click.echo(current_translations['database_is_app_default'], err=True)
