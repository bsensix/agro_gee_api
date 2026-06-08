# Segmentacao Swagger por Tipo de Dado GEE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Segmentar os endpoints `/gee/*` no Swagger/OpenAPI por tipo de dado (`gee-core`, `sentinel2`, `era5-land`, `ifs-forecast`) sem alterar paths nem contratos HTTP.

**Architecture:** A segmentacao sera feita com `tags=[...]` por operacao em `agro_gee_api/routes/gee.py`, removendo a tag generica do `APIRouter` para evitar vazamento de `gee` em todas as operacoes. A ordem e metadados de exibicao das tags serao centralizados em `openapi_tags` no `FastAPI(...)` em `agro_gee_api/main.py`. O contrato sera protegido por testes de OpenAPI com mapeamento exato `path+method -> tag`.

**Tech Stack:** FastAPI, OpenAPI/Swagger, Pytest, Python 3.12

---

## File Structure Map

### Runtime/API
- Modify: `agro_gee_api/routes/gee.py`
  - Remover `tags=["gee"]` do `APIRouter`
  - Definir `tags=[...]` por endpoint `/gee/*`
- Modify: `agro_gee_api/main.py`
  - Declarar `openapi_tags` com ordem e descricoes

### Testes de contrato
- Modify: `tests/test_routes_registration.py`
  - Adicionar contrato de segmentacao por tags no `openapi.json`
  - Validar ausencia da tag `gee` em operacoes `/gee/*`

### Verificacao manual
- No file changes expected
  - Conferir `/docs` apos subida local para validar agrupamento visual

---

### Task 1: Definir contrato OpenAPI de segmentacao (TDD RED)

**Files:**
- Modify: `tests/test_routes_registration.py`
- Test: `tests/test_routes_registration.py`

- [ ] **Step 1: Adicionar teste de mapeamento exato de tags por endpoint `/gee/*`**

```python
def test_openapi_gee_endpoints_are_segmented_by_data_type_tags() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    paths = schema.get("paths", {})

    expected = {
        ("/gee/ping", "get"): "gee-core",
        ("/gee/auth/test", "post"): "gee-core",
        ("/gee/datasets", "get"): "gee-core",
        ("/gee/sentinel2/extract/point", "post"): "sentinel2",
        ("/gee/sentinel2/extract/polygon", "post"): "sentinel2",
        ("/gee/era5-land/extract/point", "post"): "era5-land",
        ("/gee/era5-land/extract/polygon", "post"): "era5-land",
        ("/gee/datasets/era5-land/variables", "get"): "era5-land",
        ("/gee/ifs-forecast/extract/point", "post"): "ifs-forecast",
        ("/gee/ifs-forecast/extract/polygon", "post"): "ifs-forecast",
        ("/gee/datasets/ifs-forecast/variables", "get"): "ifs-forecast",
    }

    for (path, method), expected_tag in expected.items():
        operation = paths[path][method]
        assert operation.get("tags") == [expected_tag]
```

- [ ] **Step 2: Adicionar teste para rejeitar tag generica `gee` em operacoes `/gee/*`**

```python
def test_openapi_gee_operations_do_not_use_generic_gee_tag() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()

    for path, methods in schema.get("paths", {}).items():
        if not path.startswith("/gee/") and path != "/gee/ping":
            continue
        for operation in methods.values():
            tags = operation.get("tags", [])
            assert "gee" not in tags
```

- [ ] **Step 3: Adicionar teste para validar `openapi_tags` (ordem e nomes)**

```python
def test_openapi_tags_define_expected_gee_segment_order() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    tags = schema.get("tags", [])
    names = [item["name"] for item in tags]
    expected = ["auth", "analytics", "gee-core", "sentinel2", "era5-land", "ifs-forecast"]

    assert names == expected
    assert all(item.get("description", "").strip() for item in tags)
```

- [ ] **Step 3.1: Adicionar teste de invariante para toda operacao `/gee/*`**

```python
def test_every_gee_operation_has_single_allowed_segment_tag() -> None:
    client = TestClient(app)
    schema = client.get("/openapi.json").json()
    allowed = {"gee-core", "sentinel2", "era5-land", "ifs-forecast"}

    for path, methods in schema.get("paths", {}).items():
        if not path.startswith("/gee"):
            continue
        for operation in methods.values():
            tags = operation.get("tags", [])
            assert len(tags) == 1
            assert tags[0] in allowed
```

- [ ] **Step 4: Rodar teste para confirmar RED**

Run: `pytest tests/test_routes_registration.py -v`
Expected: FAIL com ausencia de tags segmentadas e/ou `openapi_tags` ainda nao definidos

- [ ] **Step 5: Commit do contrato vermelho**

```bash
git add tests/test_routes_registration.py
git commit -m "test: define OpenAPI tag segmentation contract for gee endpoints"
```

---

### Task 2: Implementar tags por endpoint no router GEE (TDD GREEN)

**Files:**
- Modify: `agro_gee_api/routes/gee.py`
- Test: `tests/test_routes_registration.py`

- [ ] **Step 1: Remover tag padrao do `APIRouter` GEE**

```python
router = APIRouter(prefix="/gee")
```

- [ ] **Step 2: Aplicar `tags=["gee-core"]` nos endpoints core**

