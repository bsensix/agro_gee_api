# Remover cloud_pct das respostas meteo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover o campo `cloud_pct` das respostas `series[]` dos endpoints meteo (`era5-land` e `ifs-forecast`) sem alterar paths nem logica de extracao.

**Architecture:** A mudanca sera feita no contrato HTTP de saida em `agro_gee_api/routes/gee.py`, ajustando o model Pydantic de item de serie meteo e mantendo o mapeamento de dados com apenas `date` e `value`. A seguranca da entrega sera garantida por testes de contrato de rota e por verificacao do schema OpenAPI para impedir reintroducao de `cloud_pct`.

**Tech Stack:** FastAPI, Pydantic, Pytest, OpenAPI/Swagger, Python 3.12

---

## File Structure Map

### Runtime/API
- Modify: `agro_gee_api/routes/gee.py`
  - Remover `cloud_pct` de `MeteoExtractSeriesItemResponse`
  - Manter respostas meteo serializadas somente com `date` e `value`

### Testes
- Modify: `tests/test_gee_route.py`
  - Adicionar/ajustar asserts para garantir ausencia de `cloud_pct` em `series[]` nos 4 endpoints meteo
- Modify (se necessario): `tests/test_routes_registration.py`
  - Sem alteracoes obrigatorias para esta feature

### Verificacao de schema
- No file changes expected
  - Validar `openapi.json` sem `cloud_pct` no schema meteo

---

### Task 1: Definir contrato RED para ausencia de cloud_pct

**Files:**
- Modify: `tests/test_gee_route.py`
- Test: `tests/test_gee_route.py`

- [ ] **Step 1: Escrever teste falhando para `era5-land` point sem `cloud_pct`**

```python
def test_post_era5_land_extract_point_series_does_not_expose_cloud_pct(monkeypatch) -> None:
    # Arrange
    class StubService:
        def extract_point(self, **kwargs):
            return {
                "dataset": "ECMWF/ERA5_LAND/HOURLY",
                "variable": "air_temperature_2m",
                "value": 300.1,
                "series": [{"date": "2024-01-01", "value": 300.1, "cloud_pct": 12.3}],
            }

    monkeypatch.setattr("agro_gee_api.routes.gee.get_meteo_extract_service", lambda: StubService())
    client = TestClient(app)

    # Act
    response = client.post(
        "/gee/era5-land/extract/point",
        json={"coordinates": [-47.88, -15.79], "date_start": "2024-01-01", "date_end": "2024-01-07", "variable": "air_temperature_2m"},
    )

    # Assert
    assert response.status_code == 200
    for item in response.json()["series"]:
        assert set(item.keys()) == {"date", "value"}
        assert "cloud_pct" not in item
```

- [ ] **Step 2: Escrever teste falhando para `era5-land` polygon sem `cloud_pct`**

```python
def test_post_era5_land_extract_polygon_series_does_not_expose_cloud_pct(monkeypatch) -> None:
    class StubService:
        def extract_polygon(self, **kwargs):
            return {
                "dataset": "ECMWF/ERA5_LAND/HOURLY",
                "variable": "air_temperature_2m",
                "value": 299.7,
                "series": [{"date": "2024-01-02", "value": 299.7, "cloud_pct": 9.4}],
            }

    monkeypatch.setattr("agro_gee_api.routes.gee.get_meteo_extract_service", lambda: StubService())
    client = TestClient(app)
    response = client.post(
        "/gee/era5-land/extract/polygon",
        json={
            "geometry": {"type": "Polygon", "coordinates": [[[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]]},
            "date_start": "2024-01-01",
            "date_end": "2024-01-07",
            "variable": "air_temperature_2m",
        },
    )
    assert response.status_code == 200
    for item in response.json()["series"]:
        assert set(item.keys()) == {"date", "value"}
        assert "cloud_pct" not in item
```

- [ ] **Step 3: Escrever teste falhando para `ifs-forecast` point sem `cloud_pct`**

```python
def test_post_ifs_forecast_extract_point_series_does_not_expose_cloud_pct(monkeypatch) -> None:
    class StubService:
        def extract_point(self, **kwargs):
            return {
                "dataset": "ECMWF/IFS/OPER",
                "variable": "surface_pressure",
                "value": 1012.4,
                "series": [{"date": "2024-01-03", "value": 1012.4, "cloud_pct": 0.1}],
            }

    monkeypatch.setattr("agro_gee_api.routes.gee.get_meteo_extract_service", lambda: StubService())
    client = TestClient(app)
    response = client.post(
        "/gee/ifs-forecast/extract/point",
        json={"coordinates": [-47.88, -15.79], "date_start": "2024-01-01", "date_end": "2024-01-07", "variable": "surface_pressure"},
    )
    assert response.status_code == 200
    for item in response.json()["series"]:
        assert set(item.keys()) == {"date", "value"}
        assert "cloud_pct" not in item
```

- [ ] **Step 4: Escrever teste falhando para `ifs-forecast` polygon sem `cloud_pct`**

```python
def test_post_ifs_forecast_extract_polygon_series_does_not_expose_cloud_pct(monkeypatch) -> None:
    class StubService:
        def extract_polygon(self, **kwargs):
            return {
                "dataset": "ECMWF/IFS/OPER",
                "variable": "surface_pressure",
                "value": 1009.2,
                "series": [{"date": "2024-01-04", "value": 1009.2, "cloud_pct": 3.7}],
            }

    monkeypatch.setattr("agro_gee_api.routes.gee.get_meteo_extract_service", lambda: StubService())
    client = TestClient(app)
    response = client.post(
        "/gee/ifs-forecast/extract/polygon",
        json={
            "geometry": {"type": "Polygon", "coordinates": [[[-47.9, -15.8], [-47.8, -15.8], [-47.8, -15.7], [-47.9, -15.7], [-47.9, -15.8]]]},
            "date_start": "2024-01-01",
            "date_end": "2024-01-07",
            "variable": "surface_pressure",
        },
    )
    assert response.status_code == 200
    for item in response.json()["series"]:
        assert set(item.keys()) == {"date", "value"}
        assert "cloud_pct" not in item
```

