# Agro Endpoints V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `/agro` endpoints for soybean/corn/cotton delivering hybrid phenology, ET0/ETc, simple water balance, water status, and thermal risk from ERA5-Land series.

**Architecture:** Add a dedicated route module (`routes/agro.py`) and keep all formulas in a shared engine (`services/agro_engine.py`) driven by versioned crop parameters (`services/agro_profiles.py`). Route handlers only parse request payloads, call existing ERA5 extraction paths, enforce polygon completeness and error mapping, and return endpoint-specific response contracts.

**Tech Stack:** FastAPI, Pydantic, dataclasses, pytest

---

## Review Resolution

- Prior issue: missing polygon completeness behavior -> addressed in **Task 9 Step 2** and **Task 10 Step 2**.
- Prior issue: missing explicit error taxonomy -> addressed in **Task 9 Step 3** and **Task 10 Step 2**.
- Prior issue: missing OpenAPI examples -> addressed in **Task 10 Step 1** and **Task 11 Step 2**.
- Prior issue: incomplete profile test coverage -> addressed in **Task 1** (expanded full-table assertions for all crops).
- Prior issue: missing ET0/Ra and boundary rules -> addressed in **Tasks 5-8**.
- Prior issue: missing integration and non-regression checks -> addressed in **Task 11** (full suite + dedicated integration file + `/gee` smoke).

## File Structure and Responsibilities

- `agro_gee_api/services/agro_profiles.py`
  - Source of truth for `v1_default` constants: Tbase/Tcap, cycle ranges, GDD ranges, Kc, thermal thresholds, score class boundaries.
- `agro_gee_api/services/agro_engine.py`
  - Pure deterministic calculations for formulas and rules from the approved spec.
- `agro_gee_api/routes/agro.py`
  - `/agro` request/response models, endpoint handlers, mapping to engine calls, polygon completeness checks, and domain error mapping.
- `agro_gee_api/main.py`
  - Router registration and OpenAPI tags.
- `tests/test_agro_profiles.py`
  - Full parameter-contract coverage for all three crops.
- `tests/test_agro_engine.py`
  - Formula/rule unit tests (GDD, ET0/Ra, ETc, phase resolution, water status, thermal risk).
- `tests/test_agro_route.py`
  - API success/error contracts for all endpoint pairs and OpenAPI example checks.
- `tests/test_routes_registration.py`
  - `/agro` route and tag registration checks.
- `tests/test_agro_integration.py`
  - Mocked ERA5-Land scenario tests per crop, aggregate/unit consistency, and `/gee` non-regression smoke checks.

### Task 1: Add failing tests for full `v1_default` crop profile constants

**Files:**
- Create: `tests/test_agro_profiles.py`
- Test: `tests/test_agro_profiles.py`

- [ ] **Step 1: Write failing parameter-table tests for soybean, corn, cotton**

