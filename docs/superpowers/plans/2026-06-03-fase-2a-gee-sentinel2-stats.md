# Fase 2A - GEE Sentinel-2 Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar `POST /gee/sentinel2/stats` com autenticacao Service Account, calculo `ndvi_mean` para talhao autorizado e contrato de erros rastreavel.

**Architecture:** `api/routes/gee.py` valida payload, resolve autorizacao por `X-User-Id`, carrega geometria/area do talhao e chama `Sentinel2StatsService`. O servico (`api/services/gee_sentinel2.py`) aplica validacoes (datas, limite de 365 dias, area maxima, metrica) e traduz falhas do `GEEClient` para erros de dominio. `api/services/gee_client.py` contem a interface testavel e o adapter real com Service Account.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, Psycopg/PostGIS, earthengine-api, Pytest.

---

## Scope guard

Este plano implementa apenas Fase 2A (spec `docs/superpowers/specs/2026-06-03-fase-2-gee-sentinel2-design.md`):

- inclui: Service Account, endpoint de stats sincrono, `ndvi_mean`, contrato de erro.
- exclui: `extract/point`, `extract/polygon`, `timeseries`, `image`, `gee_datasets` (Fase 2B).

## File Structure

- Create: `api/services/__init__.py`
- Create: `api/services/gee_client.py`
- Create: `api/services/gee_sentinel2.py`
- Modify: `api/routes/gee.py`
- Modify: `pyproject.toml`
- Create: `tests/test_gee_client.py`
- Create: `tests/test_gee_service.py`
- Create: `tests/test_gee_route.py`
- Modify: `tests/test_core_crud_api_integration.py`

### Task 1: Dependency and Service Account Client Boundary

**Files:**
- Modify: `pyproject.toml`
- Create: `api/services/__init__.py`
- Create: `api/services/gee_client.py`
- Test: `tests/test_gee_client.py`

- [ ] **Step 1: Write failing tests for env contract and import safety**

```python
import os

import pytest

from agro_gee_api.services.gee_client import GEEAuthError, build_service_account_config


def test_build_service_account_config_requires_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_EMAIL", raising=False)
    monkeypatch.delenv("GEE_PRIVATE_KEY", raising=False)

    with pytest.raises(GEEAuthError) as exc:
        build_service_account_config()

    assert exc.value.error_code == "GEE_AUTH_FAILED"


def test_build_service_account_config_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEE_SERVICE_ACCOUNT_EMAIL", "svc@example.iam.gserviceaccount.com")
    monkeypatch.setenv("GEE_PRIVATE_KEY", "-----BEGIN PRIVATE KEY-----\\nabc\\n-----END PRIVATE KEY-----")

    config = build_service_account_config()

    assert config.service_account_email == "svc@example.iam.gserviceaccount.com"
```

- [ ] **Step 2: Run test to verify RED**

Run: `pytest tests/test_gee_client.py::test_build_service_account_config_requires_env_vars -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'api.services.gee_client'`).

- [ ] **Step 3: Add dependency and minimal client module**

```toml
dependencies = [
    "fastapi>=0.115,<1.0",
    "psycopg[binary]>=3.2,<4.0",
    "uvicorn[standard]>=0.30,<1.0",
    "earthengine-api>=1.5,<2.0",
]
```

```python
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class GEEAuthError(Exception):
    error_code: str
    message: str


@dataclass(frozen=True)
class ServiceAccountConfig:
    service_account_email: str
    private_key: str


def build_service_account_config() -> ServiceAccountConfig:
    email = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
    key = os.getenv("GEE_PRIVATE_KEY")
    if not email or not key:
        raise GEEAuthError("GEE_AUTH_FAILED", "Missing service account credentials")
    return ServiceAccountConfig(service_account_email=email, private_key=key)
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest tests/test_gee_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml api/services/__init__.py api/services/gee_client.py tests/test_gee_client.py
git commit -m "feat: add service-account gee client contract"
```

