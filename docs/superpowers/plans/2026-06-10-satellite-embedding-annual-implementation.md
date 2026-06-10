# Satellite Embedding Annual Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` extraction support for point and polygon, exposing all 64 embedding axes (`A00`..`A63`) through variable catalog and extract endpoints.

**Architecture:** Extend the existing meteo-style dataset catalog and extraction flow instead of introducing a new service family. Add dataset-aware extraction settings in `MeteoExtractService` so this dataset can use a longer date window and scale 10m, while existing datasets keep current behavior. Add three new routes under `/gee` following the existing endpoint and error contract patterns.

**Tech Stack:** FastAPI, Pydantic, Earth Engine Python SDK, pytest

---

## File Structure and Responsibilities

- `agro_gee_api/services/gee_meteo_catalog.py`
  - Source of truth for dataset id, variable registry, and metadata for `satellite-embedding-annual`.
- `agro_gee_api/services/gee_meteo_extract.py`
  - Dataset-aware validation/settings (`max_window_days`, `scale`) and delegation to GEE client.
- `agro_gee_api/routes/gee.py`
  - HTTP handlers for new point/polygon/variables endpoints reusing common request validation and error mapping.
- `tests/test_gee_meteo_catalog.py`
  - Exact contract tests for new dataset catalog and sorted variable payload.
- `tests/test_gee_meteo_extract_service.py`
  - Unit tests for dataset-specific policy (10-year window + scale forwarding) and dataset resolution.
- `tests/test_gee_route.py`
  - Route-level success/error mapping and variables endpoint coverage for `satellite-embedding-annual`.

### Task 1: Add failing catalog tests for Satellite Embedding variables

**Files:**
- Modify: `tests/test_gee_meteo_catalog.py`
- Test: `tests/test_gee_meteo_catalog.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_get_dataset_catalog_satellite_embedding_annual_uses_expected_dataset_id() -> None:
    catalog = get_dataset_catalog("satellite-embedding-annual")
    assert catalog.dataset_id == "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"


def test_list_dataset_variables_satellite_embedding_annual_returns_all_axes() -> None:
    variables = list_dataset_variables("satellite-embedding-annual")

    expected = [
        {
            "variable": f"A{i:02d}",
            "band_name": f"A{i:02d}",
            "title": f"Embedding axis {i}",
            "unit": "dimensionless",
        }
        for i in range(64)
    ]

    assert variables == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_gee_meteo_catalog.py -k "satellite_embedding" -v`
Expected: FAIL with unknown dataset key and/or missing expected variables.

- [ ] **Step 3: Commit failing-test checkpoint**

```bash
git add tests/test_gee_meteo_catalog.py
git commit -m "test: add failing catalog coverage for satellite embedding dataset"
```

### Task 2: Implement catalog entry with all 64 variables

**Files:**
- Modify: `agro_gee_api/services/gee_meteo_catalog.py`
- Test: `tests/test_gee_meteo_catalog.py`

- [ ] **Step 1: Implement minimal catalog changes to satisfy tests**

```python
def _satellite_embedding_variables() -> tuple[MeteoVariable, ...]:
    return tuple(
        MeteoVariable(
            variable=f"A{i:02d}",
            band_name=f"A{i:02d}",
            title=f"Embedding axis {i}",
            unit="dimensionless",
        )
        for i in range(64)
    )


_DATASET_CATALOGS["satellite-embedding-annual"] = MeteoDatasetCatalog(
    key="satellite-embedding-annual",
    dataset_id="GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
    title="Satellite Embedding V1 Annual",
    variables=_satellite_embedding_variables(),
)
```

- [ ] **Step 2: Run tests to verify pass**

Run: `pytest tests/test_gee_meteo_catalog.py -v`
Expected: PASS, including new dataset tests.

- [ ] **Step 3: Commit**

```bash
git add agro_gee_api/services/gee_meteo_catalog.py tests/test_gee_meteo_catalog.py
git commit -m "feat: add satellite embedding annual dataset catalog"
```

### Task 3: Add failing service tests for dataset-specific window and scale

**Files:**
- Modify: `tests/test_gee_meteo_extract_service.py`
- Test: `tests/test_gee_meteo_extract_service.py`