```python
@pytest.mark.parametrize(
    ("crop", "tbase", "tcap"),
    [("soybean", 10.0, 30.0), ("corn", 10.0, 30.0), ("cotton", 15.0, 32.0)],
)
def test_v1_profiles_have_expected_temperature_limits(crop: str, tbase: float, tcap: float) -> None:
    profile = get_crop_profile(crop=crop, version="v1_default")
    assert profile.tbase_c == tbase
    assert profile.tcap_c == tcap


def test_v1_profiles_expose_cycle_gdd_kc_and_thermal_thresholds() -> None:
    soybean = get_crop_profile(crop="soybean", version="v1_default")
    assert [(r.macro, r.start_pct, r.end_pct) for r in soybean.cycle_ranges] == [
        ("establishment", 0.0, 10.0),
        ("vegetative", 10.0, 45.0),
        ("reproductive", 45.0, 85.0),
        ("maturation", 85.0, 100.0),
    ]
    assert [(r.sub, r.start_gdd, r.end_gdd) for r in soybean.gdd_ranges] == [
        ("VE", 0.0, 120.0),
        ("V1-Vn", 120.0, 650.0),
        ("R1-R6", 650.0, 1350.0),
        ("R7-R8", 1350.0, 1700.0),
    ]
    assert soybean.kc_by_macro_stage == {
        "establishment": 0.45,
        "vegetative": 0.85,
        "reproductive": 1.15,
        "maturation": 0.70,
    }
    assert soybean.thermal_thresholds == ThermalThresholds(
        heat_general_c=36.0,
        heat_reproductive_c=34.0,
        cold_general_c=12.0,
        cold_reproductive_c=14.0,
        frost_c=2.0,
    )

    corn = get_crop_profile(crop="corn", version="v1_default")
    assert [(r.macro, r.start_pct, r.end_pct) for r in corn.cycle_ranges] == [
        ("establishment", 0.0, 10.0),
        ("vegetative", 10.0, 55.0),
        ("reproductive", 55.0, 88.0),
        ("maturation", 88.0, 100.0),
    ]
    assert corn.kc_by_macro_stage["reproductive"] == 1.20
    assert corn.thermal_thresholds.heat_general_c == 36.0
    assert corn.thermal_thresholds.heat_reproductive_c == 34.0
    assert corn.thermal_thresholds.cold_general_c == 10.0
    assert corn.thermal_thresholds.cold_reproductive_c == 12.0
    assert corn.thermal_thresholds.frost_c == 2.0

    cotton = get_crop_profile(crop="cotton", version="v1_default")
    assert [(r.macro, r.start_pct, r.end_pct) for r in cotton.cycle_ranges] == [
        ("establishment", 0.0, 12.0),
        ("vegetative", 12.0, 45.0),
        ("reproductive", 45.0, 85.0),
        ("maturation", 85.0, 100.0),
    ]
    assert cotton.kc_by_macro_stage == {
        "establishment": 0.45,
        "vegetative": 0.85,
        "reproductive": 1.15,
        "maturation": 0.70,
    }
    assert cotton.thermal_thresholds == ThermalThresholds(
        heat_general_c=38.0,
        heat_reproductive_c=36.0,
        cold_general_c=15.0,
        cold_reproductive_c=16.0,
        frost_c=2.0,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agro_profiles.py -v`
Expected: FAIL because `agro_profiles.py` does not exist.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_agro_profiles.py
git commit -m "test: add failing v1 crop profile contract coverage"
```

### Task 2: Implement `agro_profiles.py` and pass profile tests

**Files:**
- Create: `agro_gee_api/services/agro_profiles.py`
- Modify: `tests/test_agro_profiles.py`
- Test: `tests/test_agro_profiles.py`

- [ ] **Step 1: Implement immutable profile models and registry lookup**

```python
@dataclass(frozen=True)
class CropProfile:
    crop: str
    tbase_c: float
    tcap_c: float
    cycle_ranges: tuple[PhaseCycleRange, ...]
    gdd_ranges: tuple[PhaseGddRange, ...]
    kc_by_macro_stage: dict[str, float]
    thermal_thresholds: ThermalThresholds
    class_boundaries: ClassBoundaries


def get_crop_profile(*, crop: str, version: str = "v1_default") -> CropProfile:
    ...
```

- [ ] **Step 2: Run tests to verify pass**

Run: `pytest tests/test_agro_profiles.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add agro_gee_api/services/agro_profiles.py tests/test_agro_profiles.py
git commit -m "feat: add versioned agro crop profiles"
```

### Task 3: Add failing unit tests for GDD + phase resolution rules

**Files:**
- Create: `tests/test_agro_engine.py`
- Test: `tests/test_agro_engine.py`

- [ ] **Step 1: Write failing tests for GDD and hybrid-phase conflict rule**

```python
def test_gdd_day_uses_tmean_with_tcap_and_tbase() -> None:
    assert gdd_day(tmean_c=35.0, tbase_c=10.0, tcap_c=30.0) == 20.0


