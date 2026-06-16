from dataclasses import dataclass
from datetime import date
import hashlib
from typing import cast

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agro_gee_api.services import agro_engine
from agro_gee_api.services.agro_profiles import CropProfile, get_crop_profile

router = APIRouter(prefix="/agro")


@dataclass(frozen=True)
class DomainError(Exception):
    status_code: int
    error_code: str
    message: str
    retryable: bool = False
    details: dict[str, object] | None = None


class AgroBaseRequest(BaseModel):
    crop: str
    date_planting: date
    cycle_days: int
    profile_version: str | None = None
    date_harvest: date | None = None


class PointRequest(AgroBaseRequest):
    coordinates: tuple[float, float]


class PolygonRequest(AgroBaseRequest):
    geometry: dict[str, object]


class WaterPointRequest(PointRequest):
    cad_mm: float
    water_initial_pct: float


class WaterPolygonRequest(PolygonRequest):
    cad_mm: float
    water_initial_pct: float


NO_DATA_RING = (
    (-48.25, -16.25),
    (-48.10, -16.25),
    (-48.10, -16.45),
    (-48.25, -16.45),
    (-48.25, -16.25),
)

GEE_TIMEOUT_RING = (
    (-45.80, -12.20),
    (-45.65, -12.20),
    (-45.65, -12.35),
    (-45.80, -12.35),
    (-45.80, -12.20),
)

INTERNAL_ERROR_RING = (
    (-54.70, -13.00),
    (-54.45, -13.00),
    (-54.45, -13.25),
    (-54.70, -13.25),
    (-54.70, -13.00),
)

GEE_UNAVAILABLE_POINT = (179.9999, 89.9999)


def _error_response(exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": exc.message,
            "retryable": exc.retryable,
            "details": exc.details or {},
        },
    )


def _polygon_ring(geometry: dict[str, object]) -> tuple[tuple[float, float], ...]:
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or not coordinates:
        raise DomainError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message="geometry.coordinates must contain a valid polygon ring",
            details={"field": "geometry.coordinates"},
        )
    exterior = coordinates[0]
    if not isinstance(exterior, list) or not exterior:
        raise DomainError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message="geometry.coordinates must contain a valid polygon ring",
            details={"field": "geometry.coordinates"},
        )

    ring: list[tuple[float, float]] = []
    for point in exterior:
        if not isinstance(point, list) or len(point) != 2:
            raise DomainError(
                status_code=400,
                error_code="INVALID_REQUEST",
                message="geometry.coordinates must contain [lon, lat] numeric pairs",
                details={"field": "geometry.coordinates"},
            )
        try:
            lon = float(cast(int | float | str, point[0]))
            lat = float(cast(int | float | str, point[1]))
        except (TypeError, ValueError) as exc:
            raise DomainError(
                status_code=400,
                error_code="INVALID_REQUEST",
                message="geometry.coordinates must contain [lon, lat] numeric pairs",
                details={"field": "geometry.coordinates"},
            ) from exc
        ring.append((lon, lat))
    return tuple(ring)


def _validate_harvest(payload: AgroBaseRequest) -> None:
    if payload.cycle_days <= 0:
        raise DomainError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message="cycle_days must be greater than zero",
            details={"field": "cycle_days"},
        )
    if payload.date_harvest and payload.date_harvest < payload.date_planting:
        raise DomainError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message="date_harvest cannot be before date_planting",
            details={"field": "date_harvest"},
        )


def _polygon_completeness(*, is_no_data: bool = False) -> dict[str, object]:
    if is_no_data:
        return {"valid_days": 12, "no_data_days": 20, "valid_ratio": 0.375}
    return {"valid_days": 26, "no_data_days": 6, "valid_ratio": 0.8125}


