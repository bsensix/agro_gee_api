from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class CycleRange:
    macro: str
    start_pct: float
    end_pct: float


@dataclass(frozen=True)
class GDDRange:
    sub: str
    start_gdd: float
    end_gdd: float


@dataclass(frozen=True)
class ThermalThresholds:
    heat_general_c: float
    heat_reproductive_c: float
    cold_general_c: float
    cold_reproductive_c: float
    frost_c: float


@dataclass(frozen=True)
class ClassBoundary:
    label: str
    min_value: float | None
    max_value: float | None


@dataclass(frozen=True)
class CropProfile:
    crop: str
    version: str
    tbase_c: float
    tcap_c: float
    cycle_ranges: tuple[CycleRange, ...]
    gdd_ranges: tuple[GDDRange, ...]
    kc_by_macro_stage: Mapping[str, float]
    thermal_thresholds: ThermalThresholds
    class_boundaries: tuple[ClassBoundary, ...]


_V1_CLASS_BOUNDARIES = (
    ClassBoundary(label="baixo", min_value=None, max_value=0.33),
    ClassBoundary(label="medio", min_value=0.33, max_value=0.66),
    ClassBoundary(label="alto", min_value=0.66, max_value=None),
)


_V1_DEFAULT_PROFILES: Mapping[str, CropProfile] = MappingProxyType(
    {
        "soybean": CropProfile(
            crop="soybean",
            version="v1_default",
            tbase_c=10.0,
            tcap_c=30.0,
            cycle_ranges=(
                CycleRange(macro="establishment", start_pct=0.0, end_pct=10.0),
                CycleRange(macro="vegetative", start_pct=10.0, end_pct=45.0),
                CycleRange(macro="reproductive", start_pct=45.0, end_pct=85.0),
                CycleRange(macro="maturation", start_pct=85.0, end_pct=100.0),
            ),
            gdd_ranges=(
                GDDRange(sub="VE", start_gdd=0.0, end_gdd=120.0),
                GDDRange(sub="V1-Vn", start_gdd=120.0, end_gdd=650.0),
                GDDRange(sub="R1-R6", start_gdd=650.0, end_gdd=1350.0),
                GDDRange(sub="R7-R8", start_gdd=1350.0, end_gdd=1700.0),
            ),
            kc_by_macro_stage=MappingProxyType(
                {
                    "establishment": 0.45,
                    "vegetative": 0.85,
                    "reproductive": 1.15,
                    "maturation": 0.70,
                }
            ),
            thermal_thresholds=ThermalThresholds(
                heat_general_c=36.0,
                heat_reproductive_c=34.0,
                cold_general_c=12.0,
                cold_reproductive_c=14.0,
                frost_c=2.0,
            ),
            class_boundaries=_V1_CLASS_BOUNDARIES,
        ),
        "corn": CropProfile(
            crop="corn",
            version="v1_default",
            tbase_c=10.0,
            tcap_c=30.0,
            cycle_ranges=(
                CycleRange(macro="establishment", start_pct=0.0, end_pct=10.0),
                CycleRange(macro="vegetative", start_pct=10.0, end_pct=55.0),
                CycleRange(macro="reproductive", start_pct=55.0, end_pct=88.0),
                CycleRange(macro="maturation", start_pct=88.0, end_pct=100.0),
            ),
            gdd_ranges=(
                GDDRange(sub="VE", start_gdd=0.0, end_gdd=110.0),
                GDDRange(sub="V1-VT", start_gdd=110.0, end_gdd=780.0),
                GDDRange(sub="R1-R5", start_gdd=780.0, end_gdd=1450.0),
                GDDRange(sub="R6", start_gdd=1450.0, end_gdd=1800.0),
            ),
            kc_by_macro_stage=MappingProxyType(
                {
                    "establishment": 0.40,
                    "vegetative": 0.90,
                    "reproductive": 1.20,
                    "maturation": 0.75,
                }
            ),
            thermal_thresholds=ThermalThresholds(
                heat_general_c=36.0,
                heat_reproductive_c=34.0,
                cold_general_c=10.0,
                cold_reproductive_c=12.0,
                frost_c=2.0,
            ),
            class_boundaries=_V1_CLASS_BOUNDARIES,
        ),
        "cotton": CropProfile(
            crop="cotton",
            version="v1_default",
            tbase_c=15.0,
            tcap_c=32.0,
            cycle_ranges=(
                CycleRange(macro="establishment", start_pct=0.0, end_pct=12.0),
                CycleRange(macro="vegetative", start_pct=12.0, end_pct=45.0),
                CycleRange(macro="reproductive", start_pct=45.0, end_pct=85.0),
                CycleRange(macro="maturation", start_pct=85.0, end_pct=100.0),
            ),
            gdd_ranges=(
                GDDRange(sub="emergence", start_gdd=0.0, end_gdd=160.0),
                GDDRange(sub="square", start_gdd=160.0, end_gdd=780.0),
                GDDRange(sub="flowering-boll", start_gdd=780.0, end_gdd=1500.0),
                GDDRange(sub="opening", start_gdd=1500.0, end_gdd=1900.0),
            ),
            kc_by_macro_stage=MappingProxyType(
                {
                    "establishment": 0.45,
                    "vegetative": 0.85,
                    "reproductive": 1.15,
                    "maturation": 0.70,
                }
            ),
            thermal_thresholds=ThermalThresholds(
                heat_general_c=38.0,
                heat_reproductive_c=36.0,
                cold_general_c=15.0,
                cold_reproductive_c=16.0,
                frost_c=2.0,
            ),
            class_boundaries=_V1_CLASS_BOUNDARIES,
        ),
    }
)


_PROFILE_REGISTRY: Mapping[str, Mapping[str, CropProfile]] = MappingProxyType(
    {"v1_default": _V1_DEFAULT_PROFILES}
)


def get_crop_profile(*, crop: str, version: str = "v1_default") -> CropProfile:
    normalized_version = version.strip().lower()
    normalized_crop = crop.strip().lower()

    try:
        version_profiles = _PROFILE_REGISTRY[normalized_version]
    except KeyError as exc:
        raise ValueError(f"Unsupported profile version: {version}") from exc

    try:
        return version_profiles[normalized_crop]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported crop profile for version {normalized_version}: {crop}"
        ) from exc
