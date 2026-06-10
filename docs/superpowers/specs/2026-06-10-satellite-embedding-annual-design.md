# Design: GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL integration (point and polygon)

## Context

This API already supports dataset extraction patterns for `era5-land` and `ifs-forecast` using:

- static dataset+variable catalog in `agro_gee_api/services/gee_meteo_catalog.py`
- shared extraction orchestration in `agro_gee_api/services/gee_meteo_extract.py`
- shared Earth Engine dataset reducers in `agro_gee_api/services/gee_client.py`
- route contracts in `agro_gee_api/routes/gee.py`

The goal is to add support for `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL` for both point and polygon extraction while preserving existing API conventions.

## Approved approach

Use a static, versioned catalog (same pattern as existing datasets), exposing all embedding bands as variables.

Rationale:

- predictable API contract
- deterministic tests
- no runtime dependency for variable discovery
- consistent with current codebase architecture

## Scope

### In scope

- add dataset key `satellite-embedding-annual`
- add dataset id `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- expose all embedding bands in catalog variables
- add point extract endpoint
- add polygon extract endpoint
- add variables endpoint
- update unit/route tests for catalog/service/routes

### Out of scope

- dynamic band discovery from GEE at runtime
- caching layer for dataset metadata
- changes to auth, RBAC, or error schema

## API design

### New endpoints

- `POST /gee/satellite-embedding-annual/extract/point`
- `POST /gee/satellite-embedding-annual/extract/polygon`
- `GET /gee/datasets/satellite-embedding-annual/variables`

### Request and response contracts

Reuse existing meteo-style contracts:

- request for point: `coordinates`, `date_start`, `date_end`, `variable`
- request for polygon: `geometry`, `date_start`, `date_end`, `variable`
- response: `dataset`, `variable`, `value`, `series[{date,value}]`

No schema changes are introduced for existing endpoints.

## Components and changes

### 1) Dataset catalog (`gee_meteo_catalog.py`)

- Add new `MeteoDatasetCatalog` entry keyed by `satellite-embedding-annual`.
- Include dataset metadata (`dataset_id`, title) and full variable list.
- Variable list contains all embedding band names as `variable` and `band_name`.

### 2) Route layer (`routes/gee.py`)

- Add three route handlers mirroring current `era5-land` and `ifs-forecast` handlers.
- Use `_meteo_extract_point(...)`, `_meteo_extract_polygon(...)`, and `list_variables(...)` with dataset key `satellite-embedding-annual`.
- Keep response models and error mapping unchanged.

### 3) Service layer (`gee_meteo_extract.py`)

- Add dataset-aware extraction settings resolution (`max_window_days`, `scale`).
- Keep current behavior for existing datasets (`era5-land` and `ifs-forecast` stay at 31 days and default scale).
- Apply `satellite-embedding-annual` policy:
  - `max_window_days = 3660` (10 years) to support annual time-series use cases.
  - `scale = 10` meters to match dataset pixel size.
- Pass `scale` through service/client protocol to GEE client methods.

### 4) GEE client (`gee_client.py`)

- Keep existing reducer implementation and method names:
  - `extract_point_dataset`
  - `extract_polygon_dataset`
- No new reducer logic is required; only ensure passed scale is honored (already supported by method signatures).

## Data flow

1. Route receives payload and validates geometry/date shape using current validators.
2. `MeteoExtractService` validates date window using dataset-specific limits and resolves `dataset_key + variable + scale`.
3. `EarthEngineClient` filters `ImageCollection(dataset_id)` by geometry and date range.
4. For each image, `reduceRegion(mean)` extracts target `band_name` using effective scale (`10` for this dataset).
5. Valid values are sorted into `series`; API computes average as `value`.
6. Response returns normalized payload (`dataset`, `variable`, `value`, `series`).

For annual imagery, `series` is expected to contain sparse points (often one per year in window), while `value` remains average-of-series. This is enabled by the explicit 10-year date-window policy for this dataset key.

## Error handling

Keep existing domain mapping and status codes:

- `INVALID_REQUEST` -> `400`
- `NO_IMAGERY` -> `422`
- `GEE_UNAVAILABLE` -> `503`
- `GEE_TIMEOUT` -> `504`
- `GEE_AUTH_FAILED` -> `500`

No new error codes or envelope format changes.

## Testing strategy

### Catalog tests (`tests/test_gee_meteo_catalog.py`)

- assert dataset key resolves to `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`
- assert variables endpoint payload is sorted and exact for full embedding list

### Service tests (`tests/test_gee_meteo_extract_service.py`)

- assert variable resolution delegates correct `band_name` for the new dataset
- assert point and polygon calls map to correct dataset id
- assert dataset-specific date-window policy (`3660` accepted, `>3660` rejected)
- assert scale `10` is forwarded to client for this dataset

### Route tests (`tests/test_gee_route.py`)

- success path for point endpoint
- success path for polygon endpoint
- variables endpoint returns sorted list
- representative error mapping checks (validation and timeout/unavailable)

## Catalog appendix (implementation-defining)

### Dataset key

- `satellite-embedding-annual`

### Dataset id

- `GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL`

### Variable payload rule

- `variable == band_name`
- `unit = "dimensionless"`
- `title = "Embedding axis N"` where `N` is axis index (0..63)

### Full variable list (exact)

- `A00`, `A01`, `A02`, `A03`, `A04`, `A05`, `A06`, `A07`
- `A08`, `A09`, `A10`, `A11`, `A12`, `A13`, `A14`, `A15`
- `A16`, `A17`, `A18`, `A19`, `A20`, `A21`, `A22`, `A23`
- `A24`, `A25`, `A26`, `A27`, `A28`, `A29`, `A30`, `A31`
- `A32`, `A33`, `A34`, `A35`, `A36`, `A37`, `A38`, `A39`
- `A40`, `A41`, `A42`, `A43`, `A44`, `A45`, `A46`, `A47`
- `A48`, `A49`, `A50`, `A51`, `A52`, `A53`, `A54`, `A55`
- `A56`, `A57`, `A58`, `A59`, `A60`, `A61`, `A62`, `A63`

## Risks and mitigations

- Large static variable list can drift from provider updates.
  - Mitigation: keep list versioned and covered by exact-match tests.
- Annual cadence may surprise consumers expecting dense series.
  - Mitigation: preserve consistent response contract and document sparse series behavior.

## Rollout and compatibility

- Backward-compatible addition (new dataset key and endpoints only).
- Existing endpoints and payloads remain unchanged.
- No migrations or env var changes required.
