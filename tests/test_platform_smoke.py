import json
import os
from urllib.request import urlopen

import pytest


pytestmark = pytest.mark.integration


def test_api_healthcheck_on_exposed_port() -> None:
    api_port = int(os.getenv("API_PORT", "8000"))
    with urlopen(f"http://127.0.0.1:{api_port}/health", timeout=3) as response:
        assert response.status == 200
        assert json.loads(response.read().decode("utf-8")) == {"status": "ok"}
