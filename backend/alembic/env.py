# Talentum — backend/alembic/env.py
# Responsabilidade: Controla a evolução versionada do esquema do banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.database import Base
from app.models import User  # noqa: F401 - registers models in metadata


config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Escapa percentuais porque o ConfigParser do Alembic interpreta `%` como interpolação.
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
# Permite ao Alembic comparar os modelos registrados com o esquema do banco ao gerar revisões.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Gera instruções de migração sem abrir uma conexão com o banco."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Executa migrações usando uma conexão ativa configurada pelo Alembic."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # O comando de migração usa conexões pontuais, sem manter pool entre execuções.
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
