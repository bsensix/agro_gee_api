import pytest

from agro_gee_api.services.gee_meteo_catalog import (
    get_dataset_catalog,
    list_dataset_variables,
)


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
                    "variable": "potential_evaporation",
                    "band_name": "potential_evaporation",
                    "title": "Potential evaporation",
                    "unit": "m",
                },
                {
                    "variable": "skin_temperature",
                    "band_name": "skin_temperature",
                    "title": "Skin temperature",
                    "unit": "K",
                },
                {
                    "variable": "soil_temperature_level_1",
                    "band_name": "soil_temperature_level_1",
                    "title": "Soil temperature level 1",
                    "unit": "K",
                },
                {
                    "variable": "surface_net_solar_radiation",
                    "band_name": "surface_net_solar_radiation",
                    "title": "Surface net solar radiation",
                    "unit": "J m-2",
                },
                {
                    "variable": "temperature_2m",
                    "band_name": "temperature_2m",
                    "title": "Temperature at 2 m",
                    "unit": "K",
                },
                {
                    "variable": "total_precipitation",
                    "band_name": "total_precipitation_hourly",
                    "title": "Total precipitation",
                    "unit": "m",
                },
                {
                    "variable": "u_component_of_wind_10m",
                    "band_name": "u_component_of_wind_10m",
                    "title": "U wind component at 10 m",
                    "unit": "m s-1",
                },
                {
                    "variable": "v_component_of_wind_10m",
                    "band_name": "v_component_of_wind_10m",
                    "title": "V wind component at 10 m",
                    "unit": "m s-1",
                },
                {
                    "variable": "volumetric_soil_water_layer_1",
                    "band_name": "volumetric_soil_water_layer_1",
                    "title": "Volumetric soil water layer 1",
                    "unit": "m3 m-3",
                },
            ],
        ),
        (
            "ifs-forecast",
            [
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