- [ ] **Step 1: Add failing tests for new service behavior**

```python
def test_extract_point_satellite_embedding_forwards_scale_10() -> None:
    client = FakeMeteoClient()
    service = MeteoExtractService(gee_client=client)

    service.extract_point(
        dataset_key="satellite-embedding-annual",
        geometry_geojson=_point(),
        date_start=date(2020, 1, 1),
        date_end=date(2024, 12, 31),
        variable="A00",
    )

    assert client.last_call is not None
    assert client.last_call["dataset_id"] == "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
    assert client.last_call["band_name"] == "A00"
    assert client.last_call["scale"] == 10


def test_extract_polygon_satellite_embedding_accepts_longer_window() -> None:
    client = FakeMeteoClient()
    service = MeteoExtractService(gee_client=client)
    service.extract_polygon(
        dataset_key="satellite-embedding-annual",
        geometry_geojson=_polygon(),
        date_start=date(2017, 1, 1),
        date_end=date(2025, 1, 1),
        variable="A63",
    )

    assert client.last_call is not None
    assert client.last_call["dataset_id"] == "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
    assert client.last_call["band_name"] == "A63"
    assert client.last_call["scale"] == 10


def test_extract_point_satellite_embedding_rejects_window_above_10_years() -> None:
    service = MeteoExtractService(gee_client=FakeMeteoClient())
    with pytest.raises(ValidationError):
        service.extract_point(
            dataset_key="satellite-embedding-annual",
            geometry_geojson=_point(),
            date_start=date(2014, 1, 1),
            date_end=date(2025, 1, 1),
            variable="A00",
        )
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_gee_meteo_extract_service.py -k "satellite_embedding" -v`
Expected: FAIL because current service does not support dataset-specific window/scale.

- [ ] **Step 3: Commit failing-test checkpoint**

```bash
git add tests/test_gee_meteo_extract_service.py
git commit -m "test: add failing service tests for satellite embedding policies"
```

### Task 4: Implement service policy and client delegation updates

**Files:**
- Modify: `agro_gee_api/services/gee_meteo_extract.py`
- Modify: `agro_gee_api/routes/gee.py`
- Modify: `tests/test_gee_meteo_extract_service.py`
- Test: `tests/test_gee_meteo_extract_service.py`
- Test: `tests/test_gee_route.py`

- [ ] **Step 1: Implement minimal service changes**

```python
@dataclass(frozen=True)
class DatasetExtractSettings:
    max_window_days: int
    scale: int | None = None


_DEFAULT_SETTINGS = DatasetExtractSettings(max_window_days=31, scale=None)
_DATASET_SETTINGS = {
    "satellite-embedding-annual": DatasetExtractSettings(max_window_days=3660, scale=10)
}


def _settings_for_dataset(self, dataset_key: str) -> DatasetExtractSettings:
    return _DATASET_SETTINGS.get(dataset_key, _DEFAULT_SETTINGS)
```

Also update `MeteoExtractClient` protocol and calls to pass `scale`:

```python
def extract_dataset_point(..., scale: int | None = None) -> DatasetExtractResult: ...
def extract_dataset_polygon(..., scale: int | None = None) -> DatasetExtractResult: ...
```

And update route adapter signatures in `_MeteoRouteClient` to forward scale:

```python
def extract_dataset_point(..., scale: int | None = None) -> DatasetExtractResult:
    return self._gee_client.extract_point_dataset(..., scale=scale)


def extract_dataset_polygon(..., scale: int | None = None) -> DatasetExtractResult:
    return self._gee_client.extract_polygon_dataset(..., scale=scale)
```

Add a route-wiring test that uses the real route path + meteo service path (without mocking `get_meteo_extract_service`) and verifies `scale=10` reaches `get_gee_client`:

```python
def test_post_satellite_embedding_extract_point_forwards_scale_10_to_gee_client(monkeypatch):
    captured: dict[str, object] = {}

    class GeeClientStub:
        def extract_point_dataset(self, **kwargs: object) -> dict[str, object]:
            captured.update(kwargs)
            return {
                "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
                "variable": "A00",
                "value": 0.2,
                "series": [{"date": "2024-01-01T00:00:00Z", "value": 0.2, "cloud_pct": None}],
            }

        def extract_polygon_dataset(self, **kwargs: object) -> dict[str, object]:
            raise AssertionError("not used")

    monkeypatch.setattr("agro_gee_api.routes.gee.get_gee_client", lambda: GeeClientStub(), raising=False)
    response = TestClient(app).post(...)
    assert response.status_code == 200
    assert captured["scale"] == 10
```

