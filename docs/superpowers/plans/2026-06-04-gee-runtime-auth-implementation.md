# GEE Runtime Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar autenticacao real do Google Earth Engine com `ee.Initialize(...)`, expor endpoint de diagnostico `POST /gee/auth/test` e conectar os endpoints GEE existentes a consultas reais.

**Architecture:** A inicializacao do Earth Engine fica centralizada em um runtime singleton com lock e estado em memoria (`api/services/gee_runtime.py`). O cliente GEE concreto usa esse runtime antes de executar operacoes e normaliza erros para um contrato unico. O router GEE passa a depender desse cliente real e expor um endpoint de autenticacao/diagnostico protegido.

**Tech Stack:** Python 3.12, FastAPI, earthengine-api, pytest, Docker Compose.

---

## File Structure

- Create: `api/services/gee_runtime.py` (inicializacao `ee.Initialize`, estado, lock, health check)
- Modify: `api/services/gee_client.py` (cliente real + mapeamento canonico de erros)
- Modify: `api/routes/gee.py` (endpoint `POST /gee/auth/test`, factories reais, authz)
- Modify: `api/routes/_authz.py` (regra de acesso admin/internal para auth diagnostic)
- Modify: `docker-compose.yml` (env vars GEE no servico `api`)
- Modify: `.env.example` (documentar vars GEE)
- Create: `tests/test_gee_runtime.py` (unitarios de runtime)
- Modify: `tests/test_gee_client.py` (cobertura de erro fallback `GEE_INTERNAL_ERROR`)
- Modify: `tests/test_gee_route.py` (contrato de `POST /gee/auth/test` + erros)
- Modify: `tests/test_core_crud_api_integration.py` (smoke de auth test com monkeypatch)

### Task 1: Runtime Earth Engine (`gee_runtime`)

**Files:**
- Create: `api/services/gee_runtime.py`
- Test: `tests/test_gee_runtime.py`

- [ ] **Step 1: Write failing tests for auth mode resolution and initialization**

```python
def test_resolve_auth_mode_auto_prefers_service_account():
    ...

def test_resolve_auth_mode_oauth_requires_oauth_credentials():
    ...

def test_resolve_auth_mode_auto_falls_back_to_oauth_when_sa_missing():
    ...

def test_resolve_auth_mode_requires_project_id_in_all_modes():
    ...

def test_private_key_normalizes_escaped_newlines():
    ...

def test_ensure_initialized_sets_state_on_success():
    ...

def test_ensure_initialized_force_recheck_runs_health_probe_again():
    ...

def test_ensure_initialized_concurrent_calls_initialize_once():
    ...

def test_transient_error_does_not_poison_credentials_state():
    ...

def test_ensure_initialized_maps_unknown_error_to_internal_error():
    ...

def test_runtime_sanitizes_sensitive_error_messages():
    ...
```

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/test_gee_runtime.py -v`
Expected: FAIL (module/class/function missing)

- [ ] **Step 3: Implement minimal runtime with lock/state**

```python
class EarthEngineRuntime:
    def ensure_initialized(self, *, force_recheck: bool = False) -> RuntimeStatus: ...
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest tests/test_gee_runtime.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/services/gee_runtime.py tests/test_gee_runtime.py
git commit -m "feat: add earth engine runtime initialization service"
```

### Task 2: Cliente GEE real + contrato canonico de erros

**Files:**
- Modify: `api/services/gee_client.py`
- Test: `tests/test_gee_client.py`

- [ ] **Step 1: Write failing tests for canonical error mapping in all operations**

```python
def test_ndvi_mean_maps_unknown_ee_error_to_internal_error():
    ...

def test_extract_point_maps_auth_error_to_gee_auth_failed():
    ...

def test_extract_polygon_maps_timeout_to_gee_timeout():
    ...

def test_timeseries_maps_unavailable_to_gee_unavailable():
    ...

def test_image_maps_unknown_ee_error_to_internal_error():
    ...
```

- [ ] **Step 2: Run targeted tests to verify RED**

Run: `pytest tests/test_gee_client.py -v`
Expected: FAIL in new cases

- [ ] **Step 3: Implement concrete client methods using ee API**

```python
class EarthEngineClient:
    def ndvi_mean(...): ...
    def extract_point(...): ...
    def extract_polygon(...): ...
    def timeseries(...): ...
    def image(...): ...
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest tests/test_gee_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/services/gee_client.py tests/test_gee_client.py
git commit -m "feat: implement earth engine client operations and error mapping"
```

### Task 3: Endpoint `POST /gee/auth/test`

**Files:**
- Modify: `api/routes/gee.py`
- Modify: `api/routes/_authz.py`
- Test: `tests/test_gee_route.py`

- [ ] **Step 1: Write failing route tests for auth diagnostic endpoint**

```python
def test_post_gee_auth_test_returns_200_status_payload(monkeypatch):
    ...

def test_post_gee_auth_test_returns_mapped_auth_failed(monkeypatch):
    ...