- [ ] **Step 5: Rodar RED em testes focados**

Run: `pytest tests/test_gee_route.py::test_post_era5_land_extract_point_series_does_not_expose_cloud_pct tests/test_gee_route.py::test_post_era5_land_extract_polygon_series_does_not_expose_cloud_pct tests/test_gee_route.py::test_post_ifs_forecast_extract_point_series_does_not_expose_cloud_pct tests/test_gee_route.py::test_post_ifs_forecast_extract_polygon_series_does_not_expose_cloud_pct -v`
Expected: FAIL em cada teste na assercao `set(item.keys()) == {"date", "value"}` (ou `"cloud_pct" not in item`) porque o contrato atual ainda inclui `cloud_pct`

- [ ] **Step 6: Commit do contrato vermelho**

```bash
git add tests/test_gee_route.py
git commit -m "test: define meteo response contract without cloud_pct"
```

---

### Task 2: Implementar mudanca de contrato no model meteo

**Files:**
- Modify: `agro_gee_api/routes/gee.py`
- Test: `tests/test_gee_route.py`

- [ ] **Step 1: Remover campo `cloud_pct` do model de serie meteo**

```python
class MeteoExtractSeriesItemResponse(BaseModel):
    date: str
    value: float
```

- [ ] **Step 2: Confirmar mapeamento de resposta usa o model atualizado**

```python
series=[MeteoExtractSeriesItemResponse(**item) for item in extract_result["series"]]
```

- [ ] **Step 2.1: Verificar explicitamente que campos extras internos nao chegam no HTTP**

Run: `pytest tests/test_gee_route.py::test_post_era5_land_extract_point_series_does_not_expose_cloud_pct -v`
Expected: PASS com `series[]` contendo apenas `date` e `value`

- [ ] **Step 3: Rodar teste focado para validar GREEN**

Run: `pytest tests/test_gee_route.py::test_post_era5_land_extract_point_series_does_not_expose_cloud_pct tests/test_gee_route.py::test_post_era5_land_extract_polygon_series_does_not_expose_cloud_pct tests/test_gee_route.py::test_post_ifs_forecast_extract_point_series_does_not_expose_cloud_pct tests/test_gee_route.py::test_post_ifs_forecast_extract_polygon_series_does_not_expose_cloud_pct -v`
Expected: PASS com ausencia de `cloud_pct` em `series[]`

- [ ] **Step 4: Rodar regressao do modulo de rota GEE**

Run: `pytest tests/test_gee_route.py -v`
Expected: PASS

- [ ] **Step 5: Commit da implementacao**

```bash
git add agro_gee_api/routes/gee.py tests/test_gee_route.py
git commit -m "feat: remove cloud_pct from meteo series response"
```

---

### Task 3: Validar OpenAPI e contrato final

**Files:**
- No file changes expected

- [ ] **Step 1: Rebuild/restart para refletir schema novo**

Run: `docker compose up -d --build --force-recreate`
Expected: container `agro_gee_api` em estado `Up`

- [ ] **Step 2: Verificar schema OpenAPI de meteo sem `cloud_pct` (cheque direcionado)**

Run:
`python -c "import json,urllib.request; s=json.load(urllib.request.urlopen('http://127.0.0.1:8000/openapi.json')); p=s['paths']; c=s.get('components',{}).get('schemas',{});
targets=[('/gee/era5-land/extract/point','post'),('/gee/era5-land/extract/polygon','post'),('/gee/ifs-forecast/extract/point','post'),('/gee/ifs-forecast/extract/polygon','post')];
def ref_name(x): return x.split('/')[-1]
bad=[]
for path,method in targets:
  rs=p[path][method]['responses']['200']['content']['application/json']['schema']
  root=c[ref_name(rs['$ref'])] if '$ref' in rs else rs
  series_items=root['properties']['series']['items']
  item=c[ref_name(series_items['$ref'])] if '$ref' in series_items else series_items
  props=item.get('properties',{})
  if 'cloud_pct' in props: bad.append(path)
print('bad',bad)"`

Expected: `bad []`

- [ ] **Step 3: Rodar suite de contratos relevantes**

Run: `pytest tests/test_runtime_no_postgres_contract.py tests/test_routes_registration.py tests/test_gee_route.py -v`
Expected: PASS

- [ ] **Step 4: Validacao manual de endpoint meteo**

Run (exemplo):
`curl -s -X POST http://127.0.0.1:8000/gee/era5-land/extract/point -H "Content-Type: application/json" -d "{\"coordinates\":[-47.88,-15.79],\"date_start\":\"2024-01-01\",\"date_end\":\"2024-01-07\",\"variable\":\"air_temperature_2m\"}"`

Expected: itens de `series[]` contendo apenas `date` e `value`

---

## Sequencia Recomendada

1. Task 1 (RED: contrato sem `cloud_pct`)
2. Task 2 (GREEN: model e mapeamento)
3. Task 3 (OpenAPI + regressao + validacao manual)

## Guardrails de Implementacao

- Nao alterar paths, metodos HTTP, validacoes ou logica de extracao GEE.
- Limitar escopo a payload de resposta meteo.
- Garantir que a mudanca vale para os 4 endpoints meteo (era5 point/polygon e ifs point/polygon).
- Registrar em PR/changelog como breaking change de contrato (`cloud_pct` removido).
