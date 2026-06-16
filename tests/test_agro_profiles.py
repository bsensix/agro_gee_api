import pytest

from agro_gee_api.services import agro_profiles
from agro_gee_api.services.agro_profiles import ThermalThresholds, get_crop_profile


PROFILE_EXPECTATIONS = {
    "soybean": {
        "tbase_c": 10.0,
        "tcap_c": 30.0,
        "cycle_ranges": [
            ("establishment", 0.0, 10.0),
            ("vegetative", 10.0, 45.0),
            ("reproductive", 45.0, 85.0),
            ("maturation", 85.0, 100.0),
        ],
        "gdd_ranges": [
            ("VE", 0.0, 120.0),
            ("V1-Vn", 120.0, 650.0),
            ("R1-R6", 650.0, 1350.0),
            ("R7-R8", 1350.0, 1700.0),
        ],
        "kc_by_macro_stage": {
            "establishment": 0.45,
            "vegetative": 0.85,
            "reproductive": 1.15,
            "maturation": 0.70,
        },
        "thermal_thresholds": ThermalThresholds(
            heat_general_c=36.0,
            heat_reproductive_c=34.0,
            cold_general_c=12.0,
            cold_reproductive_c=14.0,
            frost_c=2.0,
        ),
        "class_boundaries": [
            ("baixo", None, 0.33),
            ("medio", 0.33, 0.66),
            ("alto", 0.66, None),
        ],
    },
    "corn": {
        "tbase_c": 10.0,
        "tcap_c": 30.0,
        "cycle_ranges": [
            ("establishment", 0.0, 10.0),
            ("vegetative", 10.0, 55.0),
            ("reproductive", 55.0, 88.0),
            ("maturation", 88.0, 100.0),
        ],
        "gdd_ranges": [
            ("VE", 0.0, 110.0),
            ("V1-VT", 110.0, 780.0),
            ("R1-R5", 780.0, 1450.0),
            ("R6", 1450.0, 1800.0),
        ],
        "kc_by_macro_stage": {
            "establishment": 0.40,
            "vegetative": 0.90,
            "reproductive": 1.20,
            "maturation": 0.75,
        },
        "thermal_thresholds": ThermalThresholds(
            heat_general_c=36.0,
            heat_reproductive_c=34.0,
            cold_general_c=10.0,
            cold_reproductive_c=12.0,
            frost_c=2.0,
        ),
        "class_boundaries": [
            ("baixo", None, 0.33),
            ("medio", 0.33, 0.66),
            ("alto", 0.66, None),
        ],
    },
    "cotton": {
        "tbase_c": 15.0,
        "tcap_c": 32.0,
        "cycle_ranges": [
            ("establishment", 0.0, 12.0),
            ("vegetative", 12.0, 45.0),
            ("reproductive", 45.0, 85.0),
            ("maturation", 85.0, 100.0),
        ],
        "gdd_ranges": [
            ("emergence", 0.0, 160.0),
            ("square", 160.0, 780.0),
            ("flowering-boll", 780.0, 1500.0),
            ("opening", 1500.0, 1900.0),
        ],
        "kc_by_macro_stage": {
            "establishment": 0.45,
            "vegetative": 0.85,
            "reproductive": 1.15,
            "maturation": 0.70,
        },
        "thermal_thresholds": ThermalThresholds(
            heat_general_c=38.0,
            heat_reproductive_c=36.0,
            cold_general_c=15.0,
            cold_reproductive_c=16.0,
            frost_c=2.0,
        ),
        "class_boundaries": [
            ("baixo", None, 0.33),
            ("medio", 0.33, 0.66),
            ("alto", 0.66, None),
        ],
    },
}


PROFILE_CASES = [
    pytest.param(crop, expected, id=crop)
    for crop, expected in PROFILE_EXPECTATIONS.items()
]


@pytest.mark.parametrize(
    ("crop", "expected"),
    PROFILE_CASES,
)
def test_v1_profiles_have_expected_temperature_limits(
    crop: str, expected: dict[str, object]
) -> None:
    profile = get_crop_profile(crop=crop, version="v1_default")
    assert profile.tbase_c == expected["tbase_c"]
    assert profile.tcap_c == expected["tcap_c"]


@pytest.mark.parametrize(
    ("crop", "expected"),
    PROFILE_CASES,
)
def test_v1_profiles_have_expected_cycle_ranges(
    crop: str, expected: dict[str, object]
) -> None:
    profile = get_crop_profile(crop=crop, version="v1_default")
    assert [
        (r.macro, r.start_pct, r.end_pct) for r in profile.cycle_ranges
    ] == expected["cycle_ranges"]


@pytest.mark.parametrize(
    ("crop", "expected"),
    PROFILE_CASES,
)
def test_v1_profiles_have_expected_gdd_ranges(
    crop: str, expected: dict[str, object]
) -> None:
    profile = get_crop_profile(crop=crop, version="v1_default")
    assert [(r.sub, r.start_gdd, r.end_gdd) for r in profile.gdd_ranges] == expected[
        "gdd_ranges"
    ]


@pytest.mark.parametrize(
    ("crop", "expected"),
    PROFILE_CASES,
)
def test_v1_profiles_have_expected_kc_by_macro_stage(
    crop: str, expected: dict[str, object]
) -> None:
    profile = get_crop_profile(crop=crop, version="v1_default")
    assert profile.kc_by_macro_stage == expected["kc_by_macro_stage"]


@pytest.mark.parametrize(
    ("crop", "expected"),
    PROFILE_CASES,
)
def test_v1_profiles_have_expected_thermal_thresholds(
    crop: str, expected: dict[str, object]
) -> None:
    profile = get_crop_profile(crop=crop, version="v1_default")
    assert profile.thermal_thresholds == expected["thermal_thresholds"]


@pytest.mark.parametrize(
    ("crop", "expected"),
    PROFILE_CASES,
)
def test_v1_profiles_have_expected_class_boundaries(
    crop: str, expected: dict[str, object]
) -> None:
    profile = get_crop_profile(crop=crop, version="v1_default")
    assert [
        (b.label, b.min_value, b.max_value) for b in profile.class_boundaries
    ] == expected["class_boundaries"]


def test_registry_containers_are_immutable() -> None:
    with pytest.raises(TypeError):
        agro_profiles._V1_DEFAULT_PROFILES["new-crop"] = get_crop_profile(
            crop="soybean"
        )

    with pytest.raises(TypeError):
        agro_profiles._PROFILE_REGISTRY["v2"] = agro_profiles._V1_DEFAULT_PROFILES


def test_get_crop_profile_requires_keyword_for_crop() -> None:
    with pytest.raises(TypeError):
        get_crop_profile("soybean")