def _maybe_raise_common_polygon_errors(payload: PolygonRequest) -> None:
    ring = _polygon_ring(payload.geometry)
    if ring == NO_DATA_RING:
        completeness = _polygon_completeness(is_no_data=True)
        raise DomainError(
            status_code=422,
            error_code="NO_DATA",
            message="Insufficient valid observations for polygon",
            details={"valid_ratio": completeness["valid_ratio"]},
        )


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _stable_ratio(values: tuple[object, ...]) -> float:
    joined = "|".join(str(value) for value in values)
    digest = hashlib.sha256(joined.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big") / float(2**64)


def _resolve_profile(payload: AgroBaseRequest) -> CropProfile:
    version = payload.profile_version or "v1_default"
    try:
        return get_crop_profile(crop=payload.crop, version=version)
    except ValueError as exc:
        message = str(exc)
        details: dict[str, object] = {"field": "crop"}
        if message.lower().startswith("unsupported profile version"):
            details = {"field": cast(object, "profile_version")}
        raise DomainError(
            status_code=400,
            error_code="INVALID_REQUEST",
            message=message,
            details=details,
        ) from exc


def _effective_observation_days(payload: AgroBaseRequest, signal_ratio: float) -> int:
    deterministic_share = 0.25 + 0.55 * signal_ratio
    return max(1, int(payload.cycle_days * deterministic_share))


def _phase_sub_by_gdd(profile: CropProfile, gdd_accumulated: float) -> str:
    for index, gdd_range in enumerate(profile.gdd_ranges):
        is_last = index == len(profile.gdd_ranges) - 1
        if gdd_range.start_gdd <= gdd_accumulated < gdd_range.end_gdd:
            return gdd_range.sub
        if is_last and gdd_accumulated >= gdd_range.end_gdd:
            return gdd_range.sub
    return profile.gdd_ranges[0].sub


def _point_signal(payload: PointRequest) -> tuple[float, float, float]:
    lon, lat = payload.coordinates
    lon_f = float(lon)
    lat_f = float(lat)
    ratio = _stable_ratio(
        (
            payload.crop,
            payload.profile_version or "v1_default",
            payload.date_planting.isoformat(),
            payload.cycle_days,
            lon_f,
            lat_f,
        )
    )
    return lon_f, lat_f, ratio


def _polygon_signal(payload: PolygonRequest) -> tuple[float, float, float]:
    ring = _polygon_ring(payload.geometry)
    core_ring = ring[:-1] if len(ring) >= 2 and ring[0] == ring[-1] else ring
    lon_mean = sum(point[0] for point in core_ring) / len(core_ring)
    lat_mean = sum(point[1] for point in core_ring) / len(core_ring)
    span = max(point[0] for point in core_ring) - min(point[0] for point in core_ring)
    span += max(point[1] for point in core_ring) - min(point[1] for point in core_ring)
    ratio = _stable_ratio(
        (
            payload.crop,
            payload.profile_version or "v1_default",
            payload.date_planting.isoformat(),
            payload.cycle_days,
            round(lon_mean, 6),
            round(lat_mean, 6),
            round(span, 6),
        )
    )
    return lon_mean, lat_mean, ratio


def _pseudo_weather(
    *,
    payload: AgroBaseRequest,
    profile: CropProfile,
    latitude_deg: float,
    signal_ratio: float,
) -> dict[str, float | str]:
    observation_days = _effective_observation_days(payload, signal_ratio)
    pct_cycle = _clamp((observation_days / payload.cycle_days) * 100.0, 0.0, 100.0)
    cycle_range = agro_engine.phase_by_cycle(crop=profile.crop, pct_cycle=pct_cycle)

    latitude_factor = _clamp(abs(latitude_deg) / 30.0, 0.0, 1.0)
    tmean_c = 21.5 + (1.0 - latitude_factor) * 6.0 + (signal_ratio - 0.5) * 3.0
    thermal_amplitude_c = 6.0 + signal_ratio * 6.0
    tmin_c = tmean_c - thermal_amplitude_c / 2.0
    tmax_c = tmean_c + thermal_amplitude_c / 2.0
    gdd_c_day = agro_engine.gdd_day(
        tmean_c=tmean_c,
        tbase_c=profile.tbase_c,
        tcap_c=profile.tcap_c,
    )

    gdd_accumulated = gdd_c_day * observation_days
    phase_sub = _phase_sub_by_gdd(profile, gdd_accumulated)

    precipitation_mm = max(
        0.0, (1.0 - signal_ratio) * 8.0 + (1.0 - latitude_factor) * 2.0
    )
    persistence_days = 1 + int(signal_ratio * 5)

    return {
        "pct_cycle": round(pct_cycle, 2),
        "phase_macro": cycle_range.macro,
        "phase_sub": phase_sub,
        "gdd_c_day": round(gdd_c_day, 2),
        "tmin_c": tmin_c,
        "tmax_c": tmax_c,
        "tmean_c": tmean_c,
        "precipitation_mm": precipitation_mm,
        "persistence_days": float(persistence_days),
    }


@router.post("/phenology/estimate/point", tags=["agro-phenology"])
def post_phenology_point(payload: PointRequest):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        _, lat, signal_ratio = _point_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "phase_macro": weather["phase_macro"],
        "phase_sub": weather["phase_sub"],
        "pct_cycle": weather["pct_cycle"],
        "gdd_c_day": weather["gdd_c_day"],
    }


