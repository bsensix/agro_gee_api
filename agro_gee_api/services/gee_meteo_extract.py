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
    ) -> DatasetExtractResult: ...

    def extract_dataset_polygon(
        self,
        *,
        dataset_id: str,
        band_name: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
    ) -> DatasetExtractResult: ...


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
        self._validate(date_start=date_start, date_end=date_end)
        dataset_id, band_name = self._resolve_dataset_and_band(
            dataset_key=dataset_key,
            variable=variable,
        )
        try:
            return self._gee_client.extract_dataset_point(
                dataset_id=dataset_id,
                band_name=band_name,
                geometry_geojson=geometry_geojson,
                date_start=date_start.isoformat(),
                date_end=date_end.isoformat(),
            )
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
        self._validate(date_start=date_start, date_end=date_end)
        dataset_id, band_name = self._resolve_dataset_and_band(
            dataset_key=dataset_key,
            variable=variable,
        )
        try:
            return self._gee_client.extract_dataset_polygon(
                dataset_id=dataset_id,
                band_name=band_name,
                geometry_geojson=geometry_geojson,
                date_start=date_start.isoformat(),
                date_end=date_end.isoformat(),
            )
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

    def _validate(self, *, date_start: date, date_end: date) -> None:
        if date_start > date_end:
            raise ValidationError("INVALID_REQUEST", "date_start must be <= date_end")
        if (date_end - date_start).days > 31:
            raise ValidationError("INVALID_REQUEST", "date range exceeds 31 days")

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
