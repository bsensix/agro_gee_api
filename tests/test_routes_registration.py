from fastapi.testclient import TestClient

from agro_gee_api.main import app


def _openapi_operations(client: TestClient) -> dict[tuple[str, str], dict[str, object]]:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json().get("paths", {})

    operations: dict[tuple[str, str], dict[str, object]] = {}
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, operation in methods.items():
            if not isinstance(operation, dict):
                continue
            operations[(path, method.upper())] = operation
    return operations


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


def test_gee_openapi_operations_have_expected_single_tags() -> None:
    client = TestClient(app)
    operations = _openapi_operations(client)

    expected_tags_by_operation = {
        ("/gee/ping", "GET"): "gee-core",
        ("/gee/auth/test", "POST"): "gee-core",
        ("/gee/datasets", "GET"): "gee-core",
        ("/gee/sentinel2/extract/point", "POST"): "sentinel2",
        ("/gee/sentinel2/extract/polygon", "POST"): "sentinel2",
        ("/gee/era5-land/extract/point", "POST"): "era5-land",
        ("/gee/era5-land/extract/polygon", "POST"): "era5-land",
        ("/gee/datasets/era5-land/variables", "GET"): "era5-land",
        ("/gee/ifs-forecast/extract/point", "POST"): "ifs-forecast",
        ("/gee/ifs-forecast/extract/polygon", "POST"): "ifs-forecast",
        ("/gee/datasets/ifs-forecast/variables", "GET"): "ifs-forecast",
    }

    for operation_key, expected_tag in expected_tags_by_operation.items():
        operation = operations[operation_key]
        assert operation.get("tags") == [expected_tag]


def test_all_gee_operations_use_single_allowed_non_generic_tag() -> None:
    client = TestClient(app)
    operations = _openapi_operations(client)

    allowed_gee_tags = {"gee-core", "sentinel2", "era5-land", "ifs-forecast"}
    gee_operations = {
        op_key: op for op_key, op in operations.items() if op_key[0].startswith("/gee")
    }

    assert gee_operations

    for operation in gee_operations.values():
        tags = operation.get("tags")
        assert isinstance(tags, list)
        assert len(tags) == 1
        assert tags[0] in allowed_gee_tags
        assert tags[0] != "gee"


def test_openapi_global_tag_metadata_order_and_descriptions() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200

    expected_tag_names = [
        "auth",
        "analytics",
        "gee-core",
        "sentinel2",
        "era5-land",
        "ifs-forecast",
    ]

    schema_tags = response.json().get("tags", [])
    assert [tag.get("name") for tag in schema_tags] == expected_tag_names
    assert all(
        isinstance(tag.get("description"), str) and tag.get("description", "").strip()
        for tag in schema_tags
    )