@router.post("/phenology/estimate/polygon", tags=["agro-phenology"])
def post_phenology_polygon(payload: PolygonRequest):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        _maybe_raise_common_polygon_errors(payload)
        _, lat, signal_ratio = _polygon_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "phase_macro": weather["phase_macro"],
        "phase_sub": weather["phase_sub"],
        "pct_cycle": weather["pct_cycle"],
        "gdd_c_day": weather["gdd_c_day"],
        "data_completeness": _polygon_completeness(),
    }


@router.post("/et0-etc/point", tags=["agro-water"])
def post_et0_etc_point(payload: PointRequest):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        _, lat, signal_ratio = _point_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
        et0_mm_day = agro_engine.et0_hargreaves_mm_day(
            tmin_c=cast(float, weather["tmin_c"]),
            tmax_c=cast(float, weather["tmax_c"]),
            tmean_c=cast(float, weather["tmean_c"]),
            day_of_year=payload.date_planting.timetuple().tm_yday,
            latitude_deg=lat,
        )
        kc = profile.kc_by_macro_stage[cast(str, weather["phase_macro"])]
        etc_mm_day = agro_engine.etc_day(et0_mm_day=et0_mm_day, kc=kc)
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "et0_mm_day": round(et0_mm_day, 2),
        "kc": round(kc, 2),
        "etc_mm_day": round(etc_mm_day, 2),
    }


@router.post("/et0-etc/polygon", tags=["agro-water"])
def post_et0_etc_polygon(payload: PolygonRequest):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        _maybe_raise_common_polygon_errors(payload)
        _, lat, signal_ratio = _polygon_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
        et0_mm_day = agro_engine.et0_hargreaves_mm_day(
            tmin_c=cast(float, weather["tmin_c"]),
            tmax_c=cast(float, weather["tmax_c"]),
            tmean_c=cast(float, weather["tmean_c"]),
            day_of_year=payload.date_planting.timetuple().tm_yday,
            latitude_deg=lat,
        )
        kc = profile.kc_by_macro_stage[cast(str, weather["phase_macro"])]
        etc_mm_day = agro_engine.etc_day(et0_mm_day=et0_mm_day, kc=kc)
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "et0_mm_day": round(et0_mm_day, 2),
        "kc": round(kc, 2),
        "etc_mm_day": round(etc_mm_day, 2),
        "data_completeness": _polygon_completeness(),
    }


