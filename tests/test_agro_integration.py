"""Integration coverage for Task 11 /agro endpoints.

This module focuses on /agro contracts. It also keeps minimal /gee smoke checks
as explicit non-regression coverage required by the Task 11 plan.
"""

from fastapi.testclient import TestClient
import pytest

from agro_gee_api.main import app
from agro_gee_api.services.agro_engine import kelvin_to_celsius, meters_to_mm


POINT_COORDINATES = [-47.8825, -15.7942]
POLYGON_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [
        [
            [-47.91, -15.78],
            [-47.86, -15.78],
            [-47.86, -15.82],
            [-47.91, -15.82],
            [-47.91, -15.78],
        ]
    ],
}


def _point_payload(crop: str) -> dict[str, object]:
    return {
        "crop": crop,
        "date_planting": "2026-10-15",
        "cycle_days": 120,
        "coordinates": POINT_COORDINATES,
        "profile_version": "v1_default",
    }


def _polygon_payload(crop: str) -> dict[str, object]:
    return {
        "crop": crop,
        "date_planting": "2026-10-15",
        "cycle_days": 120,
        "geometry": POLYGON_GEOMETRY,
        "profile_version": "v1_default",
    }


@pytest.mark.parametrize("crop", ["soybean", "corn", "cotton"])
def test_agro_et0_etc_point_for_main_crops_keeps_internal_consistency(
    crop: str,
) -> None:
    client = TestClient(app)

    response = client.post("/agro/et0-etc/point", json=_point_payload(crop))

    assert response.status_code == 200
    body = response.json()
    assert body["crop"] == crop
    assert body["etc_mm_day"] == pytest.approx(
        body["et0_mm_day"] * body["kc"], abs=1e-2
    )


@pytest.mark.parametrize("crop", ["soybean", "corn", "cotton"])
def test_agro_water_balance_point_for_main_crops_has_bucket_constraints(
    crop: str,
) -> None:
    client = TestClient(app)
    payload = {
        **_point_payload(crop),
        "cad_mm": 120.0,
        "water_initial_pct": 50.0,
    }

    response = client.post("/agro/water-balance/simple/point", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["crop"] == crop
    assert body["soil_water_mm"] >= 0.0
    assert body["deficit_mm"] >= 0.0
    assert body["excess_mm"] >= 0.0
    assert body["soil_water_mm"] <= body["cad_mm"]


@pytest.mark.parametrize("crop", ["soybean", "corn", "cotton"])
def test_agro_polygon_completeness_ratio_matches_aggregate_days(crop: str) -> None:
    client = TestClient(app)

    response = client.post(
        "/agro/phenology/estimate/polygon",
        json={**_polygon_payload(crop), "date_harvest": "2027-02-12"},
    )

    assert response.status_code == 200
    completeness = response.json()["data_completeness"]
    valid_days = completeness["valid_days"]
    no_data_days = completeness["no_data_days"]
    assert valid_days + no_data_days > 0
    assert completeness["valid_ratio"] == pytest.approx(
        valid_days / (valid_days + no_data_days)
    )
    assert completeness["valid_ratio"] >= 0.60


def test_agro_meteorology_unit_normalization_contract() -> None:
    meteo_snapshot = {
        "tmean_k": 300.15,
        "tmax_k": 303.15,
        "total_precipitation_m": 0.012,
    }

    normalized_snapshot = {
        "tmean_c": kelvin_to_celsius(meteo_snapshot["tmean_k"]),
        "tmax_c": kelvin_to_celsius(meteo_snapshot["tmax_k"]),
        "total_precipitation_mm": meters_to_mm(meteo_snapshot["total_precipitation_m"]),
    }

    assert normalized_snapshot["tmean_c"] == pytest.approx(27.0)
    assert normalized_snapshot["tmax_c"] == pytest.approx(30.0)
    assert normalized_snapshot["total_precipitation_mm"] == pytest.approx(12.0)


def test_gee_ping_non_regression_smoke() -> None:
    """Task 11 plan non-regression smoke for /gee ping."""

    client = TestClient(app)

    response = client.get("/gee/ping")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_gee_era5_point_non_regression_smoke_with_mocked_service(monkeypatch) -> None:
    """Task 11 plan non-regression smoke for /gee ERA5 extract."""

    class MeteoService:
        def extract_point(self, **_: object) -> dict[str, object]:
            return {
                "dataset": "ECMWF/ERA5_LAND/HOURLY",
                "variable": "air_temperature_2m",
                "value": 300.15,
                "series": [
                    {"date": "2026-06-01T00:00:00Z", "value": 299.15},
                    {"date": "2026-06-02T00:00:00Z", "value": 301.15},
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
            "date_end": "2026-06-02",
            "variable": "air_temperature_2m",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["dataset"] == "ECMWF/ERA5_LAND/HOURLY"
    assert body["variable"] == "air_temperature_2m"
    assert body["value"] == pytest.approx(300.15)
    assert kelvin_to_celsius(body["value"]) == pytest.approx(27.0)
    assert len(body["series"]) == 2
