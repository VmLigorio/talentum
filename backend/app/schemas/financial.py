# Talentum — backend/app/schemas/financial.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FinancialProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: int
    monthly_income: Decimal
    monthly_expenses: Decimal
    risk_profile: str | None
    updated_at: datetime


class FinancialProfileUpdate(BaseModel):
    monthly_income: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    monthly_expenses: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    risk_profile: str | None = Field(default=None, max_length=30)


class PatrimonyItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    category: str
    description: str
    institution: str | None
    value: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PatrimonyItemCreate(BaseModel):
    category: str = Field(min_length=2, max_length=40)
    description: str = Field(min_length=2, max_length=160)
    institution: str | None = Field(default=None, max_length=120)
    value: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)


class PatrimonyItemUpdate(BaseModel):
    category: str | None = Field(default=None, min_length=2, max_length=40)
    description: str | None = Field(default=None, min_length=2, max_length=160)
    institution: str | None = Field(default=None, max_length=120)
    value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=500)


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    title: str
    target_value: Decimal
    current_value: Decimal
    target_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class GoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    target_value: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    current_value: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    target_date: date | None = None


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    target_value: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    current_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    target_date: date | None = None
    status: str | None = Field(default=None, pattern="^(active|completed|paused)$")