```python
@router.get("/ping", tags=["gee-core"])
@router.post("/auth/test", response_model=GEEAuthTestResponse, tags=["gee-core"])
@router.get("/datasets", response_model=list[GEEDatasetResponse], tags=["gee-core"])
```

- [ ] **Step 3: Aplicar `tags=["sentinel2"]` nos endpoints Sentinel-2**

```python
@router.post("/sentinel2/extract/point", response_model=Sentinel2ExtractValueResponse, tags=["sentinel2"])
@router.post("/sentinel2/extract/polygon", response_model=Sentinel2ExtractValueResponse, tags=["sentinel2"])
```

- [ ] **Step 4: Aplicar tag `era5-land` nos endpoints meteo ERA5-Land**

```python
@router.post("/era5-land/extract/point", response_model=MeteoExtractResponse, tags=["era5-land"])
@router.post("/era5-land/extract/polygon", response_model=MeteoExtractResponse, tags=["era5-land"])
@router.get("/datasets/era5-land/variables", response_model=list[MeteoVariableResponse], tags=["era5-land"])
```

- [ ] **Step 4.1: Aplicar tag `ifs-forecast` nos endpoints meteo IFS**

```python

@router.post("/ifs-forecast/extract/point", response_model=MeteoExtractResponse, tags=["ifs-forecast"])
@router.post("/ifs-forecast/extract/polygon", response_model=MeteoExtractResponse, tags=["ifs-forecast"])
@router.get("/datasets/ifs-forecast/variables", response_model=list[MeteoVariableResponse], tags=["ifs-forecast"])
```

- [ ] **Step 5: Rodar contrato de rotas para validar GREEN parcial**

Run: `pytest tests/test_routes_registration.py -v`
Expected: testes de tag mapping passam ou falham somente por falta de `openapi_tags` globais

- [ ] **Step 6: Commit da segmentacao no router**

```bash
git add agro_gee_api/routes/gee.py
git commit -m "feat: segment gee endpoints by per-operation OpenAPI tags"
```

---

### Task 3: Definir metadados globais de tags no app (OpenAPI)

**Files:**
- Modify: `agro_gee_api/main.py`
- Test: `tests/test_routes_registration.py`

- [ ] **Step 1: Declarar `openapi_tags` com nomes e descricoes curtas**

```python
OPENAPI_TAGS = [
    {"name": "auth", "description": "Authentication endpoints"},
    {"name": "analytics", "description": "Analytics endpoints"},
    {"name": "gee-core", "description": "Core GEE runtime and catalog endpoints"},
    {"name": "sentinel2", "description": "Sentinel-2 extraction endpoints"},
    {"name": "era5-land", "description": "ERA5-Land extraction endpoints"},
    {"name": "ifs-forecast", "description": "IFS forecast extraction endpoints"},
]

app = FastAPI(title="Agro Insight API", openapi_tags=OPENAPI_TAGS)
```

- [ ] **Step 2: Rodar teste focado para validar ordem e consistencia de tags**

Run: `pytest tests/test_routes_registration.py -v`
Expected: PASS nos testes de segmentacao e contratos existentes

- [ ] **Step 3: Commit dos metadados de documentacao**

```bash
git add agro_gee_api/main.py
git commit -m "docs: define OpenAPI tag order for gee data segments"
```

---

### Task 4: Verificacao final e validacao visual no Swagger

**Files:**
- No file changes expected

- [ ] **Step 1: Rodar subset de regressao de contratos ativos**

Run: `pytest tests/test_runtime_no_postgres_contract.py tests/test_routes_registration.py -v`
Expected: PASS

- [ ] **Step 2: Rebuild/restart local para refletir schema novo**

Run: `docker compose up -d --build --force-recreate`
Expected: container API `Up` em `:8000`

- [ ] **Step 3: Validar OpenAPI por script local (sem dependencia externa)**

Run:
`python -c "import json,urllib.request; s=json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')); bad=[]; tags=set();
for p,m in s.get('paths',{}).items():
    if not p.startswith('/gee'):
        continue
    for op in m.values():
        t=op.get('tags',[])
        tags.update(t)
        if 'gee' in t:
            bad.append((p,t))
print('tags',sorted(tags)); print('bad',bad)"`

Expected: `tags` inclui `gee-core`, `sentinel2`, `era5-land`, `ifs-forecast` e `bad` e lista vazia

- [ ] **Step 4: Validacao visual manual no Swagger**

Run: abrir `http://127.0.0.1:8000/docs`
Expected: secoes separadas por tag (`gee-core`, `sentinel2`, `era5-land`, `ifs-forecast`) com endpoints agrupados corretamente

---

## Sequencia Recomendada

1. Task 1 (contrato RED)
2. Task 2 (GREEN em `routes/gee.py`)
3. Task 3 (metadados globais `openapi_tags`)
4. Task 4 (regressao e validacao visual)

## Guardrails de Implementacao

- Nao alterar paths, nomes de endpoints, models, auth ou logica de extracao.
- Evitar criar novos routers/submodulos (YAGNI para esta entrega).
- Todo endpoint `/gee/*` deve ter exatamente uma tag permitida: `gee-core`, `sentinel2`, `era5-land` ou `ifs-forecast`.
- Nao reintroduzir dependencia de PostgreSQL no runtime/testes desta mudanca.
