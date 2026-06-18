from datetime import date

from fastapi.testclient import TestClient

from agro_gee_api.main import app
from agro_gee_api.routes._authz import AuthzContext, get_authz_context
from agro_gee_api.routes.gee import _is_gee_auth_test_enabled
from agro_gee_api.services.gee_client import GEEUnavailableError
from agro_gee_api.services.gee_client import GEEAuthError
from agro_gee_api.services.gee_sentinel2_extract import (
    ValidationError as ExtractValidationError,
)
from agro_gee_api.services.gee_sentinel1_extract import (
    GEEAuthFailedError as Sentinel1GEEAuthFailedError,
    GEETimeoutError as Sentinel1GEETimeoutError,
    ValidationError as Sentinel1ValidationError,
)
from agro_gee_api.services.gee_meteo_extract import (
    GEETimeoutError as MeteoGEETimeoutError,
    ValidationError as MeteoValidationError,
)


def _override_authz() -> AuthzContext:
    return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))


def _setup_auth_test_client(monkeypatch, authz_override) -> TestClient:
    app.dependency_overrides[get_authz_context] = authz_override
    monkeypatch.setenv("GEE_AUTH_TEST_ENABLED", "true")
    return TestClient(app)


def test_get_gee_datasets_returns_active_catalog(monkeypatch) -> None:
    class CatalogService:
        def list_datasets(self) -> list[object]:
            class Item:
                dataset_id = "COPERNICUS/S2_SR_HARMONIZED"
                provider = "gee"
                title = "Sentinel-2 SR Harmonized"
                bands = ["B2", "B3", "B4", "B8"]

            return [Item()]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_catalog_service", lambda: CatalogService()
    )
    client = TestClient(app)

    response = client.get("/gee/datasets")

    assert response.status_code == 200
    assert response.json() == [
        {
            "dataset_id": "COPERNICUS/S2_SR_HARMONIZED",
            "provider": "gee",
            "title": "Sentinel-2 SR Harmonized",
            "bands": ["B2", "B3", "B4", "B8"],
        }
    ]


def test_post_extract_point_returns_value(monkeypatch) -> None:
    class ExtractService:
        def extract_point(self, **_: object) -> float:
            return 0.41

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService()
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "COPERNICUS/S2_SR_HARMONIZED",
        "metric": "ndvi_mean",
        "value": 0.41,
        "series": [],
    }


def test_post_extract_point_returns_error_schema(monkeypatch) -> None:
    class ExtractService:
        def extract_point(self, **_: object) -> float:
            raise ExtractValidationError("INVALID_REQUEST", "Unsupported metric")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService()
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "foo_mean",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"
    assert "correlation_id" in response.json()


