from app.config import Settings


def test_allowed_origins_accepts_comma_separated_env(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:3000,https://demo.example")

    settings = Settings(_env_file=None)

    assert settings.allowed_origins == ["http://localhost:3000", "https://demo.example"]
