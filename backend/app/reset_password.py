import argparse
from datetime import datetime, timezone
from getpass import getpass

from sqlalchemy import select, update

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import User, UserSession


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Redefine a senha de um usuário Talentum")
    parser.add_argument("--email", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    email = args.email.strip().lower()
    password = getpass("Nova senha (não será exibida): ")
    confirmation = getpass("Confirme a nova senha: ")

    if len(password) < 8:
        raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")
    if password != confirmation:
        raise SystemExit("As senhas não conferem.")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise SystemExit("Nenhum usuário encontrado com este e-mail.")

        user.password_hash = hash_password(password)
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