- [ ] **Step 2: Run tests to verify pass**

Run: `pytest tests/test_gee_meteo_extract_service.py tests/test_gee_route.py -k "satellite_embedding" -v`
Expected: PASS including new policy tests and existing regressions.

- [ ] **Step 3: Commit**

```bash
git add agro_gee_api/services/gee_meteo_extract.py agro_gee_api/routes/gee.py tests/test_gee_meteo_extract_service.py tests/test_gee_route.py
git commit -m "feat: add dataset-specific window and scale for meteo extract"
```

### Task 5: Add failing route tests for new endpoints

**Files:**
- Modify: `tests/test_gee_route.py`
- Test: `tests/test_gee_route.py`

- [ ] **Step 1: Write failing route tests**

```python
def test_post_satellite_embedding_extract_point_returns_extract_contract(monkeypatch) -> None:
    class MeteoService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "satellite-embedding-annual"
            assert kwargs["variable"] == "A00"
            return {
                "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
                "variable": "A00",
                "value": 0.123,
                "series": [
                    {"date": "2024-01-01T00:00:00Z", "value": 0.10, "cloud_pct": None},
                    {"date": "2025-01-01T00:00:00Z", "value": 0.146, "cloud_pct": None},
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)
    response = client.post(
        "/gee/satellite-embedding-annual/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2024-01-01",
            "date_end": "2025-01-01",
            "variable": "A00",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
        "variable": "A00",
        "value": 0.123,
        "series": [
            {"date": "2024-01-01T00:00:00Z", "value": 0.1},
            {"date": "2025-01-01T00:00:00Z", "value": 0.146},
        ],
    }


def test_post_satellite_embedding_extract_polygon_returns_extract_contract(monkeypatch) -> None:
    class MeteoService:
        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["dataset_key"] == "satellite-embedding-annual"
            assert kwargs["variable"] == "A63"
            return {
                "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
                "variable": "A63",
                "value": -0.22,
                "series": [
                    {"date": "2023-01-01T00:00:00Z", "value": -0.22, "cloud_pct": None}
                ],
            }

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)
    response = client.post(
        "/gee/satellite-embedding-annual/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2023-01-01",
            "date_end": "2025-01-01",
            "variable": "A63",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "dataset": "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL",
        "variable": "A63",
        "value": -0.22,
        "series": [{"date": "2023-01-01T00:00:00Z", "value": -0.22}],
    }


def test_get_satellite_embedding_variables_returns_bare_sorted_array(monkeypatch) -> None:
    class MeteoService:
        def list_variables(self, dataset_key: str) -> list[dict[str, str]]:
            assert dataset_key == "satellite-embedding-annual"
            return [
                {
                    "variable": "A01",
                    "band_name": "A01",
                    "title": "Embedding axis 1",
                    "unit": "dimensionless",
                },
                {
                    "variable": "A00",
                    "band_name": "A00",
                    "title": "Embedding axis 0",
                    "unit": "dimensionless",
                },
            ]

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)
    response = client.get("/gee/datasets/satellite-embedding-annual/variables")

    assert response.status_code == 200
    assert response.json() == [
        {
            "variable": "A00",
            "band_name": "A00",
            "title": "Embedding axis 0",
            "unit": "dimensionless",
        },
        {
            "variable": "A01",
            "band_name": "A01",
            "title": "Embedding axis 1",
            "unit": "dimensionless",
        },
    ]


def test_post_satellite_embedding_extract_point_maps_validation_error(monkeypatch) -> None:
    class MeteoService:
        def extract_point(self, **kwargs: object) -> dict[str, object]:
            raise MeteoValidationError("INVALID_REQUEST", "Unsupported variable")

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)
    response = client.post(
        "/gee/satellite-embedding-annual/extract/point",
        json={
            "coordinates": [-47.0, -15.0],
            "date_start": "2024-01-01",
            "date_end": "2025-01-01",
            "variable": "BAD_AXIS",
        },
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_REQUEST"


def test_post_satellite_embedding_extract_polygon_maps_timeout(monkeypatch) -> None:
    class MeteoService:
        def extract_polygon(self, **kwargs: object) -> dict[str, object]:
            raise MeteoGEETimeoutError("GEE_TIMEOUT", "timeout", retryable=True)

    monkeypatch.setattr(
        "agro_gee_api.routes.gee.get_meteo_extract_service",
        lambda: MeteoService(),
        raising=False,
    )
    client = TestClient(app)
    response = client.post(
        "/gee/satellite-embedding-annual/extract/polygon",
        json={
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
                ],
            },
            "date_start": "2024-01-01",
            "date_end": "2025-01-01",
            "variable": "A00",
        },
    )

    assert response.status_code == 504
    assert response.json()["error_code"] == "GEE_TIMEOUT"
```

