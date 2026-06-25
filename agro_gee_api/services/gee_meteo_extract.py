from dataclasses import dataclass
from datetime import date
from typing import Protocol

from agro_gee_api.services.gee_client import (
    DatasetExtractResult,
    GEEAuthError,
    GEEUnavailableError,
)
from agro_gee_api.services.gee_meteo_catalog import (
    MeteoVariablePayload,
    get_dataset_catalog,
    list_dataset_variables,
)


@dataclass(frozen=True)
class ValidationError(Exception):
    error_code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class GEETimeoutError(Exception):
    error_code: str
    message: str
    retryable: bool


class MeteoExtractClient(Protocol):
    def extract_dataset_point(
        self,
        *,
        dataset_id: str,
        band_name: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult: ...

    def extract_dataset_polygon(
        self,
        *,
        dataset_id: str,
        band_name: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult: ...


@dataclass(frozen=True)
class _DatasetExtractSettings:
    max_window_days: int
    max_window_label: str
    max_window_years: int | None = None
    scale: int | None = None


_DEFAULT_DATASET_SETTINGS = _DatasetExtractSettings(
    max_window_days=31,
    max_window_label="31 days",
)
_DATASET_SETTINGS_BY_KEY: dict[str, _DatasetExtractSettings] = {
    "copernicus-dem-glo30": _DatasetExtractSettings(
        max_window_days=36500,
        max_window_label="100 years",
        scale=30,
    ),
    "satellite-embedding-annual": _DatasetExtractSettings(
        max_window_days=3660,
        max_window_label="10 years",
        max_window_years=10,
        scale=10,
    ),
}


class MeteoExtractService:
    def __init__(self, *, gee_client: MeteoExtractClient) -> None:
        self._gee_client = gee_client

    def extract_point(
        self,
        *,
        dataset_key: str,
        geometry_geojson: dict[str, object],
        date_start: date,
        date_end: date,
        variable: str,
    ) -> DatasetExtractResult:
        settings = self._get_dataset_settings(dataset_key=dataset_key)
        self._validate(date_start=date_start, date_end=date_end, settings=settings)
        dataset_id, band_name = self._resolve_dataset_and_band(
            dataset_key=dataset_key,
            variable=variable,
        )
        request_args: dict[str, object] = {
            "dataset_id": dataset_id,
            "band_name": band_name,
            "geometry_geojson": geometry_geojson,
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
        }
        if settings.scale is not None:
            request_args["scale"] = settings.scale
        try:
            return self._gee_client.extract_dataset_point(**request_args)
        except TimeoutError as exc:
            raise GEETimeoutError(
                "GEE_TIMEOUT", "GEE request timed out", retryable=True
            ) from exc
        except (GEEAuthError, GEEUnavailableError):
            raise

    def extract_polygon(
        self,
        *,
        dataset_key: str,
        geometry_geojson: dict[str, object],
        date_start: date,
        date_end: date,
        variable: str,
    ) -> DatasetExtractResult:
        settings = self._get_dataset_settings(dataset_key=dataset_key)
        self._validate(date_start=date_start, date_end=date_end, settings=settings)
        dataset_id, band_name = self._resolve_dataset_and_band(
            dataset_key=dataset_key,
            variable=variable,
        )
        request_args: dict[str, object] = {
            "dataset_id": dataset_id,
            "band_name": band_name,
            "geometry_geojson": geometry_geojson,
            "date_start": date_start.isoformat(),
            "date_end": date_end.isoformat(),
        }
        if settings.scale is not None:
            request_args["scale"] = settings.scale
        try:
            return self._gee_client.extract_dataset_polygon(**request_args)
        except TimeoutError as exc:
            raise GEETimeoutError(
                "GEE_TIMEOUT", "GEE request timed out", retryable=True
            ) from exc
        except (GEEAuthError, GEEUnavailableError):
            raise

    def list_variables(self, dataset_key: str) -> list[MeteoVariablePayload]:
        try:
            return list_dataset_variables(dataset_key)
        except KeyError as exc:
            raise ValidationError("INVALID_REQUEST", "Unsupported dataset_key") from exc

    def _validate(
        self,
        *,
        date_start: date,
        date_end: date,
        settings: _DatasetExtractSettings,
    ) -> None:
        if date_start > date_end:
            raise ValidationError("INVALID_REQUEST", "date_start must be <= date_end")
        if (date_end - date_start).days > settings.max_window_days:
            raise ValidationError(
                "INVALID_REQUEST",
                f"date range exceeds {settings.max_window_label}",
            )
        if settings.max_window_years is not None:
            max_end = self._add_years(date_start, settings.max_window_years)
            if date_end > max_end:
                raise ValidationError(
                    "INVALID_REQUEST",
                    f"date range exceeds {settings.max_window_label}",
                )

    def _get_dataset_settings(self, *, dataset_key: str) -> _DatasetExtractSettings:
        return _DATASET_SETTINGS_BY_KEY.get(dataset_key, _DEFAULT_DATASET_SETTINGS)

    def _add_years(self, value: date, years: int) -> date:
        try:
            return value.replace(year=value.year + years)
        except ValueError:
            return value.replace(month=2, day=28, year=value.year + years)

    def _resolve_dataset_and_band(
        self, *, dataset_key: str, variable: str
    ) -> tuple[str, str]:
        try:
            dataset = get_dataset_catalog(dataset_key)
        except KeyError as exc:
            raise ValidationError("INVALID_REQUEST", "Unsupported dataset_key") from exc

        for item in dataset.variables:
            if item.variable == variable:
                return dataset.dataset_id, item.band_name

        raise ValidationError(
            "INVALID_REQUEST",
            f"Unsupported variable '{variable}' for dataset '{dataset_key}'",
        )
