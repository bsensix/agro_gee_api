from dataclasses import dataclass
from datetime import date

from agro_gee_api.services.gee_client import GEEAuthError, GEEClient, GEEUnavailableError


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


@dataclass(frozen=True)
class GEEAuthFailedError(Exception):
    error_code: str
    message: str
    retryable: bool = False


class Sentinel2ExtractService:
    _SUPPORTED_METRICS = {"ndvi_mean", "ndwi_mean", "evi_mean", "savi_mean"}

    def __init__(self, *, gee_client: GEEClient) -> None:
        self._gee_client = gee_client

    def extract_point(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: date,
        date_end: date,
        metric: str,
    ) -> float:
        self._validate_inputs(date_start=date_start, date_end=date_end, metric=metric)
        try:
            return self._gee_client.extract_point(
                geometry_geojson=geometry_geojson,
                date_start=date_start.isoformat(),
                date_end=date_end.isoformat(),
                cloud_pct_max=20,
                metric=metric,
            )
        except TimeoutError as exc:
            raise GEETimeoutError(
                "GEE_TIMEOUT", "GEE request timed out", retryable=True
            ) from exc
        except GEEAuthError as exc:
            raise GEEAuthFailedError("GEE_AUTH_FAILED", exc.message) from exc
        except GEEUnavailableError:
            raise

    def extract_polygon(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: date,
        date_end: date,
        metric: str,
    ) -> float:
        self._validate_inputs(date_start=date_start, date_end=date_end, metric=metric)
        return self._gee_client.extract_polygon(
            geometry_geojson=geometry_geojson,
            date_start=date_start.isoformat(),
            date_end=date_end.isoformat(),
            cloud_pct_max=20,
            metric=metric,
        )

    def timeseries(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: date,
        date_end: date,
        metric: str,
    ) -> list[dict[str, object]]:
        self._validate_inputs(date_start=date_start, date_end=date_end, metric=metric)
        return self._gee_client.timeseries(
            geometry_geojson=geometry_geojson,
            date_start=date_start.isoformat(),
            date_end=date_end.isoformat(),
            cloud_pct_max=20,
            metric=metric,
        )

    def image(
        self,
        *,
        geometry_geojson: dict[str, object],
        date_start: date,
        date_end: date,
        metric: str,
    ) -> str:
        self._validate_inputs(date_start=date_start, date_end=date_end, metric=metric)
        return self._gee_client.image(
            geometry_geojson=geometry_geojson,
            date_start=date_start.isoformat(),
            date_end=date_end.isoformat(),
            cloud_pct_max=20,
            metric=metric,
        )

    def _validate_inputs(
        self, *, date_start: date, date_end: date, metric: str
    ) -> None:
        if metric not in self._SUPPORTED_METRICS:
            raise ValidationError("INVALID_REQUEST", "Unsupported metric")
        if date_start > date_end:
            raise ValidationError("INVALID_REQUEST", "date_start must be <= date_end")
        if (date_end - date_start).days > 365:
            raise ValidationError("INVALID_REQUEST", "date range exceeds 365 days")
