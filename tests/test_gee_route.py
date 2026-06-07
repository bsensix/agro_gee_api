from datetime import date
from typing import Mapping, Sequence

from fastapi.testclient import TestClient

from agro_gee_api.main import app
from agro_gee_api.routes._authz import AuthzContext, get_authz_context
from agro_gee_api.routes.gee import _is_gee_auth_test_enabled
from agro_gee_api.services.gee_client import GEEUnavailableError
from agro_gee_api.services.gee_client import GEEAuthError
from agro_gee_api.services.gee_sentinel2_extract import ValidationError as ExtractValidationError
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


class _FakeAuthzCursor:
    def __init__(
        self,
        allowed_rows: Sequence[Mapping[str, object]],
        role_row: Mapping[str, object],
    ):
        self._allowed_rows = allowed_rows
        self._role_row = role_row
        self._execute_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self._execute_count += 1

    def fetchall(self) -> Sequence[Mapping[str, object]]:
        return self._allowed_rows

    def fetchone(self) -> Mapping[str, object]:
        return self._role_row


class _FakeAuthzConnection:
    def __init__(
        self,
        allowed_rows: Sequence[Mapping[str, object]],
        role_row: Mapping[str, object],
    ):
        self._allowed_rows = allowed_rows
        self._role_row = role_row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self) -> _FakeAuthzCursor:
        return _FakeAuthzCursor(self._allowed_rows, self._role_row)


def _mock_authz_db(monkeypatch, *, role: str) -> None:
    allowed_rows = [{"user_id": 1}]
    role_row = {"role": role}
    monkeypatch.setattr(
        "agro_gee_api.routes._authz.get_connection",
        lambda: _FakeAuthzConnection(allowed_rows, role_row),
    )


def test_get_gee_datasets_returns_active_catalog(monkeypatch) -> None:
    class CatalogService:
        def list_datasets(self) -> list[object]:
            class Item:
                dataset_id = "COPERNICUS/S2_SR_HARMONIZED"
                provider = "gee"
                title = "Sentinel-2 SR Harmonized"
                bands = ["B2", "B3", "B4", "B8"]

            return [Item()]

    monkeypatch.setattr("agro_gee_api.routes.gee.get_catalog_service", lambda: CatalogService())
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

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
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

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
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
        "agro_gee_api.routes.gee.get_gee_client", lambda: AuthFailedClient(), raising=False
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
        "agro_gee_api.routes.gee.get_gee_client", lambda: UnavailableClient(), raising=False
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
        "agro_gee_api.routes.gee.get_gee_client", lambda: AuthFailedClient(), raising=False
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

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
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

    monkeypatch.setattr("agro_gee_api.routes.gee.get_extract_service", lambda: ExtractService())
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

    monkeypatch.setattr("agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True)
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

    monkeypatch.setattr("agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True)
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck", _raise_auth_failed, raising=False
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

    monkeypatch.setattr("agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True)
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

    monkeypatch.setattr("agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True)
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck", _raise_unavailable, raising=False
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

    monkeypatch.setattr("agro_gee_api.routes.gee._has_gee_auth_test_access", lambda _: True)
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
    _mock_authz_db(monkeypatch, role="owner")
    client = TestClient(app)

    response = client.post(
        "/gee/auth/test",
        headers={"X-User-Id": "1", "X-User-Role": "admin"},
    )

    assert response.status_code == 403
    assert response.json()["error_code"] == "FORBIDDEN_SCOPE"


def test_post_auth_test_allows_internal_role_from_db(monkeypatch) -> None:
    app.dependency_overrides.pop(get_authz_context, None)
    monkeypatch.setenv("GEE_AUTH_TEST_ENABLED", "true")
    _mock_authz_db(monkeypatch, role="internal")
    monkeypatch.setattr(
        "agro_gee_api.routes.gee.run_gee_auth_recheck", lambda: None, raising=False
    )
    client = TestClient(app)

    response = client.post("/gee/auth/test", headers={"X-User-Id": "1"})

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
            {"date": "2026-06-01T00:00:00Z", "value": 300.5, "cloud_pct": None},
            {"date": "2026-06-10T00:00:00Z", "value": 301.8, "cloud_pct": None},
        ],
    }


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
        "agro_gee_api.routes.gee.get_meteo_extract_service", lambda: service, raising=False
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
        "agro_gee_api.routes.gee.get_meteo_extract_service", lambda: service, raising=False
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
        "agro_gee_api.routes.gee.get_meteo_extract_service", lambda: service, raising=False
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
                    "band_name": "10m_wind_speed",
                    "title": "Wind speed at 10 m",
                    "unit": "m s-1",
                },
                {
                    "variable": "air_temperature_2m",
                    "band_name": "2m_temperature",
                    "title": "Air temperature at 2 m",
                    "unit": "K",
                },
                {
                    "variable": "surface_pressure",
                    "band_name": "surface_pressure",
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
            "band_name": "2m_temperature",
            "title": "Air temperature at 2 m",
            "unit": "K",
        },
        {
            "variable": "surface_pressure",
            "band_name": "surface_pressure",
            "title": "Surface pressure",
            "unit": "Pa",
        },
        {
            "variable": "wind_speed_10m",
            "band_name": "10m_wind_speed",
            "title": "Wind speed at 10 m",
            "unit": "m s-1",
        },
    ]
