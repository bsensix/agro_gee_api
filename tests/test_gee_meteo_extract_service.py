from datetime import date

import pytest

from agro_gee_api.services.gee_client import (
    DatasetExtractResult,
    GEEAuthError,
    GEEUnavailableError,
)
from agro_gee_api.services.gee_meteo_extract import (
    GEETimeoutError,
    MeteoExtractService,
    ValidationError,
)


class FakeMeteoClient:
    def __init__(self) -> None:
        self.last_call: dict[str, object] | None = None

    def extract_dataset_point(self, **kwargs: object) -> DatasetExtractResult:
        self.last_call = kwargs
        return {
            "dataset": str(kwargs["dataset_id"]),
            "variable": "air_temperature_2m",
            "value": 301.15,
            "series": [
                {
                    "date": "2026-06-01T00:00:00Z",
                    "value": 300.0,
                    "cloud_pct": None,
                },
                {
                    "date": "2026-06-10T00:00:00Z",
                    "value": 302.3,
                    "cloud_pct": None,
                },
            ],
        }

    def extract_dataset_polygon(self, **kwargs: object) -> DatasetExtractResult:
        self.last_call = kwargs
        return {
            "dataset": str(kwargs["dataset_id"]),
            "variable": "surface_pressure",
            "value": 8.5,
            "series": [
                {
                    "date": "2026-06-01T00:00:00Z",
                    "value": 8.0,
                    "cloud_pct": None,
                },
                {
                    "date": "2026-06-10T00:00:00Z",
                    "value": 9.0,
                    "cloud_pct": None,
                },
            ],
        }


def _point() -> dict[str, object]:
    return {"type": "Point", "coordinates": [-47.0, -15.0]}


def _polygon() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
        ],
    }


def test_extract_point_delegates_dataset_and_variable_band_to_client() -> None:
    client = FakeMeteoClient()
    service = MeteoExtractService(gee_client=client)

    result = service.extract_point(
        dataset_key="era5-land",
        geometry_geojson=_point(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        variable="air_temperature_2m",
    )

    assert result == {
        "dataset": "ECMWF/ERA5_LAND/HOURLY",
        "variable": "air_temperature_2m",
        "value": 301.15,
        "series": [
            {"date": "2026-06-01T00:00:00Z", "value": 300.0, "cloud_pct": None},
            {"date": "2026-06-10T00:00:00Z", "value": 302.3, "cloud_pct": None},
        ],
    }
    assert client.last_call == {
        "dataset_id": "ECMWF/ERA5_LAND/HOURLY",
        "band_name": "temperature_2m",
        "geometry_geojson": _point(),
        "date_start": "2026-06-01",
        "date_end": "2026-06-10",
    }


def test_extract_polygon_delegates_dataset_and_variable_band_to_client() -> None:
    client = FakeMeteoClient()
    service = MeteoExtractService(gee_client=client)

    result = service.extract_polygon(
        dataset_key="ifs-forecast",
        geometry_geojson=_polygon(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        variable="surface_pressure",
    )

    assert result == {
        "dataset": "ECMWF/NRT_FORECAST/IFS/OPER",
        "variable": "surface_pressure",
        "value": 8.5,
        "series": [
            {"date": "2026-06-01T00:00:00Z", "value": 8.0, "cloud_pct": None},
            {"date": "2026-06-10T00:00:00Z", "value": 9.0, "cloud_pct": None},
        ],
    }
    assert client.last_call == {
        "dataset_id": "ECMWF/NRT_FORECAST/IFS/OPER",
        "band_name": "surface_pressure_sfc",
        "geometry_geojson": _polygon(),
        "date_start": "2026-06-01",
        "date_end": "2026-06-10",
    }


def test_extract_point_rejects_date_start_after_date_end() -> None:
    service = MeteoExtractService(gee_client=FakeMeteoClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_point(
            dataset_key="era5-land",
            geometry_geojson=_point(),
            date_start=date(2026, 6, 11),
            date_end=date(2026, 6, 10),
            variable="air_temperature_2m",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


def test_extract_polygon_rejects_window_above_31_days() -> None:
    service = MeteoExtractService(gee_client=FakeMeteoClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_polygon(
            dataset_key="ifs-forecast",
            geometry_geojson=_polygon(),
            date_start=date(2026, 1, 1),
            date_end=date(2026, 2, 2),
            variable="surface_pressure",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


def test_extract_point_rejects_unknown_variable_case_sensitive() -> None:
    service = MeteoExtractService(gee_client=FakeMeteoClient())

    with pytest.raises(ValidationError) as exc:
        service.extract_point(
            dataset_key="era5-land",
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            variable="Air_temperature_2m",
        )

    assert exc.value.error_code == "INVALID_REQUEST"


def test_list_variables_returns_catalog_payload() -> None:
    service = MeteoExtractService(gee_client=FakeMeteoClient())

    variables = service.list_variables("ifs-forecast")

    assert variables == [
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


def test_extract_point_accepts_total_precipitation_sfc_variable() -> None:
    client = FakeMeteoClient()
    service = MeteoExtractService(gee_client=client)

    service.extract_point(
        dataset_key="ifs-forecast",
        geometry_geojson=_point(),
        date_start=date(2026, 6, 1),
        date_end=date(2026, 6, 10),
        variable="total_precipitation_sfc",
    )

    assert client.last_call is not None
    assert client.last_call["band_name"] == "total_precipitation_sfc"


class TimeoutPointClient(FakeMeteoClient):
    def extract_dataset_point(self, **kwargs: object) -> DatasetExtractResult:
        self.last_call = kwargs
        raise TimeoutError("timeout")


def test_extract_point_maps_timeout_to_gee_timeout_error() -> None:
    service = MeteoExtractService(gee_client=TimeoutPointClient())

    with pytest.raises(GEETimeoutError) as exc:
        service.extract_point(
            dataset_key="era5-land",
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            variable="air_temperature_2m",
        )

    assert exc.value.error_code == "GEE_TIMEOUT"
    assert exc.value.retryable is True


class AuthPointClient(FakeMeteoClient):
    def extract_dataset_point(self, **kwargs: object) -> DatasetExtractResult:
        self.last_call = kwargs
        raise GEEAuthError("GEE_AUTH_FAILED", "bad creds")


def test_extract_point_passes_through_auth_error() -> None:
    service = MeteoExtractService(gee_client=AuthPointClient())

    with pytest.raises(GEEAuthError) as exc:
        service.extract_point(
            dataset_key="era5-land",
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            variable="air_temperature_2m",
        )

    assert exc.value.error_code == "GEE_AUTH_FAILED"


class UnavailablePointClient(FakeMeteoClient):
    def extract_dataset_point(self, **kwargs: object) -> DatasetExtractResult:
        self.last_call = kwargs
        raise GEEUnavailableError("GEE_UNAVAILABLE", "offline", retryable=True)


def test_extract_point_passes_through_unavailable_error() -> None:
    service = MeteoExtractService(gee_client=UnavailablePointClient())

    with pytest.raises(GEEUnavailableError) as exc:
        service.extract_point(
            dataset_key="era5-land",
            geometry_geojson=_point(),
            date_start=date(2026, 6, 1),
            date_end=date(2026, 6, 10),
            variable="air_temperature_2m",
        )

    assert exc.value.error_code == "GEE_UNAVAILABLE"