### Task 2: Sentinel-2 Domain Service (validation + mapping)

**Files:**
- Create: `api/services/gee_sentinel2.py`
- Modify: `api/services/gee_client.py`
- Test: `tests/test_gee_service.py`

- [ ] **Step 1: Write failing tests for required validations**

```python
from datetime import date

import pytest

from agro_gee_api.services.gee_sentinel2 import Sentinel2StatsService, ValidationError


class DummyClient:
    def ndvi_mean(self, **_: object) -> tuple[float | None, int]:
        return 0.42, 3


def test_validate_rejects_start_after_end() -> None:
    service = Sentinel2StatsService(gee_client=DummyClient(), area_limit_ha=10000)
    with pytest.raises(ValidationError) as exc:
        service.compute(
            geometry_geojson={"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
            area_ha=100,
            date_start=date(2026, 6, 2),
            date_end=date(2026, 6, 1),
            metric="ndvi_mean",
        )
    assert exc.value.error_code == "INVALID_REQUEST"


def test_validate_rejects_window_above_365_days() -> None:
    service = Sentinel2StatsService(gee_client=DummyClient(), area_limit_ha=10000)
    with pytest.raises(ValidationError) as exc:
        service.compute(
            geometry_geojson={"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]},
            area_ha=100,
            date_start=date(2025, 1, 1),
            date_end=date(2026, 2, 1),
            metric="ndvi_mean",
        )
    assert exc.value.error_code == "INVALID_REQUEST"
```

- [ ] **Step 2: Run RED tests**

Run: `pytest tests/test_gee_service.py::test_validate_rejects_start_after_end tests/test_gee_service.py::test_validate_rejects_window_above_365_days -v`
Expected: FAIL (missing service module/classes).

- [ ] **Step 3: Implement minimal domain model and validations**

```python
if metric != "ndvi_mean":
    raise ValidationError("INVALID_REQUEST", "Unsupported metric")
if date_start > date_end:
    raise ValidationError("INVALID_REQUEST", "date_start must be <= date_end")
if (date_end - date_start).days > 365:
    raise ValidationError("INVALID_REQUEST", "date range exceeds 365 days")
if area_ha > self._area_limit_ha:
    raise AreaLimitError("AREA_LIMIT_EXCEEDED", "Field area exceeds synchronous limit")
```

- [ ] **Step 4: Add failing tests for cloud filter and external error mapping**

```python
class CaptureCloudClient:
    def __init__(self) -> None:
        self.cloud = None
    def ndvi_mean(self, **kwargs: object) -> tuple[float | None, int]:
        self.cloud = kwargs["cloud_pct_max"]
        return 0.55, 4


def test_compute_uses_cloud_filter_20_percent() -> None:
    client = CaptureCloudClient()
    service = Sentinel2StatsService(gee_client=client, area_limit_ha=10000)
    result = service.compute(...)
    assert client.cloud == 20
    assert result.images_used == 4
```

Also add tests for `NoImageryError`, `GEETimeoutError`, `GEEUnavailableError`, `GEEAuthFailedError` mapping.

- [ ] **Step 5: Implement GREEN for mapping**

```python
except TimeoutError as exc:
    raise GEETimeoutError("GEE_TIMEOUT", "GEE request timed out", retryable=True) from exc
except GEEAuthError as exc:
    raise GEEAuthFailedError("GEE_AUTH_FAILED", exc.message) from exc
```

- [ ] **Step 6: Run full service tests**

Run: `pytest tests/test_gee_service.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/services/gee_client.py api/services/gee_sentinel2.py tests/test_gee_service.py
git commit -m "feat: add sentinel-2 stats domain service"
```

### Task 3: FastAPI Route and Error Schema

**Files:**
- Modify: `api/routes/gee.py`
- Test: `tests/test_gee_route.py`

- [ ] **Step 1: Write failing tests for endpoint contract and non-2xx payload**