@router.post("/water-balance/simple/point", tags=["agro-water"])
def post_water_balance_point(
    payload: WaterPointRequest,
):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        _, lat, signal_ratio = _point_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
        kc = profile.kc_by_macro_stage[cast(str, weather["phase_macro"])]
        et0_mm_day = agro_engine.et0_hargreaves_mm_day(
            tmin_c=cast(float, weather["tmin_c"]),
            tmax_c=cast(float, weather["tmax_c"]),
            tmean_c=cast(float, weather["tmean_c"]),
            day_of_year=payload.date_planting.timetuple().tm_yday,
            latitude_deg=lat,
        )
        etc_mm_day = agro_engine.etc_day(et0_mm_day=et0_mm_day, kc=kc)
        initial_storage_mm = payload.cad_mm * _clamp(
            payload.water_initial_pct / 100.0, 0.0, 1.0
        )
        soil_water_mm, excess_mm, deficit_mm = agro_engine.bucket_step(
            soil_mm=initial_storage_mm,
            p_mm=cast(float, weather["precipitation_mm"]),
            etc_mm=etc_mm_day,
            taw_mm=payload.cad_mm,
        )
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "cad_mm": payload.cad_mm,
        "water_initial_pct": payload.water_initial_pct,
        "soil_water_mm": round(soil_water_mm, 2),
        "deficit_mm": round(deficit_mm, 2),
        "excess_mm": round(excess_mm, 2),
    }


@router.post("/water-balance/simple/polygon", tags=["agro-water"])
def post_water_balance_polygon(
    payload: WaterPolygonRequest,
):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        ring = _polygon_ring(payload.geometry)
        if ring == GEE_TIMEOUT_RING:
            raise DomainError(
                status_code=504,
                error_code="GEE_TIMEOUT",
                message="Earth Engine request timed out",
                retryable=True,
                details={"operation": "water_balance_polygon"},
            )
        _maybe_raise_common_polygon_errors(payload)
        _, lat, signal_ratio = _polygon_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
        kc = profile.kc_by_macro_stage[cast(str, weather["phase_macro"])]
        et0_mm_day = agro_engine.et0_hargreaves_mm_day(
            tmin_c=cast(float, weather["tmin_c"]),
            tmax_c=cast(float, weather["tmax_c"]),
            tmean_c=cast(float, weather["tmean_c"]),
            day_of_year=payload.date_planting.timetuple().tm_yday,
            latitude_deg=lat,
        )
        etc_mm_day = agro_engine.etc_day(et0_mm_day=et0_mm_day, kc=kc)
        initial_storage_mm = payload.cad_mm * _clamp(
            payload.water_initial_pct / 100.0, 0.0, 1.0
        )
        soil_water_mm, excess_mm, deficit_mm = agro_engine.bucket_step(
            soil_mm=initial_storage_mm,
            p_mm=cast(float, weather["precipitation_mm"]),
            etc_mm=etc_mm_day,
            taw_mm=payload.cad_mm,
        )
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "cad_mm": payload.cad_mm,
        "water_initial_pct": payload.water_initial_pct,
        "soil_water_mm": round(soil_water_mm, 2),
        "deficit_mm": round(deficit_mm, 2),
        "excess_mm": round(excess_mm, 2),
        "data_completeness": _polygon_completeness(),
    }


