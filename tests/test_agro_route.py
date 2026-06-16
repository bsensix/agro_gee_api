from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from agro_gee_api.main import app
from agro_gee_api.services.agro_profiles import ClassBoundary, get_crop_profile


POINT_BASE_PAYLOAD = {
    "crop": "soybean",
    "date_planting": "2026-10-15",
    "cycle_days": 120,
    "coordinates": [-47.8825, -15.7942],
    "profile_version": "v1_default",
}

POLYGON_BASE_PAYLOAD = {
    "crop": "soybean",
    "date_planting": "2026-10-15",
    "cycle_days": 120,
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [-47.91, -15.78],
                [-47.86, -15.78],
                [-47.86, -15.82],
                [-47.91, -15.82],
                [-47.91, -15.78],
            ]
        ],
    },
    "profile_version": "v1_default",
}


PHENOLOGY_POINT_PAYLOAD = {
    **POINT_BASE_PAYLOAD,
    "date_harvest": "2027-02-12",
}

PHENOLOGY_POLYGON_PAYLOAD = {
    **POLYGON_BASE_PAYLOAD,
    "date_harvest": "2027-02-12",
}

ET0_ETC_POINT_PAYLOAD = dict(POINT_BASE_PAYLOAD)
ET0_ETC_POLYGON_PAYLOAD = dict(POLYGON_BASE_PAYLOAD)

WATER_BALANCE_POINT_PAYLOAD = {
    **POINT_BASE_PAYLOAD,
    "cad_mm": 120.0,
    "water_initial_pct": 50.0,
}

WATER_BALANCE_POLYGON_PAYLOAD = {
    **POLYGON_BASE_PAYLOAD,
    "cad_mm": 120.0,
    "water_initial_pct": 50.0,
}

WATER_STATUS_POINT_PAYLOAD = {
    **POINT_BASE_PAYLOAD,
    "cad_mm": 120.0,
    "water_initial_pct": 50.0,
}

WATER_STATUS_POLYGON_PAYLOAD = {
    **POLYGON_BASE_PAYLOAD,
    "cad_mm": 120.0,
    "water_initial_pct": 50.0,
}

THERMAL_RISK_POINT_PAYLOAD = dict(POINT_BASE_PAYLOAD)
THERMAL_RISK_POLYGON_PAYLOAD = dict(POLYGON_BASE_PAYLOAD)

NO_DATA_POLYGON_RING = [
    [-48.25, -16.25],
    [-48.10, -16.25],
    [-48.10, -16.45],
    [-48.25, -16.45],
    [-48.25, -16.25],
]

GEE_TIMEOUT_POLYGON_RING = [
    [-45.80, -12.20],
    [-45.65, -12.20],
    [-45.65, -12.35],
    [-45.80, -12.35],
    [-45.80, -12.20],
]

INTERNAL_ERROR_POLYGON_RING = [
    [-54.70, -13.00],
    [-54.45, -13.00],
    [-54.45, -13.25],
    [-54.70, -13.25],
    [-54.70, -13.00],
]

NUMERIC_FIELDS = {
    "pct_cycle",
    "gdd_c_day",
    "et0_mm_day",
    "kc",
    "etc_mm_day",
    "cad_mm",
    "water_initial_pct",
    "soil_water_mm",
    "deficit_mm",
    "excess_mm",
    "deficit_score",
    "excess_score",
    "risk_score",
}

STRING_FIELDS = {"crop", "phase_macro", "phase_sub", "status", "risk_class"}

INTEGER_FIELDS = {"events_count"}


def polygon_geometry(ring: list[list[float]]) -> dict[str, object]:
    return {"type": "Polygon", "coordinates": [ring]}


def with_polygon_geometry(
    base_payload: dict[str, object], ring: list[list[float]]
) -> dict[str, object]:
    return {
        **base_payload,
        "geometry": polygon_geometry(ring),
    }


