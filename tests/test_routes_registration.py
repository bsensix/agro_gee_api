from fastapi.testclient import TestClient

from agro_gee_api.main import app


def test_domain_ping_routes_are_registered() -> None:
    client = TestClient(app)

    for path in ("/auth/ping", "/gee/ping", "/analytics/ping", "/whatsapp/ping"):
        response = client.get(path)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
