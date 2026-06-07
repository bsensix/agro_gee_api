from fastapi.testclient import TestClient
import psycopg

from agro_gee_api.main import app
from agro_gee_api import db


def test_db_config_uses_default_connect_timeout(monkeypatch: object) -> None:
    monkeypatch.delenv("POSTGRES_CONNECT_TIMEOUT", raising=False)

    config = db._db_config()

    assert config["connect_timeout"] == 5


def test_db_config_uses_env_connect_timeout(monkeypatch: object) -> None:
    monkeypatch.setenv("POSTGRES_CONNECT_TIMEOUT", "9")

    config = db._db_config()

    assert config["connect_timeout"] == 9


def test_operational_connection_error_returns_503(monkeypatch: object) -> None:
    def _raise_operational_error(*args: object, **kwargs: object) -> None:
        raise psycopg.OperationalError("database unavailable")

    monkeypatch.setattr(db.psycopg, "connect", _raise_operational_error)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/users")

    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
