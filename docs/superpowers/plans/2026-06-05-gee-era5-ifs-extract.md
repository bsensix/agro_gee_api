# GEE ERA5/IFS Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ERA5-Land and IFS Forecast point/polygon extract endpoints with explicit variable selection, variable catalog endpoints, and series/value outputs aligned with current extract API style.

**Architecture:** Introduce a meteo dataset/variable registry, a dedicated meteo extract service, and generic dataset-band extraction methods in the GEE client. Keep Sentinel-2 extract behavior unchanged while adding new routes under `/gee`.

**Tech Stack:** FastAPI, Pydantic, Earth Engine Python SDK, pytest

---

### Task 1: Add Meteo Catalog Registry

**Files:**
- Create: `api/services/gee_meteo_catalog.py`
- Test: `tests/test_gee_meteo_catalog.py`

- [ ] **Step 1: Write failing tests for dataset and variable catalog lookups**

```python
from agro_gee_api.services.gee_meteo_catalog import get_dataset_catalog


def test_era5_catalog_contains_variables():
    catalog = get_dataset_catalog("era5-land")
    assert catalog.dataset_id == "ECMWF/ERA5_LAND/HOURLY"
    assert len(catalog.variables) > 0


def test_unknown_catalog_key_raises_key_error():
    get_dataset_catalog("unknown")
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_gee_meteo_catalog.py -q`
Expected: FAIL (module/functions not found)

- [ ] **Step 3: Implement minimal meteo catalog module**

```python
@dataclass(frozen=True)
class MeteoVariable:
    variable: str
    band_name: str
    title: str
    unit: str


@dataclass(frozen=True)
class MeteoDatasetCatalog:
    key: str
    dataset_id: str
    title: str
    variables: tuple[MeteoVariable, ...]


def get_dataset_catalog(key: str) -> MeteoDatasetCatalog: ...
def list_dataset_variables(key: str) -> list[dict[str, str]]: ...
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_gee_meteo_catalog.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/services/gee_meteo_catalog.py tests/test_gee_meteo_catalog.py
git commit -m "feat: add GEE meteo dataset variable catalog"
```

### Task 2: Add Meteo Extract Service Validation Layer

**Files:**
- Create: `api/services/gee_meteo_extract.py`
- Test: `tests/test_gee_meteo_extract_service.py`

- [ ] **Step 1: Write failing tests for validation and delegation**

```python
def test_extract_point_rejects_unknown_variable():
    ...


def test_extract_polygon_rejects_start_after_end():
    ...


def test_extract_point_delegates_to_client_with_dataset_and_band():
    ...
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_gee_meteo_extract_service.py -q`
Expected: FAIL

- [ ] **Step 3: Implement minimal service**

```python
class MeteoExtractService:
    def extract_point(...): ...
    def extract_polygon(...): ...
    def list_variables(...): ...
```

Rules:
- Validate `date_start <= date_end`
- Validate date window max 31 days
- Validate variable exists in selected dataset catalog
- Map runtime errors to existing domain exceptions (`GEE_AUTH_FAILED`, `GEE_TIMEOUT`, etc.)

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_gee_meteo_extract_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/services/gee_meteo_extract.py tests/test_gee_meteo_extract_service.py
git commit -m "feat: add meteo extract service with input validation"
```

### Task 3: Extend EarthEngineClient for Generic Dataset-Band Extract

**Files:**
- Modify: `api/services/gee_client.py`
- Test: `tests/test_gee_client.py`

- [ ] **Step 1: Write failing tests for generic meteo extraction methods**

```python
def test_extract_dataset_point_returns_series_and_mean_value():
    ...


def test_extract_dataset_polygon_returns_series_and_mean_value():
    ...


def test_extract_dataset_drops_non_numeric_values_and_raises_no_imagery_if_empty():
    ...
