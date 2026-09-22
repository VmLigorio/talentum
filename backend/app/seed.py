import argparse
from getpass import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.database import SessionLocal
from app.models import ClientPermission, ClientProfile, User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cria um usuário inicial do Talentum")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument(
        "--role",
        choices=("admin", "advisor", "client"),
        default="admin",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    email = args.email.strip().lower()
    password = getpass("Senha (não será exibida): ")
    confirmation = getpass("Confirme a senha: ")

    if len(password) < 8:
        raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")
    if password != confirmation:
        raise SystemExit("As senhas não conferem.")

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)) is not None:
            raise SystemExit("Já existe um usuário com este e-mail.")

        user = User(
            name=args.name.strip(),
            email=email,
            password_hash=hash_password(password),
            role=args.role,
        )
        db.add(user)
        db.flush()
        if args.role == "client":
            db.add(ClientProfile(user_id=user.id))
            db.add(ClientPermission(client_id=user.id))
        db.commit()

    print(f"Usuário {email} criado com o papel {args.role}.")


if __name__ == "__main__":
    main()