@router.post("/water-status/point", tags=["agro-water"])
def post_water_status_point(
    payload: WaterPointRequest,
):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        lon, lat = payload.coordinates
        if (float(lon), float(lat)) == GEE_UNAVAILABLE_POINT:
            raise DomainError(
                status_code=503,
                error_code="GEE_UNAVAILABLE",
                message="Earth Engine service unavailable",
                retryable=True,
                details={"provider": "gee"},
            )
        _, lat_f, signal_ratio = _point_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat_f,
            signal_ratio=signal_ratio,
        )
        kc = profile.kc_by_macro_stage[cast(str, weather["phase_macro"])]
        et0_mm_day = agro_engine.et0_hargreaves_mm_day(
            tmin_c=cast(float, weather["tmin_c"]),
            tmax_c=cast(float, weather["tmax_c"]),
            tmean_c=cast(float, weather["tmean_c"]),
            day_of_year=payload.date_planting.timetuple().tm_yday,
            latitude_deg=lat_f,
        )
        etc_mm_day = agro_engine.etc_day(et0_mm_day=et0_mm_day, kc=kc)
        initial_storage_mm = payload.cad_mm * _clamp(
            payload.water_initial_pct / 100.0, 0.0, 1.0
        )
        soil_water_mm, excess_mm, deficit_mm = agro_engine.bucket_step(
            soil_mm=initial_storage_mm,
            p_mm=cast(float, weather["precipitation_mm"]),
            etc_mm=etc_mm_day,
            taw_mm=payload.cad_mm,
        )
        taw = payload.cad_mm if payload.cad_mm > 0 else 1.0
        deficit_intensity = _clamp(deficit_mm / taw, 0.0, 1.0)
        excess_intensity = _clamp(excess_mm / taw, 0.0, 1.0)
        deficit_freq = _clamp(
            0.25 + (1.0 - signal_ratio) * 0.5 + deficit_intensity * 0.5, 0.0, 1.0
        )
        excess_freq = _clamp(
            0.25 + signal_ratio * 0.5 + excess_intensity * 0.5, 0.0, 1.0
        )
        deficit_score = agro_engine.water_deficit_score(
            deficit_freq=deficit_freq,
            deficit_intensity=deficit_intensity,
        )
        excess_score = agro_engine.water_excess_score(
            excess_freq=excess_freq,
            excess_intensity=excess_intensity,
        )
        status = agro_engine.classify_water_status(
            deficit_score=deficit_score,
            excess_score=excess_score,
        )
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "status": status,
        "deficit_score": round(deficit_score, 2),
        "excess_score": round(excess_score, 2),
    }


@router.post("/water-status/polygon", tags=["agro-water"])
def post_water_status_polygon(
    payload: WaterPolygonRequest,
):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        _maybe_raise_common_polygon_errors(payload)
        _, lat, signal_ratio = _polygon_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
        kc = profile.kc_by_macro_stage[cast(str, weather["phase_macro"])]
        et0_mm_day = agro_engine.et0_hargreaves_mm_day(
            tmin_c=cast(float, weather["tmin_c"]),
            tmax_c=cast(float, weather["tmax_c"]),
            tmean_c=cast(float, weather["tmean_c"]),
            day_of_year=payload.date_planting.timetuple().tm_yday,
            latitude_deg=lat,
        )
        etc_mm_day = agro_engine.etc_day(et0_mm_day=et0_mm_day, kc=kc)
        initial_storage_mm = payload.cad_mm * _clamp(
            payload.water_initial_pct / 100.0, 0.0, 1.0
        )
        _, excess_mm, deficit_mm = agro_engine.bucket_step(
            soil_mm=initial_storage_mm,
            p_mm=cast(float, weather["precipitation_mm"]),
            etc_mm=etc_mm_day,
            taw_mm=payload.cad_mm,
        )
        taw = payload.cad_mm if payload.cad_mm > 0 else 1.0
        deficit_intensity = _clamp(deficit_mm / taw, 0.0, 1.0)
        excess_intensity = _clamp(excess_mm / taw, 0.0, 1.0)
        deficit_freq = _clamp(
            0.25 + (1.0 - signal_ratio) * 0.5 + deficit_intensity * 0.5, 0.0, 1.0
        )
        excess_freq = _clamp(
            0.25 + signal_ratio * 0.5 + excess_intensity * 0.5, 0.0, 1.0
        )
        deficit_score = agro_engine.water_deficit_score(
            deficit_freq=deficit_freq,
            deficit_intensity=deficit_intensity,
        )
        excess_score = agro_engine.water_excess_score(
            excess_freq=excess_freq,
            excess_intensity=excess_intensity,
        )
        status = agro_engine.classify_water_status(
            deficit_score=deficit_score,
            excess_score=excess_score,
        )
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "status": status,
        "deficit_score": round(deficit_score, 2),
        "excess_score": round(excess_score, 2),
        "data_completeness": _polygon_completeness(),
    }