```

- [ ] **Step 2: Run targeted tests to verify failure**

Run: `pytest tests/test_gee_client.py::test_extract_dataset_point_returns_series_and_mean_value -q`
Expected: FAIL

- [ ] **Step 3: Implement generic extraction methods**

Add methods:
- `extract_point_dataset(...)`
- `extract_polygon_dataset(...)`

Implementation details:
- Build `ImageCollection(dataset_id)` filtered by geometry/date range
- Enforce date filter bounds:
  - start = `date_startT00:00:00Z` (inclusive)
  - end = `date_end + 1 day at 00:00:00Z` (exclusive)
- Select `band_name`
- Compute per-image spatial mean with `reduceRegion`
- Build `series` with `date` (ISO UTC), `value`, `cloud_pct: None`
- Sort `series` ascending by `date`
- Compute `value` as arithmetic mean of numeric series values
- Drop null/NaN/inf values; raise `NO_IMAGERY` if no valid values remain

Additional tests required in this task:
- assert UTC ISO datetime format in `series[].date`
- assert temporal ordering ascending by `date`
- assert exact filter window conversion to inclusive/exclusive UTC boundaries

- [ ] **Step 4: Run full GEE client tests**

Run: `pytest tests/test_gee_client.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/services/gee_client.py tests/test_gee_client.py
git commit -m "feat: add generic GEE dataset band extraction"
```

### Task 4: Add ERA5 and IFS Routes

**Files:**
- Modify: `api/routes/gee.py`
- Test: `tests/test_gee_route.py`

- [ ] **Step 1: Write failing route tests for new endpoints**

```python
def test_post_era5_extract_point_returns_200(): ...
def test_post_era5_extract_polygon_returns_200(): ...
def test_post_ifs_extract_point_returns_200(): ...
def test_post_ifs_extract_polygon_returns_200(): ...
def test_get_era5_variables_returns_catalog(): ...
def test_get_ifs_variables_returns_catalog(): ...
def test_variable_catalog_response_is_sorted_bare_array(): ...
def test_variable_lookup_is_case_sensitive_invalid_request(): ...
def test_extract_point_rejects_out_of_range_coordinates(): ...
def test_extract_polygon_rejects_invalid_ring_shape(): ...
def test_extract_polygon_rejects_non_numeric_coordinates(): ...
def test_extract_polygon_rejects_out_of_range_coordinates(): ...
```

- [ ] **Step 2: Run targeted route tests to verify failure**

Run: `pytest tests/test_gee_route.py -k "era5 or ifs" -q`
Expected: FAIL

- [ ] **Step 3: Implement route models and handlers**

Add handlers:
- `POST /gee/era5-land/extract/point`
- `POST /gee/era5-land/extract/polygon`
- `POST /gee/ifs-forecast/extract/point`
- `POST /gee/ifs-forecast/extract/polygon`
- `GET /gee/datasets/era5-land/variables`
- `GET /gee/datasets/ifs-forecast/variables`

Response style:
- `dataset`, `variable`, `value`, `series`
- `series` entries include `date`, `value`, `cloud_pct`

Error mapping:
- Reuse existing `_error_response` mapping with `INVALID_REQUEST`, `NO_IMAGERY`, `GEE_UNAVAILABLE`, `GEE_TIMEOUT`, `GEE_AUTH_FAILED`, `GEE_INTERNAL_ERROR`

Geometry validation required before GEE calls:
- Point coords numeric and within lon/lat bounds
- Polygon ring closed and length >= 4
- Polygon coordinates numeric and within lon/lat bounds for all vertices
- malformed geometry mapped to `INVALID_REQUEST`

- [ ] **Step 4: Run route tests**

Run: `pytest tests/test_gee_route.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/routes/gee.py tests/test_gee_route.py
git commit -m "feat: add ERA5 and IFS extract endpoints"
```

### Task 5: Integration and OpenAPI Verification

**Files:**
- Modify: `tests/test_core_crud_api_integration.py` (only if needed for new routes)

- [ ] **Step 1: Write failing integration tests for new endpoints**

```python
def test_gee_era5_extract_point_returns_200_with_mocked_service(): ...
def test_gee_ifs_extract_polygon_returns_200_with_mocked_service(): ...
```

- [ ] **Step 2: Run targeted integration tests to verify failure**

Run: `pytest tests/test_core_crud_api_integration.py -k "era5 or ifs" -q`
Expected: FAIL

- [ ] **Step 3: Implement minimal integration wiring needed to pass**

Implement only route/service glue required by failing tests.

- [ ] **Step 4: Re-run targeted integration tests**

Run: `pytest tests/test_core_crud_api_integration.py -k "era5 or ifs" -q`
Expected: PASS

- [ ] **Step 5: Rebuild API and verify OpenAPI exposes new paths**

Run: `docker compose up -d --build api`

Run:
`python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://localhost:8000/openapi.json')); print('\n'.join(sorted([p for p in d.get('paths',{}) if '/gee/era5-land' in p or '/gee/ifs-forecast' in p or '/gee/datasets/era5-land/variables' in p or '/gee/datasets/ifs-forecast/variables' in p])))"`

Expected: all 6 new paths listed

- [ ] **Step 6: Smoke test new endpoints with valid payloads**

Run sample calls for each extract endpoint using a known variable from each catalog.
Expected: HTTP 200 with `dataset`, `variable`, `value`, `series`.

- [ ] **Step 7: Commit**

```bash
git add tests/test_core_crud_api_integration.py
git commit -m "test: add integration coverage for ERA5 and IFS extract"
```

### Task 6: Final Verification

**Files:**
- No new files required

- [ ] **Step 1: Run consolidated relevant tests**

Run:
`pytest tests/test_gee_client.py tests/test_gee_route.py tests/test_gee_meteo_catalog.py tests/test_gee_meteo_extract_service.py -q`

Expected: all pass

- [ ] **Step 2: Run full test suite if feasible**

Run: `pytest -q`
Expected: no regressions

- [ ] **Step 3: Validate API behavior manually**

Run smoke calls for:
- `GET /gee/datasets/era5-land/variables`
- `GET /gee/datasets/ifs-forecast/variables`
- one point + one polygon extract for each dataset

Expected: response contract matches spec.

- [ ] **Step 4: Document rollout notes in PR/body**

Include:
- New endpoints
- Window limit (31 days)
- Variable selection behavior
- `cloud_pct` semantics (`null` for ERA5/IFS)

### Task 7: Sentinel-2 Compatibility Regression Check

**Files:**
- No new files required

- [ ] **Step 1: Run existing Sentinel-2 route/client tests**

Run:
`pytest tests/test_gee_client.py tests/test_gee_route.py -k "sentinel2 or extract" -q`

Expected: PASS

- [ ] **Step 2: Execute Sentinel-2 smoke calls**

Run one `extract/point` and one `extract/polygon` request with existing payload format.
Expected: response includes `dataset`, `metric`, `value`, `series` and no contract regressions.

- [ ] **Step 3: Commit**

```bash
git add .
git commit -m "test: verify sentinel2 compatibility after meteo additions"
```
