"""
V3 Milestone 2 Phase 1: Alembic environment.

Two deliberate departures from the generated template, both so this
migration setup needs zero per-environment editing:

1. `target_metadata` is the application's own `Base.metadata` (see
   app/db/database.py and app/db/models.py), imported here rather than
   left as the template's `None` -- this is what lets
   `alembic revision --autogenerate` compare the migration history
   against the actual current models, and what tests in
   tests/test_migrations.py compare a freshly-migrated schema against.

2. The database URL is read from `app.core.config.settings.database_url`
   -- the exact same setting (and therefore the exact same
   DATABASE_URL environment variable / .env file) the running
   application itself uses -- instead of a separate, hardcoded
   `sqlalchemy.url` in alembic.ini. A migration run always targets
   whatever database the app is currently configured for: SQLite for
   local dev/tests by default, or PostgreSQL wherever DATABASE_URL
   points at one. There is exactly one place that decides which
   database this project talks to.
"""

from logging.config import fileConfig

from alembic import context

# Importing app.db.models (even though nothing below references it by
# name) is required, not incidental -- it's what populates
# Base.metadata with every table before target_metadata is read.
# Without this import, an app that hadn't already imported its models
# elsewhere in the process would autogenerate/apply against an empty
# metadata object.
from app.core.config import settings
from app.db import models  # noqa: F401  (see comment above)
from app.db.database import Base, build_engine, is_sqlite_url

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging -- but ONLY when this
# env.py is being driven by an actual `alembic` CLI invocation
# (`config.cmd_opts` is set by alembic's own CLI entrypoint, and stays
# None for a Config() built and passed to command.upgrade()/stamp()/etc.
# programmatically -- see app/db/migration_bootstrap.py, which is how
# this project runs migrations at app startup and in every test).
#
# This matters because `fileConfig` doesn't just add handlers, it
# *replaces* whatever handlers are already attached to every logger
# named in this ini's [loggers] section (root included), regardless of
# `disable_existing_loggers`. migration_bootstrap.run_startup_migrations
# runs at every app startup -- i.e. every time the test suite imports
# app.main -- so an unconditional fileConfig call here would reset the
# root logger's handlers out from under whatever the host process
# (uvicorn, or pytest's `caplog` fixture) had already configured,
# silently breaking log capture for anything that happens afterward.
# Restricting this to real CLI runs (`alembic revision`, `alembic
# upgrade head` typed at a terminal) keeps that nice formatted output
# there, without the programmatic path -- the one this app actually
# depends on at runtime -- ever touching logging configuration it
# doesn't own.
if config.config_file_name is not None and config.cmd_opts is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# The URL migrations run against -- always the application's own
# current DATABASE_URL, never alembic.ini's placeholder value (see
# that file's comment on its own sqlalchemy.url line).
_DATABASE_URL = settings.database_url


def run_migrations_offline() -> None:
    """
    Emit migrations as SQL text without a live database connection
    (`alembic upgrade head --sql`). Not part of this project's normal
    dev/test workflow (both of those run online, below), but kept
    working -- unchanged from the generated template except for
    reading `_DATABASE_URL` -- since it's a standard Alembic escape
    hatch for reviewing exactly what SQL a migration would run before
    it's applied to a real database, useful once PostgreSQL is a
    shared/production target in later phases.
    """
    context.configure(
        url=_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite_url(_DATABASE_URL),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live connection. Uses `build_engine` (the
    same dialect-aware engine construction the application itself uses
    -- see app/db/database.py) rather than `engine_from_config`, so a
    migration run and the running app never risk diverging in how they
    each talk to the same database.

    `render_as_batch` is enabled for SQLite only. SQLite can't run most
    `ALTER TABLE` statements directly (adding/dropping/altering a
    column, changing a constraint) -- Alembic's "batch" mode works
    around this by rebuilding the table under the hood (new table,
    copy rows, swap names) instead of emitting an ALTER SQLite can't
    execute. PostgreSQL supports real ALTER TABLE natively, so batch
    mode is left off there -- migrations apply directly and don't pay
    the cost of a rebuild for a change that doesn't need one.
    """
    connectable = build_engine(_DATABASE_URL)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite_url(_DATABASE_URL),
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
