from fastapi.testclient import TestClient

from agro_gee_api.main import app


def test_domain_ping_routes_are_registered() -> None:
    client = TestClient(app)

    for path in ("/auth/ping", "/gee/ping", "/analytics/ping"):
        response = client.get(path)

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_removed_core_domains_return_404() -> None:
    client = TestClient(app)

    for path in ("/users", "/farms", "/fields", "/whatsapp/ping"):
        response = client.get(path)
        assert response.status_code == 404


def test_openapi_does_not_expose_removed_core_domains() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json().get("paths", {})

    for prefix in ("/users", "/farms", "/fields", "/whatsapp"):
        assert not any(
            path == prefix or path.startswith(f"{prefix}/") for path in paths
        )