def test_post_extract_point_uses_runtime_client_factory_and_maps_auth_failed(
    monkeypatch,
) -> None:
    class AuthFailedClient:
        def extract_point(self, **_: object) -> float:
            raise GEEAuthError("GEE_AUTH_FAILED", "runtime auth failed")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: AuthFailedClient(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 500
    assert response.json()["error_code"] == "GEE_AUTH_FAILED"
    assert response.json()["message"] == "runtime auth failed"


def test_post_extract_polygon_uses_runtime_client_factory_and_maps_unavailable(
    monkeypatch,
) -> None:
    class UnavailableClient:
        def extract_polygon(self, **_: object) -> float:
            raise GEEUnavailableError(
                "GEE_UNAVAILABLE", "runtime unavailable", retryable=True
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: UnavailableClient(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 503
    assert response.json()["error_code"] == "GEE_UNAVAILABLE"
    assert response.json()["message"] == "runtime unavailable"
    assert response.json()["retryable"] is True


def test_post_extract_polygon_uses_runtime_client_factory_and_maps_auth_failed(
    monkeypatch,
) -> None:
    class AuthFailedClient:
        def extract_polygon(self, **_: object) -> float:
            raise GEEAuthError("GEE_AUTH_FAILED", "runtime auth failed polygon")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_gee_client",
        lambda: AuthFailedClient(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 500
    assert response.json()["error_code"] == "GEE_AUTH_FAILED"
    assert response.json()["message"] == "runtime auth failed polygon"


def test_post_extract_polygon_returns_value(monkeypatch) -> None:
    class ExtractService:
        def extract_polygon(self, **_: object) -> float:
            return 0.53

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService()
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.53


def test_post_extract_point_includes_daily_series_with_cloud_pct(monkeypatch) -> None:
    class ExtractService:
        def extract_point(self, **_: object) -> float:
            return 0.99

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            return [
                {"date": "2026-06-01", "value": 0.30, "cloud_pct": 10.0},
                {"date": "2026-06-02", "value": 0.50, "cloud_pct": 20.0},
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService()
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel2/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.4
    assert response.json()["series"] == [
        {"date": "2026-06-01", "value": 0.3, "cloud_pct": 10.0},
        {"date": "2026-06-02", "value": 0.5, "cloud_pct": 20.0},
    ]


SENTINEL1_VALID_POINT_PAYLOAD = {
    "coordinates": [-47.0, -15.0],
    "date_start": "2026-06-01",
    "date_end": "2026-06-10",
    "metric": "vv_mean",
}

SENTINEL1_VALID_POLYGON_PAYLOAD = {
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
        ],
    },
    "date_start": "2026-06-01",
    "date_end": "2026-06-10",
    "metric": "vv_mean",
}


def test_post_sentinel1_extract_point_returns_extract_contract(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_point(self, **kwargs: object) -> float:
            assert kwargs["geometry_geojson"] == {
                "type": "Point",
                "coordinates": [-47.0, -15.0],
            }
            assert kwargs["date_start"] == date(2026, 6, 1)
            assert kwargs["date_end"] == date(2026, 6, 10)
            assert kwargs["metric"] == "vv_mean"
            return 0.44

        def timeseries(self, **kwargs: object) -> list[dict[str, object]]:
            assert kwargs["geometry_geojson"] == {
                "type": "Point",
                "coordinates": [-47.0, -15.0],
            }
            assert kwargs["date_start"] == date(2026, 6, 1)
            assert kwargs["date_end"] == date(2026, 6, 10)
            assert kwargs["metric"] == "vv_mean"
            return [
                {"date": "2026-06-01", "value": 0.33, "cloud_pct": None},
                {"date": "2026-06-02", "value": 0.55, "cloud_pct": None},
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "COPERNICUS/S1_GRD",
        "metric": "vv_mean",
        "value": 0.44,
        "series": [
            {"date": "2026-06-01", "value": 0.33, "cloud_pct": None},
            {"date": "2026-06-02", "value": 0.55, "cloud_pct": None},
        ],
    }


def test_post_sentinel1_extract_polygon_returns_extract_contract(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **kwargs: object) -> float:
            assert kwargs["geometry_geojson"] == {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            }
            assert kwargs["date_start"] == date(2026, 6, 1)
            assert kwargs["date_end"] == date(2026, 6, 10)
            assert kwargs["metric"] == "vv_mean"
            return 0.62

        def timeseries(self, **kwargs: object) -> list[dict[str, object]]:
            assert kwargs["geometry_geojson"] == {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            }
            assert kwargs["date_start"] == date(2026, 6, 1)
            assert kwargs["date_end"] == date(2026, 6, 10)
            assert kwargs["metric"] == "vv_mean"
            return [
                {"date": "2026-06-01", "value": 0.61, "cloud_pct": None},
                {"date": "2026-06-02", "value": 0.63, "cloud_pct": None},
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "COPERNICUS/S1_GRD",
        "metric": "vv_mean",
        "value": 0.62,
        "series": [
            {"date": "2026-06-01", "value": 0.61, "cloud_pct": None},
            {"date": "2026-06-02", "value": 0.63, "cloud_pct": None},
        ],
    }


def test_post_sentinel1_extract_point_maps_unsupported_metric_to_invalid_request(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            raise Sentinel1ValidationError("INVALID_REQUEST", "Unsupported metric")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point",
        json={**SENTINEL1_VALID_POINT_PAYLOAD, "metric": "foo_mean"},
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error_code"] == "INVALID_REQUEST"
    assert "correlation_id" in body


def test_post_sentinel1_extract_point_maps_validation_error_code_directly(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            raise Sentinel1ValidationError(
                "AREA_LIMIT_EXCEEDED", "Area exceeds supported limit"
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 413
    assert body["error_code"] == "AREA_LIMIT_EXCEEDED"
    assert "correlation_id" in body


def test_post_sentinel1_extract_polygon_maps_no_imagery_unavailable_to_422(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            raise GEEUnavailableError(
                "NO_IMAGERY", "No imagery for date range", retryable=False
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 422
    assert body["error_code"] == "NO_IMAGERY"
    assert "correlation_id" in body


def test_post_sentinel1_extract_polygon_maps_unsupported_metric_to_invalid_request(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            raise Sentinel1ValidationError("INVALID_REQUEST", "Unsupported metric")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon",
        json={**SENTINEL1_VALID_POLYGON_PAYLOAD, "metric": "foo_mean"},
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error_code"] == "INVALID_REQUEST"
    assert "correlation_id" in body


def test_post_sentinel1_extract_point_maps_no_imagery_unavailable_to_422(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            raise GEEUnavailableError(
                "NO_IMAGERY", "No imagery for date range", retryable=False
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 422
    assert body["error_code"] == "NO_IMAGERY"
    assert "correlation_id" in body


def test_post_sentinel1_extract_point_rejects_invalid_coordinate_bounds(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        extract_called = False
        timeseries_called = False

        def extract_point(self, **_: object) -> float:
            self.extract_called = True
            return 0.0

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            self.timeseries_called = True
            return []

    service = Sentinel1Service()
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: service,
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point",
        json={**SENTINEL1_VALID_POINT_PAYLOAD, "coordinates": [-181.0, -15.0]},
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error_code"] == "INVALID_REQUEST"
    assert "correlation_id" in body
    assert service.extract_called is False
    assert service.timeseries_called is False


def test_post_sentinel1_extract_polygon_rejects_unclosed_ring(monkeypatch) -> None:
    class Sentinel1Service:
        extract_called = False
        timeseries_called = False

        def extract_polygon(self, **_: object) -> float:
            self.extract_called = True
            return 0.0

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            self.timeseries_called = True
            return []

    service = Sentinel1Service()
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: service,
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon",
        json={
            **SENTINEL1_VALID_POLYGON_PAYLOAD,
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.1, -15.1]]
                ],
            },
        },
    )
    body = response.json()

    assert response.status_code == 400
    assert body["error_code"] == "INVALID_REQUEST"
    assert "correlation_id" in body
    assert service.extract_called is False
    assert service.timeseries_called is False


def test_post_sentinel1_extract_point_maps_unavailable_to_503(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            raise GEEUnavailableError("GEE_UNAVAILABLE", "offline", retryable=True)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 503
    assert body["error_code"] == "GEE_UNAVAILABLE"
    assert body["message"] == "offline"
    assert body["retryable"] is True
    assert "correlation_id" in body


def test_post_sentinel1_extract_polygon_maps_unavailable_to_503(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            raise GEEUnavailableError(
                "GEE_UNAVAILABLE", "offline polygon", retryable=True
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 503
    assert body["error_code"] == "GEE_UNAVAILABLE"
    assert body["message"] == "offline polygon"
    assert body["retryable"] is True
    assert "correlation_id" in body


def test_post_sentinel1_extract_point_maps_timeout_to_504(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            raise Sentinel1GEETimeoutError(
                "GEE_TIMEOUT", "timeout point", retryable=True
            )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 504
    assert body["error_code"] == "GEE_TIMEOUT"
    assert body["message"] == "timeout point"
    assert body["retryable"] is True
    assert "correlation_id" in body


def test_post_sentinel1_extract_polygon_maps_timeout_to_504(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            raise Sentinel1GEETimeoutError("GEE_TIMEOUT", "timeout", retryable=True)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 504
    assert body["error_code"] == "GEE_TIMEOUT"
    assert body["message"] == "timeout"
    assert body["retryable"] is True
    assert "correlation_id" in body


def test_post_sentinel1_extract_point_maps_auth_failed_to_500(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            raise Sentinel1GEEAuthFailedError("GEE_AUTH_FAILED", "auth failed")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 500
    assert body["error_code"] == "GEE_AUTH_FAILED"
    assert body["message"] == "auth failed"
    assert body["retryable"] is False
    assert "correlation_id" in body


def test_post_sentinel1_extract_polygon_maps_auth_failed_to_500(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            raise Sentinel1GEEAuthFailedError("GEE_AUTH_FAILED", "auth failed polygon")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 500
    assert body["error_code"] == "GEE_AUTH_FAILED"
    assert body["message"] == "auth failed polygon"
    assert body["retryable"] is False
    assert "correlation_id" in body


def test_post_sentinel1_extract_polygon_maps_raw_auth_error_to_500(monkeypatch) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            raise GEEAuthError("GEE_AUTH_FAILED", "raw auth failed polygon")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 500
    assert body["error_code"] == "GEE_AUTH_FAILED"
    assert body["message"] == "raw auth failed polygon"
    assert body["retryable"] is False
    assert "correlation_id" in body


def test_post_sentinel1_extract_polygon_maps_raw_auth_error_from_timeseries_to_500(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            return 0.62

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            raise GEEAuthError("GEE_AUTH_FAILED", "raw auth failed timeseries")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )
    body = response.json()

    assert response.status_code == 500
    assert body["error_code"] == "GEE_AUTH_FAILED"
    assert body["message"] == "raw auth failed timeseries"
    assert body["retryable"] is False
    assert "correlation_id" in body


def test_post_sentinel1_extract_point_recomputes_value_from_numeric_series(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            return 0.91

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            return [
                {"date": "2026-06-01", "value": 0.40, "cloud_pct": None},
                {"date": "2026-06-02", "value": "ignored", "cloud_pct": None},
                {"date": "2026-06-03", "value": 0.80, "cloud_pct": None},
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.6


def test_post_sentinel1_extract_polygon_recomputes_value_from_numeric_series(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            return 0.95

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            return [
                {"date": "2026-06-01", "value": 0.40, "cloud_pct": None},
                {"date": "2026-06-02", "value": "ignored", "cloud_pct": None},
                {"date": "2026-06-03", "value": 0.80, "cloud_pct": None},
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.6


def test_post_sentinel1_extract_point_keeps_extracted_value_when_series_empty(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            return 0.72

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.72


def test_post_sentinel1_extract_polygon_keeps_extracted_value_when_series_empty(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_polygon(self, **_: object) -> float:
            return 0.67

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            return []

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/polygon", json={**SENTINEL1_VALID_POLYGON_PAYLOAD}
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.67


def test_post_sentinel1_extract_point_keeps_extracted_value_when_series_non_numeric(
    monkeypatch,
) -> None:
    class Sentinel1Service:
        def extract_point(self, **_: object) -> float:
            return 0.81

        def timeseries(self, **_: object) -> list[dict[str, object]]:
            return [
                {"date": "2026-06-01", "value": "n/a", "cloud_pct": None},
                {"date": "2026-06-02", "value": None, "cloud_pct": None},
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_sentinel1_extract_service",
        lambda: Sentinel1Service(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/sentinel1/extract/point", json={**SENTINEL1_VALID_POINT_PAYLOAD}
    )

    assert response.status_code == 200
    assert response.json()["value"] == 0.81


def test_removed_endpoints_return_404() -> None:
    client = TestClient(app)

    timeseries_response = client.post(
        "/gee/sentinel2/timeseries",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )
    image_response = client.post(
        "/gee/sentinel2/image",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )
    stats_response = client.post(
        "/gee/sentinel2/stats",
        headers={"X-User-Id": "1"},
        json={
            "field_id": 10,
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "metric": "ndvi_mean",
        },
    )

    assert timeseries_response.status_code == 404
    assert image_response.status_code == 404
    assert stats_response.status_code == 404


def test_post_auth_test_returns_200_payload(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))

    monkeypatch.setattr(
        "agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True
    )
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck", lambda: None, raising=False
    )
    client = _setup_auth_test_client(monkeypatch, _authz)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_auth_test_maps_auth_failed(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))

    def _raise_auth_failed() -> None:
        raise GEEAuthError("GEE_AUTH_FAILED", "Auth failed")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True
    )
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck",
        _raise_auth_failed,
        raising=False,
    )
    client = _setup_auth_test_client(monkeypatch, _authz)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 500
    assert response.json()["error_code"] == "GEE_AUTH_FAILED"


def test_post_auth_test_maps_runtime_auth_failed(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))

    def _raise_auth_failed(*, force_recheck: bool = False) -> None:
        assert force_recheck is True
        raise GEEAuthError("GEE_AUTH_FAILED", "Runtime auth failed")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True
    )
    monkeypatch.setattr(
        "agro_gee_api.routes.gee._GEE_RUNTIME.ensure_initialized",
        _raise_auth_failed,
        raising=False,
    )
    client = _setup_auth_test_client(monkeypatch, _authz)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 500
    assert response.json()["error_code"] == "GEE_AUTH_FAILED"


def test_post_auth_test_maps_unavailable(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))

    def _raise_unavailable() -> None:
        raise GEEUnavailableError("GEE_UNAVAILABLE", "offline", retryable=True)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True
    )
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck",
        _raise_unavailable,
        raising=False,
    )
    client = _setup_auth_test_client(monkeypatch, _authz)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 503
    assert response.json()["error_code"] == "GEE_UNAVAILABLE"
    assert response.json()["retryable"] is True


def test_post_auth_test_maps_internal_error(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))

    def _raise_internal() -> None:
        raise GEEUnavailableError("GEE_INTERNAL", "boom", retryable=False)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True
    )
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck", _raise_internal, raising=False
    )
    client = _setup_auth_test_client(monkeypatch, _authz)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 500
    assert response.json()["error_code"] == "GEE_INTERNAL"
    assert response.json()["retryable"] is False


def test_post_auth_test_returns_403_for_non_admin(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))

    client = _setup_auth_test_client(monkeypatch, _authz)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_SCOPE"


def test_post_auth_test_returns_200_for_internal_scope_user(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(
            requester_user_id=1,
            allowed_user_ids=(1,),
            requester_role="internal",
        )

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck", lambda: None, raising=False
    )
    client = _setup_auth_test_client(monkeypatch, _authz)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_auth_test_returns_404_when_feature_disabled(monkeypatch) -> None:
    def _authz() -> AuthzContext:
        return AuthzContext(requester_user_id=1, allowed_user_ids=(1,))

    app.dependency_overrides[get_authz_context] = _authz
    monkeypatch.setenv("GEE_AUTH_TEST_ENABLED", "false")
    client = TestClient(app)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 404


def test_post_auth_test_rejects_spoofed_admin_header(monkeypatch) -> None:
    app.dependency_overrides.pop(get_authz_context, None)
    monkeypatch.setenv("GEE_AUTH_TEST_ENABLED", "true")
    client = TestClient(app)

    response = client.post(
        "/gee/auth/test",
        headers={"X-User-Id": "1", "X-User-Role": "admin"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_SCOPE"


def test_post_auth_test_rejects_internal_role_from_request_header(monkeypatch) -> None:
    app.dependency_overrides.pop(get_authz_context, None)
    monkeypatch.setenv("GEE_AUTH_TEST_ENABLED", "true")
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck", lambda: None, raising=False
    )
    client = TestClient(app)

    response = client.post(
        "/gee/auth/test",
        headers={"X-User-Id": "1", "X-Requester-Role": "internal"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_SCOPE"


def test_auth_test_enabled_defaults_true_in_dev(monkeypatch) -> None:
    monkeypatch.delenv("GEE_AUTH_TEST_ENABLED", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("APP_ENV", raising=False)

    assert _is_gee_auth_test_enabled() is True


def test_auth_test_enabled_defaults_false_in_prod(monkeypatch) -> None:
    monkeypatch.delenv("GEE_AUTH_TEST_ENABLED", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("APP_ENV", raising=False)

    assert _is_gee_auth_test_enabled() is False


def test_auth_test_enabled_defaults_blank_env_uses_environment_default(
    monkeypatch,
) -> None:
    monkeypatch.setenv("GEE_AUTH_TEST_ENABLED", "   ")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("APP_ENV", raising=False)

    assert _is_gee_auth_test_enabled() is True


def test_post_era5_land_extract_point_returns_extract_contract(monkeypatch) -> None:
    class MeteoService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "era5-land"
            assert kwargs["variable"] == "air_temperature_2m"
            return {
                "dataset": "ECMWF/ERA5_LAND/HOURLY",
                "variable": "air_temperature_2m",
                "value": 301.15,
                "series": [
                    {
                        "date": "2026-06-01T00:00:00Z",
                        "value": 300.5,
                        "cloud_pct": None,
                    },
                    {
                        "date": "2026-06-10T00:00:00Z",
                        "value": 301.8,
                        "cloud_pct": None,
                    },
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/era5-land/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "air_temperature_2m",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "ECMWF/ERA5_LAND/HOURLY",
        "variable": "air_temperature_2m",
        "value": 301.15,
        "series": [
            {"date": "2026-06-01T00:00:00Z", "value": 300.5},
            {"date": "2026-06-10T00:00:00Z", "value": 301.8},
        ],
    }


def test_post_era5_land_extract_polygon_series_items_expose_date_and_value_only(
    monkeypatch,
) -> None:
    class MeteoService:
        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "era5-land"
            return {
                "dataset": "ECMWF/ERA5_LAND/HOURLY",
                "variable": "air_temperature_2m",
                "value": 300.0,
                "series": [
                    {
                        "date": "2026-06-03T00:00:00Z",
                        "value": 299.2,
                        "cloud_pct": 25.0,
                    }
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/era5-land/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "air_temperature_2m",
        },
    )

    assert response.status_code == 200
    assert response.json()["series"] == [
        {"date": "2026-06-03T00:00:00Z", "value": 299.2}
    ]
    assert "cloud_pct" not in response.json()["series"][0]


def test_post_ifs_forecast_extract_point_series_items_expose_date_and_value_only(
    monkeypatch,
) -> None:
    class MeteoService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "ifs-forecast"
            return {
                "dataset": "ECMWF/NRT_FORECAST/IFS/OPER",
                "variable": "surface_pressure",
                "value": 100100.0,
                "series": [
                    {
                        "date": "2026-06-01T06:00:00Z",
                        "value": 100080.0,
                        "cloud_pct": None,
                    }
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/ifs-forecast/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "surface_pressure",
        },
    )

    assert response.status_code == 200
    assert response.json()["series"] == [
        {"date": "2026-06-01T06:00:00Z", "value": 100080.0}
    ]
    assert "cloud_pct" not in response.json()["series"][0]


def test_post_ifs_forecast_extract_polygon_series_items_expose_date_and_value_only(
    monkeypatch,
) -> None:
    class MeteoService:
        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "ifs-forecast"
            return {
                "dataset": "ECMWF/NRT_FORECAST/IFS/OPER",
                "variable": "surface_pressure",
                "value": 100090.0,
                "series": [
                    {
                        "date": "2026-06-01T12:00:00Z",
                        "value": 100050.0,
                        "cloud_pct": 5.0,
                    }
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/ifs-forecast/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "surface_pressure",
        },
    )

    assert response.status_code == 200
    assert response.json()["series"] == [
        {"date": "2026-06-01T12:00:00Z", "value": 100050.0}
    ]
    assert "cloud_pct" not in response.json()["series"][0]


def test_post_era5_land_extract_point_rejects_invalid_coordinate_bounds(
    monkeypatch,
) -> None:
    class MeteoService:
        called = False

        def extract_point(self, **kwargs: object) -> dict[str, object]:
            self.called = True
            return {
                "dataset": "ECMWF/ERA5_LAND/HOURLY",
                "variable": "air_temperature_2m",
                "value": 0.0,
                "series": [],
            }

    service = MeteoService()
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: service,
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/era5-land/extract/point",
        json={
            "coordinates": [-181.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "air_temperature_2m",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"
    assert service.called is False


def test_post_ifs_forecast_extract_polygon_rejects_unclosed_ring(monkeypatch) -> None:
    class MeteoService:
        called = False

        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            self.called = True
            return {
                "dataset": "ECMWF/NRT_FORECAST/IFS/OPER",
                "variable": "surface_pressure",
                "value": 0.0,
                "series": [],
            }

    service = MeteoService()
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: service,
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/ifs-forecast/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.1, -15.1]]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "surface_pressure",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"
    assert service.called is False


def test_post_ifs_forecast_extract_polygon_maps_service_timeout(monkeypatch) -> None:
    class MeteoService:
        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            raise MeteoGEETimeoutError("GEE_TIMEOUT", "timeout", retryable=True)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/ifs-forecast/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-47.0, -15.0],
                        [-46.9, -15.0],
                        [-46.9, -15.1],
                        [-47.0, -15.0],
                    ]
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "surface_pressure",
        },
    )

    assert response.status_code == 504
    assert response.json()["error_code"] == "GEE_TIMEOUT"
    assert response.json()["retryable"] is True


def test_post_era5_land_extract_polygon_preserves_all_rings(monkeypatch) -> None:
    class MeteoService:
        captured_geometry: dict[str, object] | None = None

        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            self.captured_geometry = kwargs["geometry_geojson"]  # type: ignore[assignment]
            return {
                "dataset": "ECMWF/ERA5_LAND/HOURLY",
                "variable": "air_temperature_2m",
                "value": 1.23,
                "series": [
                    {
                        "date": "2026-06-01T00:00:00Z",
                        "value": 1.0,
                        "cloud_pct": None,
                    },
                    {
                        "date": "2026-06-10T00:00:00Z",
                        "value": 1.46,
                        "cloud_pct": None,
                    },
                ],
            }

    service = MeteoService()
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: service,
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/era5-land/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-47, -15],
                        [-46.8, -15],
                        [-46.8, -15.2],
                        [-47, -15.2],
                        [-47, -15],
                    ],
                    [
                        [-46.95, -15.05],
                        [-46.9, -15.05],
                        [-46.9, -15.1],
                        [-46.95, -15.1],
                        [-46.95, -15.05],
                    ],
                ],
            },
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "air_temperature_2m",
        },
    )

    assert response.status_code == 200
    assert service.captured_geometry == {
        "type": "Polygon",
        "coordinates": [
            [
                [-47.0, -15.0],
                [-46.8, -15.0],
                [-46.8, -15.2],
                [-47.0, -15.2],
                [-47.0, -15.0],
            ],
            [
                [-46.95, -15.05],
                [-46.9, -15.05],
                [-46.9, -15.1],
                [-46.95, -15.1],
                [-46.95, -15.05],
            ],
        ],
    }


def test_post_ifs_forecast_extract_point_maps_service_validation_error(
    monkeypatch,
) -> None:
    class MeteoService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            raise MeteoValidationError("INVALID_REQUEST", "Unsupported variable")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/ifs-forecast/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "unknown_variable",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"


def test_post_era5_land_extract_point_rejects_case_sensitive_variable(
    monkeypatch,
) -> None:
    class MeteoService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            raise MeteoValidationError("INVALID_REQUEST", "Unsupported variable")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/era5-land/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "AIR_TEMPERATURE_2M",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"


def test_post_ifs_forecast_extract_point_rejects_case_sensitive_variable(
    monkeypatch,
) -> None:
    class MeteoService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            raise MeteoValidationError("INVALID_REQUEST", "Unsupported variable")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/ifs-forecast/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2026-06-01",
            "date_end": "2026-06-10",
            "variable": "SURFACE_PRESSURE",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"


def test_get_era5_land_variables_returns_bare_sorted_array(monkeypatch) -> None:
    class MeteoService:
        def list_variables(self, dataset_key: str) -> list[dict[str, str]]:
            assert dataset_key == "era5-land"
            return [
                {
                    "variable": "total_precipitation",
                    "band_name": "total_precipitation_hourly",
                    "title": "Total precipitation",
                    "unit": "m",
                },
                {
                    "variable": "air_temperature_2m",
                    "band_name": "temperature_2m",
                    "title": "Air temperature at 2 m",
                    "unit": "K",
                },
                {
                    "variable": "dewpoint_temperature_2m",
                    "band_name": "dewpoint_temperature_2m",
                    "title": "Dewpoint temperature at 2 m",
                    "unit": "K",
                },
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.get("/gee/datasets/era5-land/variables")

    assert response.status_code == 200
    assert response.json() == [
        {
            "variable": "air_temperature_2m",
            "band_name": "temperature_2m",
            "title": "Air temperature at 2 m",
            "unit": "K",
        },
        {
            "variable": "dewpoint_temperature_2m",
            "band_name": "dewpoint_temperature_2m",
            "title": "Dewpoint temperature at 2 m",
            "unit": "K",
        },
        {
            "variable": "total_precipitation",
            "band_name": "total_precipitation_hourly",
            "title": "Total precipitation",
            "unit": "m",
        },
    ]


def test_get_ifs_forecast_variables_returns_bare_sorted_array(monkeypatch) -> None:
    class MeteoService:
        def list_variables(self, dataset_key: str) -> list[dict[str, str]]:
            assert dataset_key == "ifs-forecast"
            return [
                {
                    "variable": "wind_speed_10m",
                    "band_name": "u_component_of_wind_10m_sfc",
                    "title": "Wind speed at 10 m",
                    "unit": "m s-1",
                },
                {
                    "variable": "total_precipitation_sfc",
                    "band_name": "total_precipitation_sfc",
                    "title": "Total precipitation",
                    "unit": "m",
                },
                {
                    "variable": "air_temperature_2m",
                    "band_name": "temperature_2m_sfc",
                    "title": "Air temperature at 2 m",
                    "unit": "K",
                },
                {
                    "variable": "dewpoint_temperature_2m_sfc",
                    "band_name": "dewpoint_temperature_2m_sfc",
                    "title": "Dewpoint temperature at 2 m",
                    "unit": "K",
                },
                {
                    "variable": "temperature_2m_sfc",
                    "band_name": "temperature_2m_sfc",
                    "title": "Temperature at 2 m",
                    "unit": "K",
                },
                {
                    "variable": "u_component_of_wind_10m_sfc",
                    "band_name": "u_component_of_wind_10m_sfc",
                    "title": "U wind component at 10 m",
                    "unit": "m s-1",
                },
                {
                    "variable": "v_component_of_wind_10m_sfc",
                    "band_name": "v_component_of_wind_10m_sfc",
                    "title": "V wind component at 10 m",
                    "unit": "m s-1",
                },
                {
                    "variable": "volumetric_soil_water_layer_1_sfc",
                    "band_name": "volumetric_soil_water_layer_1_sfc",
                    "title": "Volumetric soil water layer 1",
                    "unit": "m3 m-3",
                },
                {
                    "variable": "potential_evaporation_sfc",
                    "band_name": "potential_evaporation_sfc",
                    "title": "Potential evaporation",
                    "unit": "m",
                },
                {
                    "variable": "surface_pressure",
                    "band_name": "surface_pressure_sfc",
                    "title": "Surface pressure",
                    "unit": "Pa",
                },
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.get("/gee/datasets/ifs-forecast/variables")

    assert response.status_code == 200
    assert response.json() == [
        {
            "variable": "air_temperature_2m",
            "band_name": "temperature_2m_sfc",
            "title": "Air temperature at 2 m",
            "unit": "K",
        },
        {
            "variable": "dewpoint_temperature_2m_sfc",
            "band_name": "dewpoint_temperature_2m_sfc",
            "title": "Dewpoint temperature at 2 m",
            "unit": "K",
        },
        {
            "variable": "potential_evaporation_sfc",
            "band_name": "potential_evaporation_sfc",
            "title": "Potential evaporation",
            "unit": "m",
        },
        {
            "variable": "surface_pressure",
            "band_name": "surface_pressure_sfc",
            "title": "Surface pressure",
            "unit": "Pa",
        },
        {
            "variable": "temperature_2m_sfc",
            "band_name": "temperature_2m_sfc",
            "title": "Temperature at 2 m",
            "unit": "K",
        },
        {
            "variable": "total_precipitation_sfc",
            "band_name": "total_precipitation_sfc",
            "title": "Total precipitation",
            "unit": "m",
        },
        {
            "variable": "u_component_of_wind_10m_sfc",
            "band_name": "u_component_of_wind_10m_sfc",
            "title": "U wind component at 10 m",
            "unit": "m s-1",
        },
        {
            "variable": "v_component_of_wind_10m_sfc",
            "band_name": "v_component_of_wind_10m_sfc",
            "title": "V wind component at 10 m",
            "unit": "m s-1",
        },
        {
            "variable": "volumetric_soil_water_layer_1_sfc",
            "band_name": "volumetric_soil_water_layer_1_sfc",
            "title": "Volumetric soil water layer 1",
            "unit": "m3 m-3",
        },
        {
            "variable": "wind_speed_10m",
            "band_name": "u_component_of_wind_10m_sfc",
            "title": "Wind speed at 10 m",
            "unit": "m s-1",
        },
    ]


def test_post_satellite_embedding_extract_point_returns_extract_contract(
    monkeypatch,
) -> None:
    class ExtractService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "satellite-embedding-annual"
            assert kwargs["variable"] == "A00"
            return {
                "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
                "variable": "A00",
                "value": 0.512,
                "series": [
                    {
                        "date": "2017-01-01T00:00:00Z",
                        "value": 0.501,
                        "cloud_pct": None,
                    },
                    {
                        "date": "2017-12-31T00:00:00Z",
                        "value": 0.523,
                        "cloud_pct": None,
                    },
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: ExtractService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/satellite-embedding-annual/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2017-01-01",
            "date_end": "2017-12-31",
            "variable": "A00",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
        "variable": "A00",
        "value": 0.512,
        "series": [
            {"date": "2017-01-01T00:00:00Z", "value": 0.501},
            {"date": "2017-12-31T00:00:00Z", "value": 0.523},
        ],
    }


def test_post_satellite_embedding_extract_polygon_returns_extract_contract(
    monkeypatch,
) -> None:
    class ExtractService:
        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "satellite-embedding-annual"
            assert kwargs["variable"] == "A63"
            return {
                "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
                "variable": "A63",
                "value": 0.711,
                "series": [
                    {
                        "date": "2018-01-01T00:00:00Z",
                        "value": 0.701,
                        "cloud_pct": 2.0,
                    },
                    {
                        "date": "2018-12-31T00:00:00Z",
                        "value": 0.721,
                        "cloud_pct": 4.0,
                    },
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: ExtractService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/satellite-embedding-annual/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2018-01-01",
            "date_end": "2018-12-31",
            "variable": "A63",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
        "variable": "A63",
        "value": 0.711,
        "series": [
            {"date": "2018-01-01T00:00:00Z", "value": 0.701},
            {"date": "2018-12-31T00:00:00Z", "value": 0.721},
        ],
    }


def test_get_satellite_embedding_variables_returns_bare_sorted_array(
    monkeypatch,
) -> None:
    class ExtractService:
        def list_variables(self, dataset_key: str) -> list[dict[str, str]]:
            assert dataset_key == "satellite-embedding-annual"
            return [
                {
                    "variable": "A63",
                    "band_name": "A63",
                    "title": "Embedding axis 63",
                    "unit": "dimensionless",
                },
                {
                    "variable": "A00",
                    "band_name": "A00",
                    "title": "Embedding axis 0",
                    "unit": "dimensionless",
                },
                {
                    "variable": "A10",
                    "band_name": "A10",
                    "title": "Embedding axis 10",
                    "unit": "dimensionless",
                },
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: ExtractService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.get("/gee/datasets/satellite-embedding-annual/variables")

    assert response.status_code == 200
    assert response.json() == [
        {
            "variable": "A00",
            "band_name": "A00",
            "title": "Embedding axis 0",
            "unit": "dimensionless",
        },
        {
            "variable": "A10",
            "band_name": "A10",
            "title": "Embedding axis 10",
            "unit": "dimensionless",
        },
        {
            "variable": "A63",
            "band_name": "A63",
            "title": "Embedding axis 63",
            "unit": "dimensionless",
        },
    ]


def test_post_satellite_embedding_extract_point_maps_service_validation_error(
    monkeypatch,
) -> None:
    class ExtractService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            raise MeteoValidationError("INVALID_REQUEST", "Unsupported variable")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: ExtractService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/satellite-embedding-annual/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2017-01-01",
            "date_end": "2017-12-31",
            "variable": "A99",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"


def test_post_satellite_embedding_extract_polygon_maps_service_timeout(
    monkeypatch,
) -> None:
    class ExtractService:
        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            raise MeteoGEETimeoutError("GEE_TIMEOUT", "timeout", retryable=True)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: ExtractService(),
        raising=False,
    )
    client = TestClient(app)

    response = client.post(
        "/gee/satellite-embedding-annual/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2018-01-01",
            "date_end": "2018-12-31",
            "variable": "A00",
        },
    )

    assert response.status_code == 504
    assert response.json()["error_code"] == "GEE_TIMEOUT"
    assert response.json()["retryable"] is True
