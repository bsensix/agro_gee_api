# Fase 2B - GEE Endpoints Complementares Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar os itens pendentes da Fase 2 no roadmap (catalogo de datasets e endpoints Sentinel-2 complementares) mantendo contrato de erros rastreavel.

**Architecture:** Expandir `api/routes/gee.py` para incluir endpoints `GET /gee/datasets`, `POST /gee/sentinel2/extract/point`, `POST /gee/sentinel2/extract/polygon`, `POST /gee/sentinel2/timeseries` e `POST /gee/sentinel2/image`, delegando regras de dominio para novos services em `api/services`. O catalogo `core.gee_datasets` sera persistido no PostGIS para desacoplar descoberta de datasets da chamada externa e permitir validacao de disponibilidade por endpoint.

**Tech Stack:** Python 3.12, FastAPI, Psycopg/PostGIS, earthengine-api, Pytest.

---

## File Structure

- Create: `database/migrations/0003_gee_datasets.sql`
- Modify: `api/routes/gee.py`
- Create: `api/services/gee_catalog.py`
- Create: `api/services/gee_sentinel2_extract.py`
- Modify: `api/services/gee_client.py`
- Create: `tests/test_gee_catalog_service.py`
- Create: `tests/test_gee_extract_service.py`
- Modify: `tests/test_gee_route.py`
- Modify: `tests/test_core_crud_api_integration.py`

### Task 1: Catalogo `gee_datasets` + endpoint `GET /gee/datasets`

**Files:**
- Create: `database/migrations/0003_gee_datasets.sql`
- Create: `api/services/gee_catalog.py`
- Modify: `api/routes/gee.py`
- Create: `tests/test_gee_catalog_service.py`
- Modify: `tests/test_gee_route.py`

- [ ] **Step 1: Escrever teste RED do service para listar datasets ativos ordenados**
- [ ] **Step 2: Rodar RED (`pytest tests/test_gee_catalog_service.py -v`)**
- [ ] **Step 3: Criar migration e service minimo para listar catalogo**
- [ ] **Step 4: Escrever teste RED da rota `GET /gee/datasets`**
- [ ] **Step 5: Implementar endpoint e validar schema de resposta**
- [ ] **Step 6: Rodar GREEN (`pytest tests/test_gee_catalog_service.py tests/test_gee_route.py -k datasets -v`)**

### Task 2: Endpoint `extract/point` (NDVI em ponto)

**Files:**
- Create: `api/services/gee_sentinel2_extract.py`
- Modify: `api/services/gee_client.py`
- Modify: `api/routes/gee.py`
- Create: `tests/test_gee_extract_service.py`
- Modify: `tests/test_gee_route.py`

- [ ] **Step 1: Escrever RED para validacoes de payload e datas no service de extract point**
- [ ] **Step 2: Rodar RED (`pytest tests/test_gee_extract_service.py -k point -v`)**
- [ ] **Step 3: Implementar minimo para `extract_point` no service**
- [ ] **Step 4: Escrever RED da rota `POST /gee/sentinel2/extract/point`**
- [ ] **Step 5: Implementar endpoint com mapeamento de erro padrao**
- [ ] **Step 6: Rodar GREEN (`pytest tests/test_gee_extract_service.py tests/test_gee_route.py -k extract_point -v`)**

### Task 3: Endpoints `extract/polygon`, `timeseries`, `image`

**Files:**
- Modify: `api/services/gee_sentinel2_extract.py`
- Modify: `api/services/gee_client.py`
- Modify: `api/routes/gee.py`
- Modify: `tests/test_gee_extract_service.py`
- Modify: `tests/test_gee_route.py`

- [ ] **Step 1: Escrever RED para cada operacao (`extract/polygon`, `timeseries`, `image`)**
- [ ] **Step 2: Rodar RED parcial por operacao**
- [ ] **Step 3: Implementar minimo de cada operacao no service**
- [ ] **Step 4: Implementar endpoints correspondentes na rota**
- [ ] **Step 5: Rodar GREEN (`pytest tests/test_gee_extract_service.py tests/test_gee_route.py -k "polygon or timeseries or image" -v`)**

### Task 4: Integracao e regressao da Fase 2

**Files:**
- Modify: `tests/test_core_crud_api_integration.py`

- [ ] **Step 1: Escrever RED de integracao para `GET /gee/datasets`**
- [ ] **Step 2: Escrever RED de integracao para ao menos um endpoint de extract**
- [ ] **Step 3: Rodar RED (`pytest -m integration tests/test_core_crud_api_integration.py -k "gee and (datasets or extract)" -v`)**
- [ ] **Step 4: Ajustar wiring minimo para GREEN**
- [ ] **Step 5: Rodar GREEN (`pytest -m integration tests/test_core_crud_api_integration.py -k "gee and (datasets or extract)" -v`)**

## Final Verification

- [ ] `pytest tests/test_gee_client.py tests/test_gee_service.py tests/test_gee_catalog_service.py tests/test_gee_extract_service.py tests/test_gee_route.py -v`
- [ ] `pytest -q -m "not integration"`
- [ ] `pytest -m integration tests/test_core_crud_api_integration.py -k gee -v`
