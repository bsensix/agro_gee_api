import json
import os
import time
from http.client import RemoteDisconnected
from urllib.error import URLError
from urllib.request import urlopen

import pytest


pytestmark = pytest.mark.integration


def test_api_healthcheck_on_exposed_port() -> None:
    api_port = int(os.getenv("API_PORT", "8000"))
    deadline = time.monotonic() + 30
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{api_port}/health", timeout=3) as response:
                assert response.status == 200
                assert json.loads(response.read().decode("utf-8")) == {"status": "ok"}
                return
        except (
            URLError,
            ConnectionResetError,
            RemoteDisconnected,
            TimeoutError,
            OSError,
        ) as exc:
            last_error = exc
            time.sleep(1)

    raise AssertionError(
        f"API healthcheck did not become ready within 30s: {last_error}"
    )
