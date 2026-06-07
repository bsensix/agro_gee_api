import json
import os
import subprocess
from urllib.request import urlopen

import pytest


pytestmark = pytest.mark.integration


def test_api_healthcheck_on_exposed_port() -> None:
    api_port = int(os.getenv("API_PORT", "8000"))
    with urlopen(f"http://127.0.0.1:{api_port}/health", timeout=3) as response:
        assert response.status == 200
        assert json.loads(response.read().decode("utf-8")) == {"status": "ok"}


def test_postgres_ready_inside_compose() -> None:
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_name = os.getenv("POSTGRES_DB", "agro_insight")

    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "pg_isready",
            "-U",
            db_user,
            "-d",
            db_name,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
