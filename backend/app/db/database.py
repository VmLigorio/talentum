# Talentum — backend/app/db/database.py
# Responsabilidade: Configura a conexão com o banco e os recursos compartilhados pelo SQLAlchemy.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarativa comum para os modelos SQLAlchemy da aplicação."""

    pass


settings = get_settings()
# Compartilha o engine no processo e testa conexões ociosas ao retirá-las do pool.
# Oculta valores vinculados nas mensagens e tracebacks de falhas SQLAlchemy.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    hide_parameters=True,
)
# A sessão não confirma transações automaticamente nem faz autoflush antes de consultas.
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Fornece uma sessão do banco e garante seu fechamento ao final."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
