from dataclasses import dataclass
from datetime import date
import os
from collections.abc import Callable
from typing import Any, cast
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agro_gee_api.routes._authz import (
    AuthzContext,
    get_authz_context,
    has_admin_or_internal_scope,
)
from agro_gee_api.services.gee_catalog import (
    GEECatalogService,
)
from agro_gee_api.services.gee_client import (
    DatasetExtractResult,
    EarthEngineClient,
    GEEAuthError,
    GEEUnavailableError,
)
from agro_gee_api.services.gee_meteo_catalog import (
    MeteoVariablePayload,
    get_dataset_catalog,
)
from agro_gee_api.services.gee_meteo_extract import (
    GEETimeoutError as MeteoGEETimeoutError,
    MeteoExtractService,
    ValidationError as MeteoValidationError,
)
from agro_gee_api.services.gee_runtime import GEERuntime
from agro_gee_api.services.gee_sentinel1_extract import (
    GEEAuthFailedError as Sentinel1GEEAuthFailedError,
    GEETimeoutError as Sentinel1GEETimeoutError,
    Sentinel1ExtractService,
    ValidationError as Sentinel1ValidationError,
)
from agro_gee_api.services.gee_landsat9_extract import (
    GEEAuthFailedError as Landsat9GEEAuthFailedError,
    GEETimeoutError as Landsat9GEETimeoutError,
    Landsat9ExtractService,
    ValidationError as Landsat9ValidationError,
)
from agro_gee_api.services.gee_sentinel2_extract import (
    GEEAuthFailedError as ExtractGEEAuthFailedError,
    GEETimeoutError as ExtractGEETimeoutError,
    Sentinel2ExtractService,
    ValidationError as ExtractValidationError,
)

router = APIRouter(prefix="/gee")

_GEE_RUNTIME = GEERuntime()

STATUS_BY_CODE = {
    "INVALID_REQUEST": 400,
    "FORBIDDEN_SCOPE": 403,
    "AREA_LIMIT_EXCEEDED": 413,
    "NO_IMAGERY": 422,
    "GEE_UNAVAILABLE": 503,
    "GEE_TIMEOUT": 504,
    "GEE_AUTH_FAILED": 500,
}


@dataclass(frozen=True)
class DomainError(Exception):
    error_code: str
    message: str
    retryable: bool = False
    details: dict[str, object] | None = None


class GEEDatasetResponse(BaseModel):
    dataset_id: str
    provider: str
    title: str
    bands: list[str]


class Sentinel2ExtractPointRequest(BaseModel):
    coordinates: list[float]
    date_start: date
    date_end: date
    metric: str


class Sentinel2ExtractPolygonRequest(BaseModel):
    geometry: dict[str, object]
    date_start: date
    date_end: date
    metric: str


class Sentinel2ExtractValueResponse(BaseModel):
    dataset: str
    metric: str
    value: float
    series: list[dict[str, object]]


class Landsat9ExtractPointRequest(BaseModel):
    coordinates: list[float]
    date_start: date
    date_end: date
    metric: str


class Landsat9ExtractPolygonRequest(BaseModel):
    geometry: dict[str, object]
    date_start: date
    date_end: date
    metric: str


class Landsat9ExtractValueResponse(BaseModel):
    dataset: str
    metric: str
    value: float
    series: list[dict[str, object]]


class Sentinel1ExtractPointRequest(BaseModel):
    coordinates: list[float]
    date_start: date
    date_end: date
    metric: str


class Sentinel1ExtractPolygonRequest(BaseModel):
    geometry: dict[str, object]
    date_start: date
    date_end: date
    metric: str


class Sentinel1ExtractValueResponse(BaseModel):
    dataset: str
    metric: str
    value: float
    series: list[dict[str, object]]


class GEEAuthTestResponse(BaseModel):
    status: str


class MeteoExtractPointRequest(BaseModel):
    coordinates: list[object]
    date_start: date
    date_end: date
    variable: str