def test_phase_by_cycle_uses_half_open_intervals() -> None:
    assert phase_by_cycle(crop="soybean", pct_cycle=10.0).macro == "vegetative"


def test_resolve_hybrid_phase_returns_most_delayed() -> None:
    delayed = resolve_hybrid_phase(by_cycle_order=3, by_gdd_order=2)
    assert delayed == 2
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_agro_engine.py -k "gdd or phase" -v`
Expected: FAIL with missing module/function errors.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_agro_engine.py
git commit -m "test: add failing gdd and phase-resolution engine tests"
```

### Task 4: Implement GDD and phase functions

**Files:**
- Create: `agro_gee_api/services/agro_engine.py`
- Modify: `tests/test_agro_engine.py`
- Test: `tests/test_agro_engine.py`

- [ ] **Step 1: Implement minimal functions for Task 3 tests**

```python
def gdd_day(*, tmean_c: float, tbase_c: float, tcap_c: float) -> float:
    return max(0.0, min(tmean_c, tcap_c) - tbase_c)


def resolve_hybrid_phase(*, by_cycle_order: int, by_gdd_order: int) -> int:
    return min(by_cycle_order, by_gdd_order)
```

Also implement `phase_by_cycle` and `phase_by_gdd` using `[start, end)` and last range closed.

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_agro_engine.py -k "gdd or phase" -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add agro_gee_api/services/agro_engine.py tests/test_agro_engine.py
git commit -m "feat: implement agro gdd and hybrid phase resolution"
```

### Task 5: Add failing unit tests for ET0/Ra, ETc, and unit conversions

**Files:**
- Modify: `tests/test_agro_engine.py`
- Test: `tests/test_agro_engine.py`

- [ ] **Step 1: Add failing tests for ET0 Hargreaves and conversions**

```python
def test_kelvin_to_celsius_conversion() -> None:
    assert kelvin_to_celsius(300.15) == pytest.approx(27.0)


def test_meters_to_mm_conversion() -> None:
    assert meters_to_mm(0.012) == pytest.approx(12.0)


def test_ra_mm_eq_point_uses_point_latitude() -> None:
    ra = extraterrestrial_radiation_mm_eq(day_of_year=15, latitude_deg=-16.67)
    assert ra > 0


def test_etc_day_is_et0_times_kc() -> None:
    assert etc_day(et0_mm=5.0, kc=1.2) == pytest.approx(6.0)
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_agro_engine.py -k "conversion or ra or etc" -v`
Expected: FAIL for missing implementations.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_agro_engine.py
git commit -m "test: add failing et0 ra etc and unit conversion tests"
```

### Task 6: Implement ET0/Ra and ETc functions

**Files:**
- Modify: `agro_gee_api/services/agro_engine.py`
- Modify: `tests/test_agro_engine.py`
- Test: `tests/test_agro_engine.py`

- [ ] **Step 1: Implement FAO-56 Ra helper + Hargreaves ET0**

```python
def et0_hargreaves_mm_day(*, tmean_c: float, tmin_c: float, tmax_c: float, day_of_year: int, latitude_deg: float) -> float:
    ra_mm_eq = extraterrestrial_radiation_mm_eq(day_of_year=day_of_year, latitude_deg=latitude_deg)
    return 0.0023 * (tmean_c + 17.8) * math.sqrt(max(tmax_c - tmin_c, 0.0)) * ra_mm_eq
```

Implement polygon-latitude helper using centroid latitude.

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_agro_engine.py -k "conversion or ra or etc" -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add agro_gee_api/services/agro_engine.py tests/test_agro_engine.py
git commit -m "feat: implement hargreaves et0 and etc helpers"
```

### Task 7: Add failing unit tests for water-balance, water-status, and thermal-score boundaries

**Files:**
- Modify: `tests/test_agro_engine.py`
- Test: `tests/test_agro_engine.py`

- [ ] **Step 1: Add failing tests for bucket and classification rules**

```python
def test_bucket_step_calculates_soil_excess_deficit() -> None:
    step = bucket_step(soil_prev_mm=95.0, cad_mm=100.0, rain_mm=20.0, etc_mm=5.0)
    assert step.soil_water_mm == 100.0
    assert step.excess_mm == 10.0