def assert_success_contract_field_types(
    body: dict[str, object], required_keys: set[str]
) -> None:
    assert isinstance(body, dict)
    for key in required_keys:
        assert key in body
        value = body[key]
        assert value is not None
        if key in STRING_FIELDS:
            assert isinstance(value, str)
            assert value
        elif key in INTEGER_FIELDS:
            assert isinstance(value, int)
        elif key in NUMERIC_FIELDS:
            assert isinstance(value, (int, float))


AGRO_OPERATION_PAYLOADS = [
    (
        "/agro/phenology/estimate/point",
        PHENOLOGY_POINT_PAYLOAD,
        {"crop", "phase_macro", "phase_sub", "pct_cycle", "gdd_c_day"},
    ),
    (
        "/agro/phenology/estimate/polygon",
        PHENOLOGY_POLYGON_PAYLOAD,
        {"crop", "phase_macro", "phase_sub", "pct_cycle", "gdd_c_day"},
    ),
    (
        "/agro/et0-etc/point",
        ET0_ETC_POINT_PAYLOAD,
        {"crop", "et0_mm_day", "kc", "etc_mm_day"},
    ),
    (
        "/agro/et0-etc/polygon",
        ET0_ETC_POLYGON_PAYLOAD,
        {"crop", "et0_mm_day", "kc", "etc_mm_day"},
    ),
    (
        "/agro/water-balance/simple/point",
        WATER_BALANCE_POINT_PAYLOAD,
        {
            "crop",
            "cad_mm",
            "water_initial_pct",
            "soil_water_mm",
            "deficit_mm",
            "excess_mm",
        },
    ),
    (
        "/agro/water-balance/simple/polygon",
        WATER_BALANCE_POLYGON_PAYLOAD,
        {
            "crop",
            "cad_mm",
            "water_initial_pct",
            "soil_water_mm",
            "deficit_mm",
            "excess_mm",
        },
    ),
    (
        "/agro/water-status/point",
        WATER_STATUS_POINT_PAYLOAD,
        {"crop", "status", "deficit_score", "excess_score"},
    ),
    (
        "/agro/water-status/polygon",
        WATER_STATUS_POLYGON_PAYLOAD,
        {"crop", "status", "deficit_score", "excess_score"},
    ),
    (
        "/agro/thermal-risk/point",
        THERMAL_RISK_POINT_PAYLOAD,
        {"crop", "risk_score", "risk_class", "events_count"},
    ),
    (
        "/agro/thermal-risk/polygon",
        THERMAL_RISK_POLYGON_PAYLOAD,
        {"crop", "risk_score", "risk_class", "events_count"},
    ),
]

POLYGON_COMPLETENESS_CASES = [
    ("/agro/phenology/estimate/polygon", PHENOLOGY_POLYGON_PAYLOAD),
    ("/agro/et0-etc/polygon", ET0_ETC_POLYGON_PAYLOAD),
    ("/agro/water-balance/simple/polygon", WATER_BALANCE_POLYGON_PAYLOAD),
    ("/agro/water-status/polygon", WATER_STATUS_POLYGON_PAYLOAD),
    ("/agro/thermal-risk/polygon", THERMAL_RISK_POLYGON_PAYLOAD),
]


