# Talentum — backend/tests/test_report_schema.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.report import ReportCreate


def test_report_period_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        ReportCreate(
            title="Relatório mensal",
            period_start=date(2026, 9, 30),
            period_end=date(2026, 9, 1),
            summary="Resumo",
        )
