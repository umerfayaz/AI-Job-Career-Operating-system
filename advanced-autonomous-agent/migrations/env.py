import os
import sys
from logging.config import fileConfig

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from backend.postgreSQL.engine import Base
from backend.postgreSQL import models
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from dotenv import load_dotenv


config = context.config
load_dotenv()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url():
    database_url = os.getenv("ALEMBIC_DATABASE_URL") or os.getenv("POSTGRES_URL")

    if not database_url:
        raise RuntimeError("Missing database url for alembic")

    
    return database_url.replace("+asyncpg", "+psycopg2")

def run_migrations_offline() -> None:
    
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
        config.set_main_option("sqlalchemy.url", get_database_url())

        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