@pytest.mark.parametrize(("path", "payload", "required_keys"), AGRO_OPERATION_PAYLOADS)
def test_agro_endpoint_pairs_return_family_success_contract_shape(
    path: str,
    payload: dict[str, object],
    required_keys: set[str],
) -> None:
    client = TestClient(app)

    response = client.post(path, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["crop"] == payload["crop"]
    assert_success_contract_field_types(body=body, required_keys=required_keys)


@pytest.mark.parametrize(("path", "payload"), POLYGON_COMPLETENESS_CASES)
def test_agro_polygon_endpoints_return_completeness_fields(
    path: str,
    payload: dict[str, object],
) -> None:
    client = TestClient(app)

    response = client.post(path, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert set(body["data_completeness"]) == {
        "valid_days",
        "no_data_days",
        "valid_ratio",
    }
    completeness = body["data_completeness"]
    assert completeness["valid_ratio"] >= 0.60
    assert isinstance(completeness["valid_days"], int)
    assert isinstance(completeness["no_data_days"], int)


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/agro/phenology/estimate/polygon",
            with_polygon_geometry(PHENOLOGY_POLYGON_PAYLOAD, NO_DATA_POLYGON_RING),
        ),
        (
            "/agro/water-balance/simple/polygon",
            with_polygon_geometry(WATER_BALANCE_POLYGON_PAYLOAD, NO_DATA_POLYGON_RING),
        ),
        (
            "/agro/thermal-risk/polygon",
            with_polygon_geometry(THERMAL_RISK_POLYGON_PAYLOAD, NO_DATA_POLYGON_RING),
        ),
    ],
)
def test_agro_polygon_returns_422_no_data_when_valid_ratio_below_threshold(
    path: str,
    payload: dict[str, object],
) -> None:
    client = TestClient(app)
    response = client.post(path, json=payload)

    assert response.status_code == 422
    assert response.json()["error_code"] == "NO_DATA"
    assert response.json()["details"]["valid_ratio"] < 0.60


