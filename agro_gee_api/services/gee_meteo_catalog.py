from dataclasses import dataclass
from typing import TypedDict


class MeteoVariablePayload(TypedDict):
    variable: str
    band_name: str
    title: str
    unit: str


@dataclass(frozen=True)
class MeteoVariable:
    variable: str
    band_name: str
    title: str
    unit: str


@dataclass(frozen=True)
class MeteoDatasetCatalog:
    key: str
    dataset_id: str
    title: str
    variables: tuple[MeteoVariable, ...]


_DATASET_CATALOGS: dict[str, MeteoDatasetCatalog] = {
    "era5-land": MeteoDatasetCatalog(
        key="era5-land",
        dataset_id="ECMWF/ERA5_LAND/HOURLY",
        title="ERA5-Land Hourly",
        variables=(
            MeteoVariable(
                variable="air_temperature_2m",
                band_name="temperature_2m",
                title="Air temperature at 2 m",
                unit="K",
            ),
            MeteoVariable(
                variable="dewpoint_temperature_2m",
                band_name="dewpoint_temperature_2m",
                title="Dewpoint temperature at 2 m",
                unit="K",
            ),
            MeteoVariable(
                variable="total_precipitation",
                band_name="total_precipitation_hourly",
                title="Total precipitation",
                unit="m",
            ),
            MeteoVariable(
                variable="potential_evaporation",
                band_name="potential_evaporation",
                title="Potential evaporation",
                unit="m",
            ),
            MeteoVariable(
                variable="volumetric_soil_water_layer_1",
                band_name="volumetric_soil_water_layer_1",
                title="Volumetric soil water layer 1",
                unit="m3 m-3",
            ),
            MeteoVariable(
                variable="temperature_2m",
                band_name="temperature_2m",
                title="Temperature at 2 m",
                unit="K",
            ),
            MeteoVariable(
                variable="skin_temperature",
                band_name="skin_temperature",
                title="Skin temperature",
                unit="K",
            ),
            MeteoVariable(
                variable="soil_temperature_level_1",
                band_name="soil_temperature_level_1",
                title="Soil temperature level 1",
                unit="K",
            ),
            MeteoVariable(
                variable="surface_net_solar_radiation",
                band_name="surface_net_solar_radiation",
                title="Surface net solar radiation",
                unit="J m-2",
            ),
            MeteoVariable(
                variable="u_component_of_wind_10m",
                band_name="u_component_of_wind_10m",
                title="U wind component at 10 m",
                unit="m s-1",
            ),
            MeteoVariable(
                variable="v_component_of_wind_10m",
                band_name="v_component_of_wind_10m",
                title="V wind component at 10 m",
                unit="m s-1",
            ),
        ),
    ),
    "ifs-forecast": MeteoDatasetCatalog(
        key="ifs-forecast",
        dataset_id="ECMWF/NRT_FORECAST/IFS/OPER",
        title="IFS Operational Forecast",
        variables=(
            MeteoVariable(
                variable="air_temperature_2m",
                band_name="temperature_2m_sfc",
                title="Air temperature at 2 m",
                unit="K",
            ),
            MeteoVariable(
                variable="total_precipitation_sfc",
                band_name="total_precipitation_sfc",
                title="Total precipitation",
                unit="m",
            ),
            MeteoVariable(
                variable="u_component_of_wind_10m_sfc",
                band_name="u_component_of_wind_10m_sfc",
                title="U wind component at 10 m",
                unit="m s-1",
            ),
            MeteoVariable(
                variable="v_component_of_wind_10m_sfc",
                band_name="v_component_of_wind_10m_sfc",
                title="V wind component at 10 m",
                unit="m s-1",
            ),
            MeteoVariable(
                variable="temperature_2m_sfc",
                band_name="temperature_2m_sfc",
                title="Temperature at 2 m",
                unit="K",
            ),
            MeteoVariable(
                variable="dewpoint_temperature_2m_sfc",
                band_name="dewpoint_temperature_2m_sfc",
                title="Dewpoint temperature at 2 m",
                unit="K",
            ),
            MeteoVariable(
                variable="volumetric_soil_water_layer_1_sfc",
                band_name="volumetric_soil_water_layer_1_sfc",
                title="Volumetric soil water layer 1",
                unit="m3 m-3",
            ),
            MeteoVariable(
                variable="potential_evaporation_sfc",
                band_name="potential_evaporation_sfc",
                title="Potential evaporation",
                unit="m",
            ),
            MeteoVariable(
                variable="surface_pressure",
                band_name="surface_pressure_sfc",
                title="Surface pressure",
                unit="Pa",
            ),
            MeteoVariable(
                variable="wind_speed_10m",
                band_name="u_component_of_wind_10m_sfc",
                title="Wind speed at 10 m",
                unit="m s-1",
            ),
        ),
    ),
    "copernicus-dem-glo30": MeteoDatasetCatalog(
        key="copernicus-dem-glo30",
        dataset_id="COPERNICUS/DEM/GLO30",
        title="Copernicus DEM GLO30",
        variables=(
            MeteoVariable(
                variable="elevation",
                band_name="DEM",
                title="Digital elevation model",
                unit="m",
            ),
        ),
    ),
    "satellite-embedding-annual": MeteoDatasetCatalog(
        key="satellite-embedding-annual",
        dataset_id="GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
        title="Satellite Embedding V1 Annual",
        variables=tuple(
            MeteoVariable(
                variable=f"A{i:02d}",
                band_name=f"A{i:02d}",
                title=f"Embedding axis {i}",
                unit="dimensionless",
            )
            for i in range(64)
        ),
    ),
}


def get_dataset_catalog(key: str) -> MeteoDatasetCatalog:
    try:
        return _DATASET_CATALOGS[key]
    except KeyError as exc:
        available_keys = ", ".join(sorted(_DATASET_CATALOGS))
        raise KeyError(
            f"Unknown meteo dataset key '{key}'. Available keys: {available_keys}"
        ) from exc


def list_dataset_variables(key: str) -> list[MeteoVariablePayload]:
    catalog = get_dataset_catalog(key)
    return [
        {
            "variable": variable.variable,
            "band_name": variable.band_name,
            "title": variable.title,
            "unit": variable.unit,
        }
        for variable in sorted(catalog.variables, key=lambda item: item.variable)
    ]
