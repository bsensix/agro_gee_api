from datetime import date

import pytest

from agro_gee_api.services.gee_client import GEEAuthError, GEEUnavailableError
from agro_gee_api.services.gee_sentinel1_extract import (
    GEEAuthFailedError,
    GEETimeoutError,
    Sentinel1ExtractService,
    ValidationError,
)


class DummyExtractClient:
    def extract_point_sentinel1(self, **_: object) -> float:
        return 0.33

    def extract_polygon_sentinel1(self, **_: object) -> float:
        return 0.41

    def timeseries_sentinel1(self, **_: object) -> list[dict[str, object]]:
        return []


def _point() -> dict[str, object]:
    return {"type": "Point", "coordinates": [-47.0, -15.0]}


def _polygon() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
        ],
    }


def test_extract_point_rejects_unsupported_metric() -> None:
    service = Sentinel1ExtractService(gee_client=DummyExtractClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


@pytest.mark.parametrize("metric", ["vv_mean", "vh_mean", "vv_vh_ratio"])
def test_extract_point_accepts_supported_metrics(metric: str) -> None:
    service = Sentinel1ExtractService(gee_client=DummyExtractClient())

    value = service.extract_point(
        geometry_geojson=_point(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        metric=metric,
    )

    assert value == 0.33


def test_extract_point_rejects_window_above_365_days() -> None:
    service = Sentinel1ExtractService(gee_client=DummyExtractClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 1, 1),
            date_end=date(2027, 1, 2),
            metric="vv_mean",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


def test_extract_point_rejects_date_start_after_date_end() -> None:
    service = Sentinel1ExtractService(gee_client=DummyExtractClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 10),
            date_end=date(2026, 6, 1),
            metric="vv_mean",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


class TimeoutClient(DummyExtractClient):
    def extract_point_sentinel1(self, **_: object) -> float:
        raise TimeoutError("timeout")


def test_extract_point_maps_timeout_to_gee_timeout_error() -> None:
    service = Sentinel1ExtractService(gee_client=TimeoutClient())

    with pytest.raises(GEETimeoutError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="vv_mean",
        )

    assert exc.value.error_code == "GEE_TIMEOUT"


class AuthClient(DummyExtractClient):
    def extract_point_sentinel1(self, **_: object) -> float:
        raise GEEAuthError("GEE_AUTH_FAILED", "bad creds")


def test_extract_point_maps_auth_error() -> None:
    service = Sentinel1ExtractService(gee_client=AuthClient())

    with pytest.raises(GEEAuthFailedError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="vv_mean",
        )

    assert exc.value.error_code == "GEE_AUTH_FAILED"


class NoImageryPolygonClient(DummyExtractClient):
    def extract_polygon_sentinel1(self, **_: object) -> float:
        raise GEEUnavailableError("NO_IMAGERY", "No valid imagery", retryable=False)


def test_extract_polygon_propagates_no_imagery_unavailable_error() -> None:
    service = Sentinel1ExtractService(gee_client=NoImageryPolygonClient())

    with pytest.raises(GEEUnavailableError) as exc:
        service.extract_polygon(
            geometry_geojson=_polygon(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="vv_mean",
        )

    assert exc.value.error_code == "NO_IMAGERY"
