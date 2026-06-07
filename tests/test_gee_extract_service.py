from datetime import date

import pytest

from agro_gee_api.services.gee_client import GEEAuthError, GEEUnavailableError
from agro_gee_api.services.gee_sentinel2_extract import (
    GEEAuthFailedError,
    GEETimeoutError,
    Sentinel2ExtractService,
    ValidationError,
)


class DummyExtractClient:
    def extract_point(self, **_: object) -> float:
        return 0.45

    def extract_polygon(self, **_: object) -> float:
        return 0.52

    def timeseries(self, **_: object) -> list[dict[str, object]]:
        return [{"date": "2026-06-01", "value": 0.4, "cloud_pct": 12.5}]

    def image(self, **_: object) -> str:
        return "https://example.com/gee/sentinel2.png"


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
    service = Sentinel2ExtractService(gee_client=DummyExtractClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="foo_mean",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


def test_extract_point_rejects_start_after_end() -> None:
    service = Sentinel2ExtractService(gee_client=DummyExtractClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 10),
            date_end=date(2026, 6, 1),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


def test_extract_point_returns_value() -> None:
    service = Sentinel2ExtractService(gee_client=DummyExtractClient())

    value = service.extract_point(
        geometry_geojson=_point(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        metric="ndvi_mean",
    )

    assert value == 0.45


def test_extract_polygon_returns_value() -> None:
    service = Sentinel2ExtractService(gee_client=DummyExtractClient())

    value = service.extract_polygon(
        geometry_geojson=_polygon(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        metric="ndvi_mean",
    )

    assert value == 0.52


def test_timeseries_returns_items() -> None:
    service = Sentinel2ExtractService(gee_client=DummyExtractClient())

    items = service.timeseries(
        geometry_geojson=_polygon(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        metric="ndvi_mean",
    )

    assert items == [{"date": "2026-06-01", "value": 0.4, "cloud_pct": 12.5}]


@pytest.mark.parametrize("metric", ["ndvi_mean", "ndwi_mean", "evi_mean", "savi_mean"])
def test_extract_point_accepts_supported_metrics(metric: str) -> None:
    service = Sentinel2ExtractService(gee_client=DummyExtractClient())

    value = service.extract_point(
        geometry_geojson=_point(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        metric=metric,
    )

    assert value == 0.45


def test_image_returns_url() -> None:
    service = Sentinel2ExtractService(gee_client=DummyExtractClient())

    url = service.image(
        geometry_geojson=_polygon(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        metric="ndvi_mean",
    )

    assert url == "https://example.com/gee/sentinel2.png"


class TimeoutClient(DummyExtractClient):
    def extract_point(self, **_: object) -> float:
        raise TimeoutError("timeout")


def test_extract_point_maps_timeout() -> None:
    service = Sentinel2ExtractService(gee_client=TimeoutClient())

    with pytest.raises(GEETimeoutError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "GEE_TIMEOUT"


class AuthClient(DummyExtractClient):
    def extract_point(self, **_: object) -> float:
        raise GEEAuthError("GEE_AUTH_FAILED", "bad creds")


def test_extract_point_maps_auth_error() -> None:
    service = Sentinel2ExtractService(gee_client=AuthClient())

    with pytest.raises(GEEAuthFailedError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "GEE_AUTH_FAILED"


class UnavailableClient(DummyExtractClient):
    def extract_point(self, **_: object) -> float:
        raise GEEUnavailableError("GEE_UNAVAILABLE", "offline", retryable=True)


def test_extract_point_propagates_unavailable() -> None:
    service = Sentinel2ExtractService(gee_client=UnavailableClient())

    with pytest.raises(GEEUnavailableError) as exc:
        service.extract_point(
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "GEE_UNAVAILABLE"
