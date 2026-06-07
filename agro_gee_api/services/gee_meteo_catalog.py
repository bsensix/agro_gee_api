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
        ),
    ),
    "ifs-forecast": MeteoDatasetCatalog(
        key="ifs-forecast",
        dataset_id="ECMWF/NRT_FORECAST/IFS/OPER",
        title="IFS Operational Forecast",
        variables=(
            MeteoVariable(
                variable="air_temperature_2m",
                band_name="2m_temperature",
                title="Air temperature at 2 m",
                unit="K",
            ),
            MeteoVariable(
                variable="surface_pressure",
                band_name="surface_pressure",
                title="Surface pressure",
                unit="Pa",
            ),
            MeteoVariable(
                variable="wind_speed_10m",
                band_name="10m_wind_speed",
                title="Wind speed at 10 m",
                unit="m s-1",
            ),
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