class MeteoExtractPolygonRequest(BaseModel):
    geometry: dict[str, object]
    date_start: date
    date_end: date
    variable: str


class MeteoExtractSeriesItemResponse(BaseModel):
    date: str
    value: float


class MeteoExtractResponse(BaseModel):
    dataset: str
    variable: str
    value: float
    series: list[MeteoExtractSeriesItemResponse]


class MeteoVariableResponse(BaseModel):
    variable: str
    band_name: str
    title: str
    unit: str


def get_catalog_service() -> GEECatalogService:
    return GEECatalogService()


def get_extract_service() -> Sentinel2ExtractService:
    return Sentinel2ExtractService(gee_client=get_gee_client())


def get_sentinel1_extract_service() -> Sentinel1ExtractService:
    return Sentinel1ExtractService(gee_client=cast(Any, get_gee_client()))


def get_landsat9_extract_service() -> Landsat9ExtractService:
    return Landsat9ExtractService(gee_client=get_gee_client())


def get_gee_client() -> EarthEngineClient:
    return EarthEngineClient(runtime=_GEE_RUNTIME)


class _MeteoRouteClient:
    def __init__(self, *, gee_client: EarthEngineClient) -> None:
        self._gee_client = gee_client

    def extract_dataset_point(
        self,
        *,
        dataset_id: str,
        band_name: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult:
        return self._gee_client.extract_point_dataset(
            dataset_id=dataset_id,
            band_name=band_name,
            variable=band_name,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            scale=scale,
        )

    def extract_dataset_polygon(
        self,
        *,
        dataset_id: str,
        band_name: str,
        geometry_geojson: dict[str, object],
        date_start: str,
        date_end: str,
        scale: int | None = None,
    ) -> DatasetExtractResult:
        return self._gee_client.extract_polygon_dataset(
            dataset_id=dataset_id,
            band_name=band_name,
            variable=band_name,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            scale=scale,
        )


def get_meteo_extract_service() -> MeteoExtractService:
    return MeteoExtractService(
        gee_client=_MeteoRouteClient(gee_client=get_gee_client())
    )


def _error_response(exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS_BY_CODE.get(exc.error_code, 500),
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "correlation_id": str(uuid4()),
            "retryable": exc.retryable,
        },
    )


def _is_gee_auth_test_enabled() -> bool:
    raw = os.getenv("GEE_AUTH_TEST_ENABLED")
    if raw is not None:
        normalized = raw.strip().lower()
        if normalized:
            return normalized in {"1", "true", "yes", "on"}

    env_name = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    return env_name in {"local", "dev", "development", "test", "testing"}


def _has_gee_auth_test_access(authz: AuthzContext) -> bool:
    return has_admin_or_internal_scope(authz)