@pytest.mark.parametrize(
    ("path", "payload", "status_code", "error_code"),
    [
        (
            "/agro/thermal-risk/point",
            {
                "crop": "soybean",
                "date_planting": "2026-12-20",
                "cycle_days": 120,
                "date_harvest": "2026-10-15",
                "coordinates": [-47.8825, -15.7942],
            },
            400,
            "INVALID_REQUEST",
        ),
        (
            "/agro/phenology/estimate/polygon",
            {
                "crop": "soybean",
                "date_planting": "2026-10-15",
                "cycle_days": 120,
                "geometry": polygon_geometry(NO_DATA_POLYGON_RING),
            },
            422,
            "NO_DATA",
        ),
        (
            "/agro/water-status/point",
            {
                "crop": "corn",
                "date_planting": "2026-09-20",
                "cycle_days": 120,
                "coordinates": [179.9999, 89.9999],
                "cad_mm": 120.0,
                "water_initial_pct": 50.0,
            },
            503,
            "GEE_UNAVAILABLE",
        ),
        (
            "/agro/water-balance/simple/polygon",
            {
                "crop": "corn",
                "date_planting": "2026-09-20",
                "cycle_days": 120,
                "geometry": polygon_geometry(GEE_TIMEOUT_POLYGON_RING),
                "cad_mm": 120.0,
                "water_initial_pct": 50.0,
            },
            504,
            "GEE_TIMEOUT",
        ),
        (
            "/agro/thermal-risk/polygon",
            {
                "crop": "cotton",
                "date_planting": "2026-10-01",
                "cycle_days": 120,
                "geometry": polygon_geometry(INTERNAL_ERROR_POLYGON_RING),
            },
            500,
            "INTERNAL_ERROR",
        ),
    ],
)
def test_agro_error_mapping_contract(
    path: str,
    payload: dict[str, object],
    status_code: int,
    error_code: str,
) -> None:
    client = TestClient(app)

    response = client.post(path, json=payload)

    assert response.status_code == status_code
    body = response.json()
    assert body["error_code"] == error_code
    assert "message" in body
    assert "retryable" in body
    assert "details" in body


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/agro/phenology/estimate/point",
            {
                **PHENOLOGY_POINT_PAYLOAD,
                "coordinates": [-47.8825],
            },
        ),
        (
            "/agro/et0-etc/point",
            {
                **ET0_ETC_POINT_PAYLOAD,
                "coordinates": [-47.8825, -15.7942, 10.0],
            },
        ),
        (
            "/agro/water-status/point",
            {
                **WATER_STATUS_POINT_PAYLOAD,
                "coordinates": ["invalid", -15.7942],
            },
        ),
    ],
)
def test_agro_point_endpoints_reject_invalid_coordinates_shape_and_type(
    path: str,
    payload: dict[str, object],
) -> None:
    client = TestClient(app)

    response = client.post(path, json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/agro/phenology/estimate/polygon",
            {
                **PHENOLOGY_POLYGON_PAYLOAD,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[["invalid", -15.78], [-47.86, -15.78]]],
                },
            },
        ),
        (
            "/agro/water-balance/simple/polygon",
            {
                **WATER_BALANCE_POLYGON_PAYLOAD,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[-47.91], [-47.86, -15.78]]],
                },
            },
        ),
    ],
)
def test_agro_polygon_endpoints_map_invalid_geometry_coordinates_to_client_error(
    path: str,
    payload: dict[str, object],
) -> None:
    client = TestClient(app)

    response = client.post(path, json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "INVALID_REQUEST"


def test_agro_phenology_point_output_changes_when_cycle_days_changes() -> None:
    client = TestClient(app)

    short_cycle = {
        **PHENOLOGY_POINT_PAYLOAD,
        "cycle_days": 90,
    }
    long_cycle = {
        **PHENOLOGY_POINT_PAYLOAD,
        "cycle_days": 180,
    }

    short_response = client.post("/agro/phenology/estimate/point", json=short_cycle)
    long_response = client.post("/agro/phenology/estimate/point", json=long_cycle)

    assert short_response.status_code == 200
    assert long_response.status_code == 200
    assert short_response.json()["pct_cycle"] != long_response.json()["pct_cycle"]


def test_agro_routes_map_unsupported_profile_version_to_invalid_request() -> None:
    client = TestClient(app)

    response = client.post(
        "/agro/et0-etc/point",
        json={
            **ET0_ETC_POINT_PAYLOAD,
            "profile_version": "v2_unknown",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "INVALID_REQUEST"
    assert body["details"]["field"] == "profile_version"


def test_agro_routes_map_unsupported_crop_to_invalid_request() -> None:
    client = TestClient(app)

    response = client.post(
        "/agro/et0-etc/point",
        json={
            **ET0_ETC_POINT_PAYLOAD,
            "crop": "wheat",
        },
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "INVALID_REQUEST"
    assert body["details"]["field"] == "crop"


def test_agro_thermal_risk_uses_profile_taxonomy_labels() -> None:
    client = TestClient(app)

    response = client.post("/agro/thermal-risk/point", json=THERMAL_RISK_POINT_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["risk_class"] in {"baixo", "medio", "alto"}


def test_agro_routes_treat_date_harvest_as_informational_only_for_outputs() -> None:
    client = TestClient(app)

    response_without_harvest = client.post(
        "/agro/phenology/estimate/point",
        json={
            **PHENOLOGY_POINT_PAYLOAD,
            "date_harvest": None,
        },
    )
    response_with_harvest = client.post(
        "/agro/phenology/estimate/point",
        json=PHENOLOGY_POINT_PAYLOAD,
    )

    assert response_without_harvest.status_code == 200
    assert response_with_harvest.status_code == 200
    assert response_without_harvest.json() == response_with_harvest.json()


def test_agro_thermal_risk_classification_uses_selected_profile_boundaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = get_crop_profile(crop="soybean", version="v1_default")
    custom_profile = replace(
        profile,
        class_boundaries=(
            ClassBoundary(label="custom-risk", min_value=None, max_value=None),
        ),
    )
    monkeypatch.setattr(
        "agro_gee_api.routes.agro._resolve_profile",
        lambda payload: custom_profile,
    )
    client = TestClient(app)

    response = client.post(
        "/agro/thermal-risk/point",
        json=THERMAL_RISK_POINT_PAYLOAD,
    )

    assert response.status_code == 200
    assert response.json()["risk_class"] == "custom-risk"
