import pytest

from agro_gee_api.services.gee_meteo_catalog import get_dataset_catalog, list_dataset_variables


@pytest.mark.parametrize(
    ("key", "dataset_id"),
    [
        ("era5-land", "ECMWF/ERA5_LAND/HOURLY"),
        ("ifs-forecast", "ECMWF/NRT_FORECAST/IFS/OPER"),
    ],
)
def test_get_dataset_catalog_uses_expected_dataset_ids(
    key: str, dataset_id: str
) -> None:
    catalog = get_dataset_catalog(key)

    assert catalog.key == key
    assert catalog.dataset_id == dataset_id


def test_get_dataset_catalog_unknown_key_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unknown"):
        get_dataset_catalog("unknown")


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        (
            "era5-land",
            [
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
            ],
        ),
        (
            "ifs-forecast",
            [
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
            ],
        ),
    ],
)
def test_list_dataset_variables_returns_exact_sorted_payload(
    key: str, expected: list[dict[str, str]]
) -> None:
    variables = list_dataset_variables(key)

    assert variables == expected


def test_list_dataset_variables_unknown_key_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unknown"):
        list_dataset_variables("unknown")
