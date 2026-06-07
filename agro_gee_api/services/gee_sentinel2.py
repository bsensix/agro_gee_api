from dataclasses import dataclass
from datetime import date

from agro_gee_api.services.gee_client import GEEAuthError, GEEClient, GEEUnavailableError


@dataclass(frozen=True)
class ValidationError(Exception):
    error_code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class AreaLimitError(Exception):
    error_code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class NoImageryError(Exception):
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


@dataclass(frozen=True)
class Sentinel2StatsResult:
    metric: str
    value: float
    images_used: int
    dataset: str = "COPERNICUS/S2_SR_HARMONIZED"


class Sentinel2StatsService:
    def __init__(self, *, gee_client: GEEClient, area_limit_ha: float) -> None:
        self._gee_client = gee_client
        self._area_limit_ha = area_limit_ha

    def compute(
        self,
        *,
        geometry_geojson: dict[str, object],
        area_ha: float,
        date_start: date,
        date_end: date,
        metric: str,
    ) -> Sentinel2StatsResult:
        if metric != "ndvi_mean":
            raise ValidationError("INVALID_REQUEST", "Unsupported metric")
        if date_start > date_end:
            raise ValidationError("INVALID_REQUEST", "date_start must be <= date_end")
        if (date_end - date_start).days > 365:
            raise ValidationError("INVALID_REQUEST", "date range exceeds 365 days")
        if area_ha > self._area_limit_ha:
            raise AreaLimitError(
                "AREA_LIMIT_EXCEEDED",
                "Field area exceeds synchronous limit",
            )

        try:
            value, images_used = self._gee_client.ndvi_mean(
                geometry_geojson=geometry_geojson,
                date_start=date_start.isoformat(),
                date_end=date_end.isoformat(),
                cloud_pct_max=20,
            )
        except TimeoutError as exc:
            raise GEETimeoutError(
                "GEE_TIMEOUT", "GEE request timed out", retryable=True
            ) from exc
        except GEEAuthError as exc:
            raise GEEAuthFailedError("GEE_AUTH_FAILED", exc.message) from exc
        except GEEUnavailableError:
            raise

        if value is None or images_used <= 0:
            raise NoImageryError("NO_IMAGERY", "No valid imagery for requested period")

        return Sentinel2StatsResult(metric=metric, value=value, images_used=images_used)