def test_water_status_tie_prefers_deficit_when_scores_equal() -> None:
    status = classify_water_status(deficit_score=0.50, excess_score=0.50)
    assert status == "deficit"


def test_thermal_score_gets_bonus_for_run_ge_3_and_ge_5() -> None:
    assert thermal_score(base_score=0.30, max_run_days=3) == pytest.approx(0.45)
    assert thermal_score(base_score=0.30, max_run_days=5) == pytest.approx(0.60)


def test_risk_class_boundaries() -> None:
    assert risk_class(0.32) == "baixo"
    assert risk_class(0.33) == "medio"
    assert risk_class(0.66) == "medio"
    assert risk_class(0.67) == "alto"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_agro_engine.py -k "bucket or water_status or thermal or risk_class" -v`
Expected: FAIL with missing behavior.

- [ ] **Step 3: Commit failing tests**

```bash
git add tests/test_agro_engine.py
git commit -m "test: add failing water and thermal scoring boundary tests"
```

### Task 8: Implement water/thermal algorithms and finish engine unit coverage

**Files:**
- Modify: `agro_gee_api/services/agro_engine.py`
- Modify: `tests/test_agro_engine.py`
- Test: `tests/test_agro_engine.py`

- [ ] **Step 1: Implement formulas exactly as spec**

Implement:
- `bucket_step`
- `compute_water_status_scores` and `classify_water_status`
- thermal event severity + persistence bonus
- class mapping (`baixo < 0.33`, `medio 0.33-0.66`, `alto > 0.66`)

- [ ] **Step 2: Run full engine/profile unit suite**

Run: `pytest tests/test_agro_engine.py tests/test_agro_profiles.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add agro_gee_api/services/agro_engine.py tests/test_agro_engine.py
git commit -m "feat: implement water status and thermal risk scoring rules"
```

### Task 9: Add failing route tests for all endpoint pairs, polygon completeness, and error mapping

**Files:**
- Create: `tests/test_agro_route.py`
- Modify: `tests/test_routes_registration.py`
- Test: `tests/test_agro_route.py`
- Test: `tests/test_routes_registration.py`

- [ ] **Step 1: Write failing success-contract tests for all endpoint pairs**

Add concrete payload assertions for:
- `/agro/phenology/estimate/point|polygon`
- `/agro/et0-etc/point|polygon`
- `/agro/water-balance/simple/point|polygon`
- `/agro/water-status/point|polygon`
- `/agro/thermal-risk/point|polygon`

- [ ] **Step 2: Add failing polygon completeness tests**

```python
def test_polygon_response_includes_data_completeness_fields() -> None:
    body = response.json()
    assert "data_completeness" in body
    assert set(body["data_completeness"]) == {"valid_days", "no_data_days", "valid_ratio"}


def test_polygon_with_valid_ratio_below_0_60_returns_422_no_data() -> None:
    assert response.status_code == 422
    assert response.json()["error_code"] == "NO_DATA"
