"""ORM pilot (Vague D) - SQLAlchemy mapping over the shared SQLite base.

Mirror of the front TypeORM pilot. The ORM only MAPS existing tables; it never
creates/alters the schema (the schema is owned by the physical migrations -
front ``migrations.ts`` + bot ``schemas/``/``migrations``). On a shared
dual-runtime base, two ORMs must never fight over the schema.
"""
