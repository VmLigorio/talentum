# Talentum — backend/tests/test_reset_password.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.reset_password import parse_args


def test_reset_password_requires_email(monkeypatch) -> None:
    """Verifica que a ferramenta de redefinição exige o e-mail como argumento."""
    monkeypatch.setattr("sys.argv", ["reset-password", "--email", "ADMIN@TALENTUM.LOCAL"])

    args = parse_args()

    assert args.email == "ADMIN@TALENTUM.LOCAL"
