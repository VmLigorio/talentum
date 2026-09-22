from app.reset_password import parse_args


def test_reset_password_requires_email(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["reset-password", "--email", "ADMIN@TALENTUM.LOCAL"])

    args = parse_args()

    assert args.email == "ADMIN@TALENTUM.LOCAL"
