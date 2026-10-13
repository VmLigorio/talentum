# Talentum — backend/app/reset_password.py
# Responsabilidade: Redefine uma senha localmente e revoga as sessões da conta.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
import argparse
from datetime import datetime, timezone
from getpass import getpass

from sqlalchemy import select, update

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import User, UserSession


def parse_args() -> argparse.Namespace:
    """Lê o e-mail da conta cuja senha será redefinida."""
    parser = argparse.ArgumentParser(description="Redefine a senha de um usuário Talentum")
    parser.add_argument("--email", required=True)
    return parser.parse_args()


def main() -> None:
    """Redefine a senha e revoga as sessões existentes da conta."""
    args = parse_args()
    email = args.email.strip().lower()
    password = getpass("Nova senha (não será exibida): ")
    confirmation = getpass("Confirme a nova senha: ")

    if len(password) < 8:  # O CLI não impõe o máximo de 128 aceito pela API (achado 133).
        raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")
    if password != confirmation:
        raise SystemExit("As senhas não conferem.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit("Nenhum usuário encontrado com este e-mail.")

        user.password_hash = hash_password(password)
        # A troca local invalida tokens, mas não cria evento no histórico de auditoria.
        user.session_version += 1
        db.execute(
            update(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        db.commit()

    print(f"Senha redefinida para {email}.")


if __name__ == "__main__":
    main()