def _is_numeric(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_lon_lat(lon: object, lat: object) -> tuple[float, float]:
    if not _is_numeric(lon) or not _is_numeric(lat):
        raise DomainError("INVALID_REQUEST", "Malformed geometry")
    lon_value = float(cast(int | float, lon))
    lat_value = float(cast(int | float, lat))
    if lon_value < -180 or lon_value > 180 or lat_value < -90 or lat_value > 90:
        raise DomainError("INVALID_REQUEST", "Malformed geometry")
    return lon_value, lat_value


def _validate_point_coordinates(
    coordinates: list[object] | list[float],
) -> dict[str, object]:
    if len(coordinates) != 2:
        raise DomainError("INVALID_REQUEST", "Malformed geometry")
    lon, lat = _validate_lon_lat(coordinates[0], coordinates[1])
    return {"type": "Point", "coordinates": [lon, lat]}


def _validate_polygon_geometry(geometry: dict[str, object]) -> dict[str, object]:
    if geometry.get("type") != "Polygon":
        raise DomainError("INVALID_REQUEST", "Malformed geometry")
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise DomainError("INVALID_REQUEST", "Malformed geometry")
    normalized_coordinates: list[list[list[float]]] = []
    for ring in coordinates:
        if not isinstance(ring, list) or len(ring) < 4:
            raise DomainError("INVALID_REQUEST", "Malformed geometry")

        normalized_ring: list[list[float]] = []
        for point in ring:
            if not isinstance(point, list) or len(point) != 2:
                raise DomainError("INVALID_REQUEST", "Malformed geometry")
            lon, lat = _validate_lon_lat(point[0], point[1])
            normalized_ring.append([lon, lat])

        if normalized_ring[0] != normalized_ring[-1]:
            raise DomainError("INVALID_REQUEST", "Malformed geometry")
        normalized_coordinates.append(normalized_ring)

    return {"type": "Polygon", "coordinates": normalized_coordinates}


def _sort_variable_catalog(
    variables: list[MeteoVariablePayload],
) -> list[MeteoVariablePayload]:
    return sorted(variables, key=lambda item: item["variable"])


def _map_meteo_error(exc: Exception) -> DomainError:
    if isinstance(exc, MeteoValidationError):
        return DomainError(exc.error_code, exc.message, retryable=exc.retryable)
    if isinstance(exc, MeteoGEETimeoutError):
        return DomainError(exc.error_code, exc.message, retryable=exc.retryable)
    if isinstance(exc, GEEAuthError):
        return DomainError("GEE_AUTH_FAILED", exc.message, retryable=False)
    if isinstance(exc, GEEUnavailableError):
        return DomainError(exc.error_code, exc.message, retryable=exc.retryable)
    return DomainError("GEE_INTERNAL_ERROR", "Earth Engine operation failed")


def _meteo_extract_point(
    *, dataset_key: str, payload: MeteoExtractPointRequest
) -> MeteoExtractResponse | JSONResponse:
    try:
        geometry_geojson = _validate_point_coordinates(payload.coordinates)
        extract_result = get_meteo_extract_service().extract_point(
            dataset_key=dataset_key,
            geometry_geojson=geometry_geojson,
            date_start=payload.date_start,
            date_end=payload.date_end,
            variable=payload.variable,
        )
    except DomainError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(_map_meteo_error(exc))

    return MeteoExtractResponse(
        dataset=extract_result["dataset"],
        variable=extract_result["variable"],
        value=extract_result["value"],
        series=[
            MeteoExtractSeriesItemResponse(date=item["date"], value=item["value"])
            for item in extract_result["series"]
        ],
    )


def _meteo_extract_polygon(
    *, dataset_key: str, payload: MeteoExtractPolygonRequest
) -> MeteoExtractResponse | JSONResponse:
    try:
        geometry_geojson = _validate_polygon_geometry(payload.geometry)
        extract_result = get_meteo_extract_service().extract_polygon(
            dataset_key=dataset_key,
            geometry_geojson=geometry_geojson,
            date_start=payload.date_start,
            date_end=payload.date_end,
            variable=payload.variable,
        )
    except DomainError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(_map_meteo_error(exc))

    return MeteoExtractResponse(
        dataset=extract_result["dataset"],
        variable=extract_result["variable"],
        value=extract_result["value"],
        series=[
            MeteoExtractSeriesItemResponse(date=item["date"], value=item["value"])
            for item in extract_result["series"]
        ],
    )


def _sentinel1_series_average_or_none(series: list[dict[str, object]]) -> float | None:
    values = [
        float(cast(float, item.get("value")))
        for item in series
        if isinstance(item, dict)
        and isinstance(item.get("value"), (int, float))
        and not isinstance(item.get("value"), bool)
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 10)


def _strip_cloud_pct_from_series(
    series: list[dict[str, object]],
) -> list[dict[str, object]]:
    return [{k: v for k, v in item.items() if k != "cloud_pct"} for item in series]


def _map_sentinel1_error(exc: Exception) -> DomainError:
    if isinstance(exc, Sentinel1ValidationError):
        return DomainError(exc.error_code, exc.message, retryable=exc.retryable)
    if isinstance(exc, Sentinel1GEETimeoutError):
        return DomainError("GEE_TIMEOUT", exc.message, retryable=exc.retryable)
    if isinstance(exc, Sentinel1GEEAuthFailedError):
        return DomainError("GEE_AUTH_FAILED", exc.message, retryable=exc.retryable)
    if isinstance(exc, GEEAuthError):
        return DomainError("GEE_AUTH_FAILED", exc.message, retryable=False)
    if isinstance(exc, GEEUnavailableError):
        return DomainError(exc.error_code, exc.message, retryable=exc.retryable)
    return DomainError("GEE_INTERNAL_ERROR", "Earth Engine operation failed")


def _build_sentinel1_response(
    *, metric: str, extracted_value: float, series: list[dict[str, object]]
) -> Sentinel1ExtractValueResponse:
    normalized_series = _strip_cloud_pct_from_series(series)
    average = _sentinel1_series_average_or_none(normalized_series)
    value = average if average is not None else extracted_value
    return Sentinel1ExtractValueResponse(
        dataset="COPERNICUS/S1_GRD",
        metric=metric,
        value=value,
        series=normalized_series,
    )


def _sentinel1_extract(
    *,
    geometry_geojson: dict[str, object],
    date_start: date,
    date_end: date,
    metric: str,
    extract_fn: Callable[..., float],
) -> Sentinel1ExtractValueResponse | JSONResponse:
    try:
        service = get_sentinel1_extract_service()
        extracted_value = extract_fn(
            service,
            geometry_geojson=geometry_geojson,
            date_start=date_start,
            date_end=date_end,
            metric=metric,
        )
        series = list(
            service.timeseries(
                geometry_geojson=geometry_geojson,
                date_start=date_start,
                date_end=date_end,
                metric=metric,
            )
        )
    except DomainError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(_map_sentinel1_error(exc))

    return _build_sentinel1_response(
        metric=metric,
        extracted_value=extracted_value,
        series=series,
    )


def _sentinel1_extract_point(
    payload: Sentinel1ExtractPointRequest,
) -> Sentinel1ExtractValueResponse | JSONResponse:
    try:
        geometry_geojson = _validate_point_coordinates(payload.coordinates)
    except DomainError as exc:
        return _error_response(exc)
    return _sentinel1_extract(
        geometry_geojson=geometry_geojson,
        date_start=payload.date_start,
        date_end=payload.date_end,
        metric=payload.metric,
        extract_fn=lambda service, **kwargs: service.extract_point(**kwargs),
    )


def _sentinel1_extract_polygon(
    payload: Sentinel1ExtractPolygonRequest,
) -> Sentinel1ExtractValueResponse | JSONResponse:
    try:
        geometry_geojson = _validate_polygon_geometry(payload.geometry)
    except DomainError as exc:
        return _error_response(exc)
    return _sentinel1_extract(
        geometry_geojson=geometry_geojson,
        date_start=payload.date_start,
        date_end=payload.date_end,
        metric=payload.metric,
        extract_fn=lambda service, **kwargs: service.extract_polygon(**kwargs),
    )


def run_gee_auth_recheck() -> None:
    _GEE_RUNTIME.ensure_initialized(force_recheck=True)


@router.get("/ping", tags=["gee-core"])
def ping() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/auth/test", response_model=GEEAuthTestResponse, tags=["gee-core"])
def post_gee_auth_test(
    authz: AuthzContext = Depends(get_authz_context),
) -> GEEAuthTestResponse | JSONResponse:
    if not _is_gee_auth_test_enabled():
        raise HTTPException(status_code=404, detail="Not Found")

    if not _has_gee_auth_test_access(authz):
        return _error_response(DomainError("FORBIDDEN_SCOPE", "Forbidden"))

    try:
        run_gee_auth_recheck()
    except GEEAuthError as exc:
        return _error_response(
            DomainError(exc.error_code, exc.message, retryable=False)
        )
    except GEEUnavailableError as exc:
        return _error_response(
            DomainError(exc.error_code, exc.message, retryable=exc.retryable)
        )

    return GEEAuthTestResponse(status="ok")


@router.post(
    "/era5-land/extract/point",
    response_model=MeteoExtractResponse,
    tags=["era5-land"],
)
def post_era5_land_extract_point(
    payload: MeteoExtractPointRequest,
) -> MeteoExtractResponse | JSONResponse:
    return _meteo_extract_point(dataset_key="era5-land", payload=payload)


@router.post(
    "/era5-land/extract/polygon",
    response_model=MeteoExtractResponse,
    tags=["era5-land"],
)
def post_era5_land_extract_polygon(
    payload: MeteoExtractPolygonRequest,
) -> MeteoExtractResponse | JSONResponse:
    return _meteo_extract_polygon(dataset_key="era5-land", payload=payload)


@router.post(
    "/ifs-forecast/extract/point",
    response_model=MeteoExtractResponse,
    tags=["ifs-forecast"],
)
def post_ifs_forecast_extract_point(
    payload: MeteoExtractPointRequest,
) -> MeteoExtractResponse | JSONResponse:
    return _meteo_extract_point(dataset_key="ifs-forecast", payload=payload)


@router.post(
    "/ifs-forecast/extract/polygon",
    response_model=MeteoExtractResponse,
    tags=["ifs-forecast"],
)
def post_ifs_forecast_extract_polygon(
    payload: MeteoExtractPolygonRequest,
) -> MeteoExtractResponse | JSONResponse:
    return _meteo_extract_polygon(dataset_key="ifs-forecast", payload=payload)


@router.post(
    "/satellite-embedding-annual/extract/point",
    response_model=MeteoExtractResponse,
    tags=["satellite-embedding-annual"],
)
def post_satellite_embedding_annual_extract_point(
    payload: MeteoExtractPointRequest,
) -> MeteoExtractResponse | JSONResponse:
    return _meteo_extract_point(
        dataset_key="satellite-embedding-annual", payload=payload
    )


@router.post(
    "/satellite-embedding-annual/extract/polygon",
    response_model=MeteoExtractResponse,
    tags=["satellite-embedding-annual"],
)
def post_satellite_embedding_annual_extract_polygon(
    payload: MeteoExtractPolygonRequest,
) -> MeteoExtractResponse | JSONResponse:
    return _meteo_extract_polygon(
        dataset_key="satellite-embedding-annual", payload=payload
    )


@router.post(
    "/sentinel1/extract/point",
    response_model=Sentinel1ExtractValueResponse,
    tags=["sentinel1"],
)
def post_sentinel1_extract_point(
    payload: Sentinel1ExtractPointRequest,
) -> Sentinel1ExtractValueResponse | JSONResponse:
    return _sentinel1_extract_point(payload)


@router.post(
    "/sentinel1/extract/polygon",
    response_model=Sentinel1ExtractValueResponse,
    tags=["sentinel1"],
)
def post_sentinel1_extract_polygon(
    payload: Sentinel1ExtractPolygonRequest,
) -> Sentinel1ExtractValueResponse | JSONResponse:
    return _sentinel1_extract_polygon(payload)


@router.get(
    "/datasets/era5-land/variables",
    response_model=list[MeteoVariableResponse],
    tags=["era5-land"],
)
def get_era5_land_variables() -> list[MeteoVariableResponse] | JSONResponse:
    try:
        variables = get_meteo_extract_service().list_variables("era5-land")
    except Exception as exc:
        return _error_response(_map_meteo_error(exc))
    return [MeteoVariableResponse(**item) for item in _sort_variable_catalog(variables)]


@router.get(
    "/datasets/ifs-forecast/variables",
    response_model=list[MeteoVariableResponse],
    tags=["ifs-forecast"],
)
def get_ifs_forecast_variables() -> list[MeteoVariableResponse] | JSONResponse:
    try:
        variables = get_meteo_extract_service().list_variables("ifs-forecast")
    except Exception as exc:
        return _error_response(_map_meteo_error(exc))
    return [MeteoVariableResponse(**item) for item in _sort_variable_catalog(variables)]


@router.get(
    "/datasets/satellite-embedding-annual/variables",
    response_model=list[MeteoVariableResponse],
    tags=["satellite-embedding-annual"],
)
def get_satellite_embedding_annual_variables() -> (
    list[MeteoVariableResponse] | JSONResponse
):
    try:
        variables = get_meteo_extract_service().list_variables(
            "satellite-embedding-annual"
        )
    except Exception as exc:
        return _error_response(_map_meteo_error(exc))
    return [MeteoVariableResponse(**item) for item in _sort_variable_catalog(variables)]


@router.get("/datasets", response_model=list[GEEDatasetResponse], tags=["gee-core"])
def get_gee_datasets() -> list[GEEDatasetResponse]:
    service = get_catalog_service()
    items = service.list_datasets()
    return [
        GEEDatasetResponse(
            dataset_id=item.dataset_id,
            provider=item.provider,
            title=item.title,
            bands=item.bands,
        )
        for item in items
    ]


@router.post(
    "/sentinel2/extract/point",
    response_model=Sentinel2ExtractValueResponse,
    tags=["sentinel2"],
)
def post_sentinel2_extract_point(
    payload: Sentinel2ExtractPointRequest,
) -> Sentinel2ExtractValueResponse | JSONResponse:
    try:
        service = get_extract_service()
        geometry_geojson = {
            "type": "Point",
            "coordinates": payload.coordinates,
        }
        value = service.extract_point(
            geometry_geojson=geometry_geojson,
            date_start=payload.date_start,
            date_end=payload.date_end,
            metric=payload.metric,
        )
        series: list[dict[str, object]] = []
        if hasattr(service, "timeseries"):
            timeseries_fn = cast(Any, service).timeseries
            series = list(
                timeseries_fn(
                    geometry_geojson=geometry_geojson,
                    date_start=payload.date_start,
                    date_end=payload.date_end,
                    metric=payload.metric,
                )
            )
        if series:
            values = [
                float(cast(float, item.get("value")))
                for item in series
                if isinstance(item, dict)
                and isinstance(item.get("value"), (int, float))
            ]
            if values:
                value = sum(values) / len(values)
    except ExtractValidationError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except GEEAuthError as exc:
        return _error_response(
            DomainError("GEE_AUTH_FAILED", exc.message, retryable=False)
        )
    except GEEUnavailableError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except ExtractGEETimeoutError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except ExtractGEEAuthFailedError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))

    return Sentinel2ExtractValueResponse(
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        metric=payload.metric,
        value=value,
        series=series,
    )


