from datetime import date

import pytest

from agro_gee_api.services.gee_client import GEEAuthError, GEEUnavailableError
from agro_gee_api.services.gee_sentinel2 import (
    AreaLimitError,
    GEEAuthFailedError,
    GEETimeoutError,
    NoImageryError,
    Sentinel2StatsService,
    ValidationError,
)


class DummyClient:
    def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
        return 0.42, 3


def _polygon() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
        ],
    }


def test_validate_rejects_start_after_end() -> None:
    service = Sentinel2StatsService(gee_client=DummyClient(), area_limit_ha=10000)
    with pytest.raises(ValidationError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=100,
            date_start=date(2026, 6, 2),
            date_end=date(2026, 6, 1),
            metric="ndvi_mean",
        )
    assert exc.value.error_code == "INVALID_REQUEST"


def test_validate_rejects_window_above_365_days() -> None:
    service = Sentinel2StatsService(gee_client=DummyClient(), area_limit_ha=10000)
    with pytest.raises(ValidationError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=100,
            date_start=date(2025, 1, 1),
            date_end=date(2026, 2, 1),
            metric="ndvi_mean",
        )
    assert exc.value.error_code == "INVALID_REQUEST"


def test_validate_rejects_unsupported_metric() -> None:
    service = Sentinel2StatsService(gee_client=DummyClient(), area_limit_ha=10000)
    with pytest.raises(ValidationError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=100,
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            metric="ndwi_mean",
        )
    assert exc.value.error_code == "INVALID_REQUEST"


def test_validate_rejects_area_over_limit() -> None:
    service = Sentinel2StatsService(gee_client=DummyClient(), area_limit_ha=10)
    with pytest.raises(AreaLimitError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=11,
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            metric="ndvi_mean",
        )
    assert exc.value.error_code == "AREA_LIMIT_EXCEEDED"


class CaptureCloudClient:
    def __init__(self) -> None:
        self.cloud = None

    def ndvi_mean(self, **kwargs: object) -> tuple[float | None, int]:
        self.cloud = kwargs["cloud_pct_max"]
        return 0.55, 4


def test_compute_uses_cloud_filter_20_percent() -> None:
    client = CaptureCloudClient()
    service = Sentinel2StatsService(gee_client=client, area_limit_ha=10000)

    result = service.compute(
        geometry_geojson=_polygon(),
        area_ha=100,
        date_start=date(2026, 1, 1),
        date_end=date(2026, 1, 31),
        metric="ndvi_mean",
    )

    assert client.cloud == 20
    assert result.images_used == 4


class NoImageryClient:
    def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
        return None, 0


def test_compute_maps_no_imagery_result_to_domain_error() -> None:
    service = Sentinel2StatsService(gee_client=NoImageryClient(), area_limit_ha=10000)

    with pytest.raises(NoImageryError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=100,
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "NO_IMAGERY"


class TimeoutClient:
    def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
        raise TimeoutError("timeout")


def test_compute_maps_timeout_to_gee_timeout() -> None:
    service = Sentinel2StatsService(gee_client=TimeoutClient(), area_limit_ha=10000)

    with pytest.raises(GEETimeoutError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=100,
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "GEE_TIMEOUT"
    assert exc.value.retryable is True


class UnavailableClient:
    def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
        raise GEEUnavailableError("GEE_UNAVAILABLE", "unavailable", retryable=True)


def test_compute_maps_unavailable_to_domain_error() -> None:
    service = Sentinel2StatsService(gee_client=UnavailableClient(), area_limit_ha=10000)

    with pytest.raises(GEEUnavailableError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=100,
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "GEE_UNAVAILABLE"


class AuthFailedClient:
    def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
        raise GEEAuthError("GEE_AUTH_FAILED", "bad creds")


def test_compute_maps_auth_error_to_domain_error() -> None:
    service = Sentinel2StatsService(gee_client=AuthFailedClient(), area_limit_ha=10000)

    with pytest.raises(GEEAuthFailedError) as exc:
        service.compute(
            geometry_geojson=_polygon(),
            area_ha=100,
            date_start=date(2026, 1, 1),
            date_end=date(2026, 1, 31),
            metric="ndvi_mean",
        )

    assert exc.value.error_code == "GEE_AUTH_FAILED"
