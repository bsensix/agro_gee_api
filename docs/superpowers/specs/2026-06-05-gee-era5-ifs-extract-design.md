# Design: GEE ERA5/IFS Extract Endpoints

## Goal

Add point/polygon extract endpoints for:

- `ECMWF/ERA5_LAND/HOURLY`
- `ECMWF/NRT_FORECAST/IFS/OPER`

using the same interaction style as existing Sentinel-2 extract endpoints, with explicit variable selection and timestamped series output.

## Scope

In scope:

- New `extract/point` and `extract/polygon` endpoints for ERA5-Land and IFS.
- New variable-catalog endpoints for those datasets.
- Series output with temporal values and `cloud_pct` set to `null` (not applicable for meteo datasets).
- Validation and error mapping aligned with existing GEE route patterns.

Out of scope:

- Reintroducing removed `timeseries`, `image`, `stats` endpoints.
- Changing Sentinel-2 endpoint contracts.

## API Contract

### New Endpoints

- `POST /gee/era5-land/extract/point`
- `POST /gee/era5-land/extract/polygon`
- `POST /gee/ifs-forecast/extract/point`
- `POST /gee/ifs-forecast/extract/polygon`
- `GET /gee/datasets/era5-land/variables`
- `GET /gee/datasets/ifs-forecast/variables`

### Request (extract)

Point:

- `coordinates: [lon, lat]`
- `date_start: YYYY-MM-DD`
- `date_end: YYYY-MM-DD`
- `variable: string` (required)

Polygon:

- `geometry: GeoJSON Polygon`
- `date_start: YYYY-MM-DD`
- `date_end: YYYY-MM-DD`
- `variable: string` (required)

### Response (extract)

- `dataset: string`
- `variable: string`
- `value: float` (mean over requested window)
- `series: [{ date, value, cloud_pct }]`

Notes:

- `date` is ISO datetime string (`YYYY-MM-DDTHH:mm:ssZ`) for temporal consistency.
- `cloud_pct` is always `null` for ERA5/IFS.
- `series` is always sorted ascending by `date`.

### Response (variables catalog)

- bare array sorted by `variable` ascending, unique case-sensitive keys.
- each item contains:
  - `variable`
  - `band_name`
  - `title`
  - `unit`
- unknown variable values (including case mismatch) return `INVALID_REQUEST`.

## Data/Computation Model

For each request:

1. Resolve dataset key -> GEE dataset id.
2. Validate `variable` exists in dataset variable catalog.
3. Build `ImageCollection` filtered by geometry and date range.
4. For each image/timestamp, compute spatial mean for selected band over geometry.
5. Build `series` entries with `date`, `value`, `cloud_pct: null`.
6. Compute `value` as mean of all series values.
7. If no valid values are produced, return `NO_IMAGERY` (422).

Temporal rules:

- `date_start` interpreted as `00:00:00Z` inclusive.
- `date_end` interpreted as next-day `00:00:00Z` exclusive to preserve full end date.
- output timestamps are UTC.

## Architecture Changes

### Routes (`api/routes/gee.py`)

- Add request/response models for meteo extract + variable list endpoints.
- Add 6 route handlers.
- Reuse existing `_error_response`, `DomainError`, and status mapping.

### Services

New module: `api/services/gee_meteo_extract.py`

- validates date window and variable
- delegates extraction to GEE client
- maps domain validation and runtime errors

New module: `api/services/gee_meteo_catalog.py`

- dataset registry (`era5-land`, `ifs-forecast`)
- variable registry per dataset

### GEE Client (`api/services/gee_client.py`)

Add generic meteo operations:

- `extract_point_dataset(...)`
- `extract_polygon_dataset(...)`

Both accept `dataset_id`, `band_name`, geometry/date window and return:

- aggregate `value`
- `series`

Maintain existing Sentinel-2 methods unchanged.

## Validation & Limits

- `date_start <= date_end`
- max date window initial limit: 31 days (to bound payload/cost)
- unsupported variable -> `INVALID_REQUEST` (400)
- malformed geometry -> `INVALID_REQUEST` (400)
- no data -> `NO_IMAGERY` (422)

## Error Mapping

- `INVALID_REQUEST` -> 400
- `NO_IMAGERY` -> 422
- `GEE_UNAVAILABLE` -> 503
- `GEE_TIMEOUT` -> 504
- `GEE_AUTH_FAILED` -> 500
- `GEE_INTERNAL_ERROR` -> 500

Geometry validation rules:

- `Point`: exactly two numeric coordinates `[lon, lat]`, lon in `[-180, 180]`, lat in `[-90, 90]`.
- `Polygon`: at least one linear ring, ring length >= 4, first coordinate equals last coordinate, all coords numeric and within lon/lat bounds.
- invalid geometry parse/shape/value errors are mapped to `INVALID_REQUEST` before GEE calls.

Numeric sanitization rules:

- drop per-timestamp values that are `null`, NaN, or infinite.
- if all series values are dropped, return `NO_IMAGERY`.
- `value` uses arithmetic mean of remaining values with no manual rounding.

## Testing Strategy

Unit tests:

- `tests/test_gee_meteo_extract_service.py`
- extend `tests/test_gee_client.py` for meteo series extraction

Route tests:

- extend `tests/test_gee_route.py` with new endpoints and variable catalogs

Compatibility tests:

- verify Sentinel-2 extract endpoints still pass unchanged

## Rollout

1. Implement service + catalog + client additions.
2. Add routes and tests.
3. Rebuild API container and verify OpenAPI paths.
4. Run smoke calls against ERA5-Land and IFS endpoints.

## Risks and Mitigations

- Large response payloads for long windows:
  - enforce 31-day initial window.
- Dataset temporal sparsity differences:
  - return available timestamps only.
- Forecast dataset availability variance:
  - standardized `NO_IMAGERY` behavior when empty.