@router.post(
    "/sentinel2/extract/polygon",
    response_model=Sentinel2ExtractValueResponse,
    tags=["sentinel2"],
)
def post_sentinel2_extract_polygon(
    payload: Sentinel2ExtractPolygonRequest,
) -> Sentinel2ExtractValueResponse | JSONResponse:
    try:
        service = get_extract_service()
        value = service.extract_polygon(
            geometry_geojson=payload.geometry,
            date_start=payload.date_start,
            date_end=payload.date_end,
            metric=payload.metric,
        )
        series: list[dict[str, object]] = []
        if hasattr(service, "timeseries"):
            timeseries_fn = cast(Any, service).timeseries
            series = list(
                timeseries_fn(
                    geometry_geojson=payload.geometry,
                    date_start=payload.date_start,
                    date_end=payload.date_end,
                    metric=payload.metric,
                )
            )
        if series:
            values = [
                float(cast(float, item.get("value")))
                for item in series
                if isinstance(item, dict)
                and isinstance(item.get("value"), (int, float))
            ]
            if values:
                value = sum(values) / len(values)
    except ExtractValidationError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except GEEAuthError as exc:
        return _error_response(
            DomainError("GEE_AUTH_FAILED", exc.message, retryable=False)
        )
    except GEEUnavailableError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))

    return Sentinel2ExtractValueResponse(
        dataset="COPERNICUS/S2_SR_HARMONIZED",
        metric=payload.metric,
        value=value,
        series=series,
    )