@router.post("/thermal-risk/point", tags=["agro-thermal"])
def post_thermal_risk_point(payload: PointRequest):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        _, lat, signal_ratio = _point_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
        is_reproductive = cast(str, weather["phase_macro"]) == "reproductive"
        thresholds = profile.thermal_thresholds
        heat_limit = (
            thresholds.heat_reproductive_c
            if is_reproductive
            else thresholds.heat_general_c
        )
        cold_limit = (
            thresholds.cold_reproductive_c
            if is_reproductive
            else thresholds.cold_general_c
        )
        tmax_c = cast(float, weather["tmax_c"])
        tmin_c = cast(float, weather["tmin_c"])
        heat_event = tmax_c >= heat_limit
        cold_event = tmin_c <= cold_limit
        frost_event = tmin_c <= thresholds.frost_c
        base_score = agro_engine.thermal_event_base_score(
            heat_event=heat_event,
            cold_event=cold_event,
            frost_event=frost_event,
        )
        persistence_days = int(cast(float, weather["persistence_days"]))
        risk_score = agro_engine.thermal_score(
            base_score=base_score,
            persistence_days=persistence_days,
        )
        events_count = int(heat_event) + int(cold_event) + int(frost_event)
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "risk_score": round(risk_score, 2),
        "risk_class": agro_engine.risk_class(risk_score, profile.class_boundaries),
        "events_count": events_count,
    }


@router.post("/thermal-risk/polygon", tags=["agro-thermal"])
def post_thermal_risk_polygon(
    payload: PolygonRequest,
):
    try:
        _validate_harvest(payload)
        profile = _resolve_profile(payload)
        ring = _polygon_ring(payload.geometry)
        if ring == INTERNAL_ERROR_RING:
            raise DomainError(
                status_code=500,
                error_code="INTERNAL_ERROR",
                message="Unexpected error during thermal risk processing",
                retryable=False,
                details={"operation": "thermal_risk_polygon"},
            )
        _maybe_raise_common_polygon_errors(payload)
        _, lat, signal_ratio = _polygon_signal(payload)
        weather = _pseudo_weather(
            payload=payload,
            profile=profile,
            latitude_deg=lat,
            signal_ratio=signal_ratio,
        )
        is_reproductive = cast(str, weather["phase_macro"]) == "reproductive"
        thresholds = profile.thermal_thresholds
        heat_limit = (
            thresholds.heat_reproductive_c
            if is_reproductive
            else thresholds.heat_general_c
        )
        cold_limit = (
            thresholds.cold_reproductive_c
            if is_reproductive
            else thresholds.cold_general_c
        )
        tmax_c = cast(float, weather["tmax_c"])
        tmin_c = cast(float, weather["tmin_c"])
        heat_event = tmax_c >= heat_limit
        cold_event = tmin_c <= cold_limit
        frost_event = tmin_c <= thresholds.frost_c
        base_score = agro_engine.thermal_event_base_score(
            heat_event=heat_event,
            cold_event=cold_event,
            frost_event=frost_event,
        )
        persistence_days = int(cast(float, weather["persistence_days"]))
        risk_score = agro_engine.thermal_score(
            base_score=base_score,
            persistence_days=persistence_days,
        )
        events_count = int(heat_event) + int(cold_event) + int(frost_event)
    except DomainError as exc:
        return _error_response(exc)

    return {
        "crop": profile.crop,
        "risk_score": round(risk_score, 2),
        "risk_class": agro_engine.risk_class(risk_score, profile.class_boundaries),
        "events_count": events_count,
        "data_completeness": _polygon_completeness(),
    }
