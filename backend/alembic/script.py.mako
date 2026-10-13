"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

# Fornece as operações de esquema e os tipos usados pelo código da revisão gerada.
from alembic import op
import sqlalchemy as sa


# Identificador e dependências que determinam a ordem desta revisão no histórico.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


# Aplica as alterações para avançar o esquema até esta revisão.
def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


# Reverte as alterações desta revisão ao voltar para a revisão anterior.
def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
