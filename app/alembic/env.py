from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel

from app import config as app_config

# Importing the models module is the whole point of this import: it is what
# registers Phrase/User/UserPreference/Attempt on SQLModel.metadata. Without it
# autogenerate diffs the live database against *empty* metadata and cheerfully
# writes a migration that drops every table.
from app import models  # noqa: F401

config = context.config

# The test suite runs `alembic upgrade head` in-process and does not want
# fileConfig() tearing down pytest's own logging handlers; it sets this False.
if config.config_file_name is not None and config.attributes.get(
    "configure_logger", True
):
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def _url() -> str:
    """`-x url=...` for a one-off target, otherwise the app's own config."""
    x_args = context.get_x_argument(as_dictionary=True)
    return x_args.get("url") or app_config.DATABASE_URL


def run_migrations_offline() -> None:
    """Emit the migrations as SQL rather than running them (`--sql`)."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # create_engine() directly, rather than engine_from_config() plus a
    # set_main_option() round-trip: alembic.ini is read by ConfigParser, which
    # treats '%' as interpolation syntax, so a password containing one would be
    # silently mangled or raise.
    connectable = create_engine(_url(), poolclass=pool.NullPool)
    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
                compare_server_default=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