```

- [ ] **Step 3: Add failing error mapping tests for route envelope**

Validate mapping:
- validation -> `400 INVALID_REQUEST`
- no data -> `422 NO_DATA`
- unavailable -> `503 GEE_UNAVAILABLE`
- timeout -> `504 GEE_TIMEOUT`
- fallback unexpected -> `500 INTERNAL_ERROR`

- [ ] **Step 4: Add failing OpenAPI coverage checks**

In `tests/test_routes_registration.py` assert:
- `/agro/*` operations exist
- allowed tags include `agro-phenology`, `agro-water`, `agro-thermal`
- each agro operation uses exactly one non-generic tag

- [ ] **Step 5: Run tests to verify failure**

Run: `pytest tests/test_agro_route.py tests/test_routes_registration.py -k "agro" -v`
Expected: FAIL (router absent).

- [ ] **Step 6: Commit failing tests**

```bash
git add tests/test_agro_route.py tests/test_routes_registration.py
git commit -m "test: add failing agro route completeness and error-contract coverage"
```

### Task 10: Implement `/agro` route module, OpenAPI examples, and app wiring

**Files:**
- Create: `agro_gee_api/routes/agro.py`
- Modify: `agro_gee_api/main.py`
- Modify: `tests/test_agro_route.py`
- Modify: `tests/test_routes_registration.py`
- Test: `tests/test_agro_route.py`
- Test: `tests/test_routes_registration.py`

- [ ] **Step 1: Implement route models with endpoint examples**

For each endpoint request/response model add `json_schema_extra` examples so OpenAPI exposes concrete payload examples.

- [ ] **Step 2: Implement handlers for 10 endpoints**

Use helpers in the same module to:
- normalize `point`/`polygon` extraction inputs
- compute polygon `valid_ratio`
- enforce `valid_ratio >= 0.60`
- delegate calculations to `agro_engine`
- map errors to `{error_code,message,retryable,details}`

- [ ] **Step 3: Register router and OpenAPI tags in `main.py`**

Add import for `agro_router`, include router, and append agro tag metadata.

- [ ] **Step 4: Run route/OpenAPI tests**

Run: `pytest tests/test_agro_route.py tests/test_routes_registration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agro_gee_api/routes/agro.py agro_gee_api/main.py tests/test_agro_route.py tests/test_routes_registration.py
git commit -m "feat: add agro endpoint routes with completeness and error contracts"
```

### Task 11: End-to-end verification and handoff checks

**Files:**
- Modify: `README.md`
- Create: `tests/test_agro_integration.py`

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: PASS or only unrelated pre-existing failures.

- [ ] **Step 1.1: Add and run integration tests with mocked ERA5-Land scenarios**

Create `tests/test_agro_integration.py` covering:
- deterministic scenarios per crop (`soybean`, `corn`, `cotton`)
- aggregate consistency (`sum daily == reported total` where applicable)
- unit consistency checks (`K->C`, `m->mm` in response fields)
- `/gee` non-regression smoke (`/gee/ping`, one existing meteo path contract)

Run: `pytest tests/test_agro_integration.py -v`
Expected: PASS.

- [ ] **Step 2: Verify OpenAPI has 10 agro paths and examples**

Run: `python -c "from fastapi.testclient import TestClient; from agro_gee_api.main import app; spec=TestClient(app).get('/openapi.json').json(); paths=spec.get('paths',{}); print(len([p for p in paths if p.startswith('/agro/')])); print(sorted([p for p in paths if p.startswith('/agro/')]))"`
Expected: 10 paths.

Run: `python -c "from fastapi.testclient import TestClient; from agro_gee_api.main import app; s=TestClient(app).get('/openapi.json').json(); op=s['paths']['/agro/phenology/estimate/point']['post']; print('examples' in str(op))"`
Expected: `True`.

- [ ] **Step 2.1: Re-run full suite after integration tests are in place**

Run: `pytest -v`
Expected: PASS or only unrelated pre-existing failures.

- [ ] **Step 3: Update docs route inventory**

Add `/agro` domain and endpoint summary in `README.md`.
Add explicit "v1 limits and assumptions" section documenting:
- generic crop profiles (`v1_default`)
- ET0 by Hargreaves-Samani
- simple bucket water-balance model
- `date_harvest` informative only
- polygon completeness rule (`valid_ratio >= 0.60`)

- [ ] **Step 4: Commit docs update**

```bash
git add README.md tests/test_agro_integration.py
git commit -m "docs: add agro endpoint domain summary"
```
