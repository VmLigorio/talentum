# Talentum — backend/app/models/report.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Report(Base):
    """Relatório patrimonial gerado e armazenado para consulta posterior."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Vincula o registro ao cliente e define o tema e o período coberto.
    client_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Separa rascunho de conteúdo publicado e registra a primeira publicação.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default=text("'draft'")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