```python
from fastapi.testclient import TestClient

from agro_gee_api.main import app


def test_post_sentinel2_stats_returns_error_schema_on_invalid_dates(monkeypatch) -> None:
    client = TestClient(app)
    response = client.post(
        "/gee/sentinel2/stats",
        headers={"X-User-Id": "1"},
        json={"field_id": 10, "date_start": "2026-06-10", "date_end": "2026-06-01", "metric": "ndvi_mean"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error_code"] == "INVALID_REQUEST"
    assert "correlation_id" in body
    assert body["retryable"] is False
```

- [ ] **Step 2: Run RED test**

Run: `pytest tests/test_gee_route.py::test_post_sentinel2_stats_returns_error_schema_on_invalid_dates -v`
Expected: FAIL (route missing).

- [ ] **Step 3: Implement route with status mapping**

```python
STATUS_BY_CODE = {
    "INVALID_REQUEST": 400,
    "FORBIDDEN_SCOPE": 403,
    "FIELD_NOT_FOUND": 404,
    "AREA_LIMIT_EXCEEDED": 413,
    "NO_IMAGERY": 422,
    "GEE_UNAVAILABLE": 503,
    "GEE_TIMEOUT": 504,
    "GEE_AUTH_FAILED": 500,
}
```

Route responsibilities:

- parse request model;
- authorize `field_id` using `AuthzContext` and owner lookup;
- load geometry + area from DB;
- call service and return 200 payload;
- on domain error, return standardized body with `correlation_id`.

- [ ] **Step 4: Add route tests for 413/422/503/504 and 200 schema**

Include concrete tests that monkeypatch the service object returned by a provider function (`get_sentinel2_service`) to force each domain error and happy path.

- [ ] **Step 5: Run route tests**

Run: `pytest tests/test_gee_route.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/routes/gee.py tests/test_gee_route.py
git commit -m "feat: add /gee/sentinel2/stats route with tracked error schema"
```

### Task 4: Integration Tests for Auth and Field Lookup

**Files:**
- Modify: `tests/test_core_crud_api_integration.py`

- [ ] **Step 1: Write failing integration tests**

Add tests (all with `@pytest.mark.integration`):

- `test_gee_stats_returns_403_for_out_of_scope_field`
- `test_gee_stats_returns_404_for_missing_field`
- `test_gee_stats_returns_200_for_authorized_field`

Use real DB entities (`users` -> `farms` -> `fields`) and monkeypatch service provider in route to return deterministic NDVI result without network.

- [ ] **Step 2: Start integration prerequisites**

Run: `docker compose up -d db`
Expected: DB container healthy.

- [ ] **Step 3: Run targeted integration test to verify RED first**

Run: `pytest -m integration tests/test_core_crud_api_integration.py::test_gee_stats_returns_403_for_out_of_scope_field -v`
Expected: FAIL before endpoint integration is complete.

- [ ] **Step 4: Implement minimum integration wiring and run GREEN set**

Run: `pytest -m integration tests/test_core_crud_api_integration.py -k gee_stats -v`
Expected: PASS.

- [ ] **Step 5: Run regression suite**

Run: `pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_core_crud_api_integration.py
git commit -m "test: cover gee stats authorization and field lookup integration"
```

## Final Verification

- [ ] `pytest tests/test_gee_client.py tests/test_gee_service.py tests/test_gee_route.py -v`
- [ ] `pytest -q`
- [ ] `pytest -m integration tests/test_core_crud_api_integration.py -k gee_stats -v`
- [ ] manual check: `POST /gee/sentinel2/stats` returns expected schema

## Execution Handoff

- **Subagent-driven (recommended):** start at **Task 1 / Step 1** with a fresh worker and enforce `@test-driven-development` per task.
- **Inline execution:** run tasks sequentially in this session, never skipping RED->GREEN transitions.

If you choose inline mode, the first command is:

`pytest tests/test_gee_client.py::test_build_service_account_config_requires_env_vars -v`