Use the same assertion style already used for `era5-land` and `ifs-forecast` tests.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_gee_route.py -k "satellite_embedding" -v`
Expected: FAIL (routes not found or 404).

- [ ] **Step 3: Commit failing-test checkpoint**

```bash
git add tests/test_gee_route.py
git commit -m "test: add failing route coverage for satellite embedding endpoints"
```

### Task 6: Implement routes and pass full relevant test set

**Files:**
- Modify: `agro_gee_api/routes/gee.py`
- Modify: `tests/test_gee_route.py`
- Test: `tests/test_gee_route.py`
- Test: `tests/test_gee_meteo_catalog.py`
- Test: `tests/test_gee_meteo_extract_service.py`

- [ ] **Step 1: Implement route handlers using existing helpers**

Add handlers:

```python
@router.post("/satellite-embedding-annual/extract/point", ...)
def post_satellite_embedding_extract_point(payload: MeteoExtractPointRequest):
    return _meteo_extract_point(dataset_key="satellite-embedding-annual", payload=payload)


@router.post("/satellite-embedding-annual/extract/polygon", ...)
def post_satellite_embedding_extract_polygon(payload: MeteoExtractPolygonRequest):
    return _meteo_extract_polygon(dataset_key="satellite-embedding-annual", payload=payload)


@router.get("/datasets/satellite-embedding-annual/variables", ...)
def get_satellite_embedding_variables():
    variables = get_meteo_extract_service().list_variables("satellite-embedding-annual")
    return [MeteoVariableResponse(**item) for item in _sort_variable_catalog(variables)]
```

- [ ] **Step 2: Run route tests**

Run: `pytest tests/test_gee_route.py -v`
Expected: PASS with new satellite embedding route coverage.

- [ ] **Step 3: Run consolidated relevant suite**

Run: `pytest tests/test_gee_meteo_catalog.py tests/test_gee_meteo_extract_service.py tests/test_gee_route.py -v`
Expected: PASS, no regressions in existing meteo/sentinel route contracts.

- [ ] **Step 4: Commit**

```bash
git add agro_gee_api/routes/gee.py tests/test_gee_route.py
git commit -m "feat: add satellite embedding annual point polygon and variables endpoints"
```

### Task 7: Final verification and handoff notes

**Files:**
- Modify (if needed): `README.md`

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: PASS or only unrelated pre-existing failures.

- [ ] **Step 2: Verify OpenAPI paths are exposed**

Run:
`python -c "from fastapi.testclient import TestClient; from agro_gee_api.main import app; d=TestClient(app).get('/openapi.json').json(); print('\n'.join(sorted([p for p in d.get('paths',{}) if 'satellite-embedding-annual' in p])))"`

Expected paths:
- `/gee/satellite-embedding-annual/extract/point`
- `/gee/satellite-embedding-annual/extract/polygon`
- `/gee/datasets/satellite-embedding-annual/variables`

- [ ] **Step 3: Document rollout note (if README is updated)**

Add concise note with dataset key and new endpoints only if project docs require route inventory updates.

- [ ] **Step 4: Final commit (if docs changed)**

```bash
git add README.md
git commit -m "docs: add satellite embedding annual endpoint references"
```
