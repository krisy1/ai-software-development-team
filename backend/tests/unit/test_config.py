from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.config import DOCKER_SECRET_MAP, Settings


class TestDockerSecrets:
    def test_skipped_when_secrets_dir_does_not_exist(self):
        s = Settings(OPENAI_API_KEY="from-env")
        s._load_docker_secrets(Path("/nonexistent/secrets"))
        assert s.OPENAI_API_KEY == "from-env"

    def test_overrides_from_docker_secrets(self):
        with TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp)
            (secrets_dir / "openai_api_key").write_text("from-docker-secret")
            (secrets_dir / "secret_key").write_text("docker-secret-key-12345")

            s = Settings(OPENAI_API_KEY="from-env", SECRET_KEY="from-env-key")
            s._load_docker_secrets(secrets_dir)

            assert s.OPENAI_API_KEY == "from-docker-secret"
            assert s.SECRET_KEY == "docker-secret-key-12345"

    def test_secret_file_with_trailing_whitespace_is_stripped(self):
        with TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp)
            (secrets_dir / "api_key").write_text("  my-api-key\n  ")

            s = Settings(API_KEY="old-key")
            s._load_docker_secrets(secrets_dir)

            assert s.API_KEY == "my-api-key"

    def test_non_secret_fields_unchanged(self):
        with TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp)
            (secrets_dir / "openai_api_key").write_text("secret-key")

            s = Settings(OPENAI_API_KEY="from-env", APP_NAME="MyApp")
            s._load_docker_secrets(secrets_dir)

            assert s.APP_NAME == "MyApp"

    def test_all_secret_keys_covered_in_map(self):
        """Every key in DOCKER_SECRET_MAP maps to a real Settings field."""
        s = Settings()
        for field_name in DOCKER_SECRET_MAP.values():
            assert hasattr(s, field_name), f"{field_name} missing from Settings"

    def test_model_post_init_calls_load_docker_secrets(self, monkeypatch):
        called = False

        def mock_load(self, secrets_dir=None):
            nonlocal called
            called = True

        monkeypatch.setattr(Settings, "_load_docker_secrets", mock_load)
        Settings()
        assert called


class TestSettingsDirect:
    def test_default_environment_is_development(self):
        s = Settings()
        assert s.ENVIRONMENT == "development"

    def test_cors_origins_list_property(self):
        s = Settings(CORS_ORIGINS='["http://localhost:3000"]')
        assert s.cors_origins_list == ["http://localhost:3000"]

    def test_chroma_url_property(self):
        s = Settings(CHROMA_HOST="my-chroma", CHROMA_PORT=9999)
        assert s.chroma_url == "http://my-chroma:9999"