@router.post(
    "/landsat9/extract/point",
    response_model=Landsat9ExtractValueResponse,
    tags=["landsat9"],
)
def post_landsat9_extract_point(
    payload: Landsat9ExtractPointRequest,
) -> Landsat9ExtractValueResponse | JSONResponse:
    try:
        service = get_landsat9_extract_service()
        geometry_geojson = {
            "type": "Point",
            "coordinates": payload.coordinates,
        }
        value = service.extract_point(
            geometry_geojson=geometry_geojson,
            date_start=payload.date_start,
            date_end=payload.date_end,
            metric=payload.metric,
        )
        series: list[dict[str, object]] = []
        if hasattr(service, "timeseries"):
            timeseries_fn = cast(Any, service).timeseries
            series = list(
                timeseries_fn(
                    geometry_geojson=geometry_geojson,
                    date_start=payload.date_start,
                    date_end=payload.date_end,
                    metric=payload.metric,
                )
            )
        if series:
            values = [
                float(cast(float, item.get("value")))
                for item in series
                if isinstance(item, dict)
                and isinstance(item.get("value"), (int, float))
            ]
            if values:
                value = sum(values) / len(values)
    except Landsat9ValidationError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except GEEAuthError as exc:
        return _error_response(
            DomainError("GEE_AUTH_FAILED", exc.message, retryable=False)
        )
    except GEEUnavailableError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except Landsat9GEETimeoutError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except Landsat9GEEAuthFailedError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))

    return Landsat9ExtractValueResponse(
        dataset="LANDSAT/LC09/C02/T1_L2",
        metric=payload.metric,
        value=value,
        series=series,
    )


