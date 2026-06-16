import math
from collections.abc import Sequence
from typing import cast

from agro_gee_api.services.agro_profiles import (
    ClassBoundary,
    CycleRange,
    get_crop_profile,
)


def gdd_day(tmean_c: float, tbase_c: float, tcap_c: float) -> float:
    effective_tmean = max(tbase_c, min(tmean_c, tcap_c))
    return effective_tmean - tbase_c


def resolve_hybrid_phase(by_cycle_order: int, by_gdd_order: int) -> int:
    return min(by_cycle_order, by_gdd_order)


def phase_by_cycle(crop: str, pct_cycle: float) -> CycleRange:
    profile = get_crop_profile(crop=crop)
    last_index = len(profile.cycle_ranges) - 1

    for index, cycle_range in enumerate(profile.cycle_ranges):
        if cycle_range.start_pct <= pct_cycle < cycle_range.end_pct:
            return cycle_range
        if index == last_index and pct_cycle == cycle_range.end_pct:
            return cycle_range

    raise ValueError(f"pct_cycle out of range for crop {crop}: {pct_cycle}")


def kelvin_to_celsius(kelvin: float) -> float:
    return kelvin - 273.15


def meters_to_mm(depth_m: float) -> float:
    return depth_m * 1000.0


def centroid_latitude_deg(
    polygon_lon_lat: Sequence[Sequence[float]] | Sequence[Sequence[Sequence[float]]],
) -> float:
    if not polygon_lon_lat:
        raise ValueError("polygon_lon_lat must not be empty")

    ring: Sequence[Sequence[float]] = cast(Sequence[Sequence[float]], polygon_lon_lat)
    if (
        polygon_lon_lat
        and polygon_lon_lat[0]
        and isinstance(polygon_lon_lat[0][0], (list, tuple))
    ):
        ring = cast(Sequence[Sequence[float]], polygon_lon_lat[0])

    if len(ring) >= 2 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if not ring:
        raise ValueError("polygon_lon_lat ring must contain coordinates")

    return sum(point[1] for point in ring) / len(ring)


def extraterrestrial_radiation_mm_eq(day_of_year: int, latitude_deg: float) -> float:
    return (
        extraterrestrial_radiation_mj_m2_day(
            day_of_year=day_of_year, latitude_deg=latitude_deg
        )
        / 2.45
    )


def extraterrestrial_radiation_mj_m2_day(
    day_of_year: int, latitude_deg: float
) -> float:
    phi = math.radians(latitude_deg)
    dr = 1.0 + 0.033 * math.cos((2.0 * math.pi / 365.0) * day_of_year)
    solar_declination = 0.409 * math.sin((2.0 * math.pi / 365.0) * day_of_year - 1.39)

    ws_arg = -math.tan(phi) * math.tan(solar_declination)
    ws_arg = max(-1.0, min(1.0, ws_arg))
    sunset_hour_angle = math.acos(ws_arg)

    ra_mj_m2_day = (
        (24.0 * 60.0 / math.pi)
        * 0.0820
        * dr
        * (
            sunset_hour_angle * math.sin(phi) * math.sin(solar_declination)
            + math.cos(phi) * math.cos(solar_declination) * math.sin(sunset_hour_angle)
        )
    )
    return ra_mj_m2_day


def et0_hargreaves_mm_day(
    tmin_c: float,
    tmax_c: float,
    tmean_c: float,
    *,
    ra_mm_eq: float | None = None,
    day_of_year: int | None = None,
    latitude_deg: float | None = None,
) -> float:
    if ra_mm_eq is not None:
        ra_mj_m2_day = ra_mm_eq * 2.45
    else:
        if day_of_year is None or latitude_deg is None:
            raise ValueError("Provide ra_mm_eq or both day_of_year and latitude_deg")
        ra_mj_m2_day = extraterrestrial_radiation_mj_m2_day(
            day_of_year=day_of_year,
            latitude_deg=latitude_deg,
        )

    t_range = max(tmax_c - tmin_c, 0.0)
    return 0.0023 * (tmean_c + 17.8) * math.sqrt(t_range) * ra_mj_m2_day


def etc_day(et0_mm_day: float, kc: float) -> float:
    return et0_mm_day * kc


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def bucket_step(
    soil_mm: float, p_mm: float, etc_mm: float, taw_mm: float
) -> tuple[float, float, float]:
    balance_mm = soil_mm + p_mm - etc_mm
    next_soil_mm = _clamp(balance_mm, 0.0, taw_mm)
    excess_mm = max(balance_mm - taw_mm, 0.0)
    deficit_mm = max(-balance_mm, 0.0)
    return (next_soil_mm, excess_mm, deficit_mm)


def _weighted_water_score(freq: float, intensity: float) -> float:
    return _clamp(0.6 * freq + 0.4 * intensity, 0.0, 1.0)


def water_deficit_score(deficit_freq: float, deficit_intensity: float) -> float:
    return _weighted_water_score(freq=deficit_freq, intensity=deficit_intensity)


def water_excess_score(excess_freq: float, excess_intensity: float) -> float:
    return _weighted_water_score(freq=excess_freq, intensity=excess_intensity)


def classify_water_status(deficit_score: float, excess_score: float) -> str:
    if deficit_score >= 0.45 and deficit_score >= excess_score:
        return "deficit"
    if excess_score >= 0.45 and excess_score > deficit_score:
        return "excesso"
    return "adequado"


def thermal_event_base_score(
    *, heat_event: bool, cold_event: bool, frost_event: bool
) -> float:
    if frost_event:
        return 0.70
    if heat_event or cold_event:
        return 0.40
    return 0.0


def thermal_persistence_bonus(persistence_days: int) -> float:
    bonus = 0.0
    if persistence_days >= 3:
        bonus += 0.15
    if persistence_days >= 5:
        bonus += 0.15
    return bonus


def thermal_score(base_score: float, persistence_days: int) -> float:
    return _clamp(base_score + thermal_persistence_bonus(persistence_days), 0.0, 1.0)


def risk_class(
    score: float, class_boundaries: Sequence[ClassBoundary] | None = None
) -> str:
    if class_boundaries is None:
        if score < 0.33:
            return "baixo"
        if score <= 0.66:
            return "medio"
        return "alto"

    for index, boundary in enumerate(class_boundaries):
        lower_match = boundary.min_value is None or score >= boundary.min_value
        if boundary.max_value is None:
            upper_match = True
        else:
            next_min = None
            if index + 1 < len(class_boundaries):
                next_min = class_boundaries[index + 1].min_value
            if next_min == boundary.max_value:
                upper_match = score < boundary.max_value
            else:
                upper_match = score <= boundary.max_value

        if lower_match and upper_match:
            return boundary.label

    if not class_boundaries:
        raise ValueError("class_boundaries must not be empty")

    if score < (class_boundaries[0].min_value or float("-inf")):
        return class_boundaries[0].label
    return class_boundaries[-1].label
