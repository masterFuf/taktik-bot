"""The database a CLI run writes to, said on stderr before anything uses it."""
import os

import click

from taktik.core.database import configure_db_service
from taktik.cli.support import language


def open_database():
    """Configure the database and say which file it is, on stderr: stdout stays a script's."""
    current_translations = language.current_translations
    path = configure_db_service().local_db.db_path
    click.echo(current_translations['database_in_use'].format(path), err=True)
    if not os.environ.get('TAKTIK_DB_PATH'):
        click.echo(current_translations['database_is_app_default'], err=True)