@router.post(
    "/landsat9/extract/polygon",
    response_model=Landsat9ExtractValueResponse,
    tags=["landsat9"],
)
def post_landsat9_extract_polygon(
    payload: Landsat9ExtractPolygonRequest,
) -> Landsat9ExtractValueResponse | JSONResponse:
    try:
        service = get_landsat9_extract_service()
        value = service.extract_polygon(
            geometry_geojson=payload.geometry,
            date_start=payload.date_start,
            date_end=payload.date_end,
            metric=payload.metric,
        )
        series: list[dict[str, object]] = []
        if hasattr(service, "timeseries"):
            timeseries_fn = cast(Any, service).timeseries
            series = list(
                timeseries_fn(
                    geometry_geojson=payload.geometry,
                    date_start=payload.date_start,
                    date_end=payload.date_end,
                    metric=payload.metric,
                )
            )
        if series:
            values = [
                float(cast(float, item.get("value")))
                for item in series
                if isinstance(item, dict)
                and isinstance(item.get("value"), (int, float))
            ]
            if values:
                value = sum(values) / len(values)
    except Landsat9ValidationError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))
    except GEEAuthError as exc:
        return _error_response(
            DomainError("GEE_AUTH_FAILED", exc.message, retryable=False)
        )
    except GEEUnavailableError as exc:
        return _error_response(DomainError(exc.error_code, exc.message, exc.retryable))

    return Landsat9ExtractValueResponse(
        dataset="LANDSAT/LC09/C02/T1_L2",
        metric=payload.metric,
        value=value,
        series=series,
    )