def test_post_gee_auth_test_returns_mapped_unavailable(monkeypatch):
    ...

def test_post_gee_auth_test_returns_mapped_internal_error(monkeypatch):
    ...

def test_post_gee_auth_test_returns_403_for_non_admin_user(monkeypatch):
    ...

def test_post_gee_auth_test_returns_200_for_internal_scope_user(monkeypatch):
    ...

def test_post_gee_auth_test_returns_404_when_feature_flag_disabled(monkeypatch):
    ...
```

- [ ] **Step 2: Run targeted tests to verify RED**

Run: `pytest tests/test_gee_route.py -k auth_test -v`
Expected: FAIL (`/gee/auth/test` missing)

- [ ] **Step 3: Implement endpoint and authz/feature-flag checks**

```python
@router.post("/auth/test")
def post_gee_auth_test(...):
    ...
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `pytest tests/test_gee_route.py -k auth_test -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/routes/gee.py tests/test_gee_route.py
git commit -m "feat: add gee auth diagnostic endpoint"
```

### Task 4: Wiring dos endpoints GEE existentes para runtime real

**Files:**
- Modify: `api/routes/gee.py`
- Modify: `tests/test_gee_route.py`
- Modify: `tests/test_core_crud_api_integration.py`

- [ ] **Step 1: Write failing tests for data endpoints using real client factory path**

```python
def test_post_sentinel2_stats_maps_runtime_internal_error(monkeypatch):
    ...

def test_post_extract_point_maps_auth_failed(monkeypatch):
    ...

def test_post_extract_polygon_maps_unavailable(monkeypatch):
    ...

def test_post_timeseries_maps_timeout(monkeypatch):
    ...

def test_integration_gee_auth_test_smoke_with_runtime_monkeypatch(...):
    ...

def test_integration_extract_point_maps_auth_failed(...):
    ...

def test_integration_extract_polygon_maps_unavailable(...):
    ...

def test_integration_timeseries_maps_timeout(...):
    ...
```

- [ ] **Step 2: Run tests to verify RED**

Run: `pytest tests/test_gee_route.py tests/test_core_crud_api_integration.py -k "gee and auth_test" -v`
Expected: FAIL in new cases

- [ ] **Step 3: Implement factory wiring with `EarthEngineClient` + runtime singleton**

```python
def get_gee_client() -> GEEClient:
    ...
```

- [ ] **Step 4: Run targeted tests to verify GREEN**

Run: `pytest tests/test_gee_route.py tests/test_core_crud_api_integration.py -k gee -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add api/routes/gee.py tests/test_gee_route.py tests/test_core_crud_api_integration.py
git commit -m "feat: wire gee endpoints to runtime-initialized client"
```

### Task 5: Configuracao Docker/env + regressao final

**Files:**
- Modify: `docker-compose.yml`
- Modify: `.env.example`

- [ ] **Step 1: Implement env vars in compose and example env docs**

Add:

```env
GEE_AUTH_MODE=auto
GEE_PROJECT_ID=
GEE_SERVICE_ACCOUNT_EMAIL=
GEE_PRIVATE_KEY=
GEE_OAUTH_CLIENT_ID=
GEE_OAUTH_CLIENT_SECRET=
GEE_OAUTH_REFRESH_TOKEN=
GEE_AUTH_TEST_ENABLED=true
```

- [ ] **Step 2: Implement and test default-by-environment behavior for `GEE_AUTH_TEST_ENABLED`**

```python
def test_auth_test_enabled_defaults_true_in_dev(monkeypatch):
    ...

def test_auth_test_enabled_defaults_false_in_prod(monkeypatch):
    ...
```

Run: `pytest tests/test_gee_route.py -k "auth_test_enabled_defaults" -v`
Expected: PASS

- [ ] **Step 3: Run complete non-integration suite**

Run: `pytest -q -m "not integration"`
Expected: PASS

- [ ] **Step 4: Run integration subset for GEE contracts**

Run: `pytest -m integration tests/test_core_crud_api_integration.py -k gee -v`
Expected: PASS

- [ ] **Step 5: Manual Docker verification**

Run:

```bash
docker compose up -d --build api
curl -X POST http://localhost:8000/gee/auth/test -H "X-User-Id: <admin_user_id>"
curl -X POST http://localhost:8000/gee/auth/test -H "X-User-Id: <non_admin_user_id>"
```

Expected: primeira chamada retorna `status=ok` com credenciais validas; segunda retorna erro de autorizacao.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml .env.example
git commit -m "chore: add gee runtime env configuration"
```

## Final Verification

- [ ] `pytest tests/test_gee_runtime.py tests/test_gee_client.py tests/test_gee_route.py -v`
- [ ] `pytest -q -m "not integration"`
- [ ] `pytest -m integration tests/test_core_crud_api_integration.py -k gee -v`
- [ ] `docker compose up -d --build api && curl -s -X POST http://localhost:8000/gee/auth/test`
