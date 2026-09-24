# Talentum — backend/tests/test_seed.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.seed import parse_args


def test_seed_supports_expected_roles(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["seed", "--name", "Admin", "--email", "admin@talentum.local", "--role", "admin"],
    )

    args = parse_args()

    assert args.role == "admin"
