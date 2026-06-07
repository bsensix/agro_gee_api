# Fase 0 - Fundacao do Projeto Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subir a base tecnica do Agro Insight com ambiente local funcional, estrutura inicial de modulos e qualidade minima para iniciar o MVP.

**Architecture:** O plano cria uma fundacao modular com `api`, `database` e `airflow` rodando em containers e conectados via Docker Compose. A API FastAPI expoe healthcheck e estrutura de rotas por dominio. O banco PostGIS recebe migracao inicial para habilitar o trabalho geoespacial nas proximas fases.

**Tech Stack:** Python, FastAPI, PostgreSQL, PostGIS, Docker, Docker Compose, Airflow, pytest

---

## Semana 1 (Fase 0)

### Dia 1 - Bootstrap do repositorio e padroes

### Task 1: Estrutura inicial do projeto

**Files:**
- Create: `README.md`
- Create: `.gitignore`
- Create: `.editorconfig`
- Create: `.env.example`
- Create: `api/main.py`
- Create: `api/routes/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Criar teste de smoke inicial (falhando primeiro)**

```python
from fastapi.testclient import TestClient
from agro_gee_api.main import app


def test_healthcheck_returns_200():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 2: Rodar teste para confirmar falha inicial**

Run: `pytest tests/test_smoke.py -v`
Expected: FAIL com erro de import/app nao definida.

- [ ] **Step 3: Implementar `api/main.py` minimo com `/health`**

```python
from fastapi import FastAPI

app = FastAPI(title="Agro Insight API")


@app.get("/health")
def healthcheck() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Rodar teste novamente para validar sucesso**

Run: `pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md .gitignore .editorconfig .env.example api/main.py api/routes/__init__.py tests/test_smoke.py
git commit -m "chore: bootstrap project structure and healthcheck smoke test"
```

---

### Dia 2 - Plataforma local com Docker e PostGIS

### Task 2: Ambiente local containerizado

**Files:**
- Create: `docker-compose.yml`
- Create: `infrastructure/docker/api.Dockerfile`
- Create: `infrastructure/docker/airflow.Dockerfile`
- Modify: `.env.example`

- [ ] **Step 1: Definir teste de disponibilidade da API e banco**

```python
import socket


def test_postgres_port_open_locally():
    s = socket.socket()
    assert s.connect_ex(("127.0.0.1", 5432)) == 0
    s.close()
```

- [ ] **Step 2: Rodar teste para confirmar falha antes de subir containers**

Run: `pytest tests/test_platform_smoke.py -v`
Expected: FAIL (porta fechada).

- [ ] **Step 3: Implementar `docker-compose.yml` com servicos `api`, `db`, `airflow`**

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    ports: ["5432:5432"]
  api:
    build:
      context: .
      dockerfile: infrastructure/docker/api.Dockerfile
    ports: ["8000:8000"]
  airflow:
    build:
      context: .
      dockerfile: infrastructure/docker/airflow.Dockerfile
```

- [ ] **Step 4: Subir stack e validar teste**

Run: `docker compose up -d && pytest tests/test_platform_smoke.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml infrastructure/docker/api.Dockerfile infrastructure/docker/airflow.Dockerfile .env.example tests/test_platform_smoke.py
git commit -m "chore: add local docker stack with api postgis and airflow"
```

---

### Dia 3 - Banco geoespacial e migracao inicial

### Task 3: Esquema inicial com PostGIS

**Files:**
- Create: `database/migrations/0001_init.sql`
- Create: `database/schemas/base.sql`
- Create: `database/seeds/seed_minimal.sql`
- Create: `tests/test_database_extensions.py`

- [ ] **Step 1: Escrever teste de extensao PostGIS (falhando primeiro)**

```python
import psycopg


def test_postgis_extension_is_enabled():
    with psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5432/agro_insight") as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname='postgis';")
            assert cur.fetchone()[0] == "postgis"
```

- [ ] **Step 2: Rodar teste para confirmar falha inicial**

Run: `pytest tests/test_database_extensions.py -v`
Expected: FAIL (extensao ausente).

- [ ] **Step 3: Criar migracao inicial habilitando PostGIS e schema base**

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS core;
```

- [ ] **Step 4: Aplicar migracao e reexecutar teste**

Run: `psql -h 127.0.0.1 -U postgres -d agro_insight -f database/migrations/0001_init.sql && pytest tests/test_database_extensions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add database/migrations/0001_init.sql database/schemas/base.sql database/seeds/seed_minimal.sql tests/test_database_extensions.py
git commit -m "feat: add initial postgis migration and database smoke tests"
```

---

### Dia 4 - API modular e contratos iniciais

### Task 4: Estrutura de rotas por dominio

**Files:**
- Create: `api/routes/auth.py`
- Create: `api/routes/gee.py`
- Create: `api/routes/analytics.py`
- Create: `api/routes/whatsapp.py`
- Modify: `api/main.py`
- Create: `tests/test_routes_registration.py`

- [ ] **Step 1: Escrever teste de registro de rotas (falhando primeiro)**

```python
from fastapi.testclient import TestClient
from agro_gee_api.main import app


def test_domain_routes_are_registered():
    client = TestClient(app)
    assert client.get("/auth/ping").status_code == 200
    assert client.get("/gee/ping").status_code == 200
    assert client.get("/analytics/ping").status_code == 200
    assert client.get("/whatsapp/ping").status_code == 200
```

- [ ] **Step 2: Rodar teste para confirmar falha inicial**

Run: `pytest tests/test_routes_registration.py -v`
Expected: FAIL (rotas ausentes).

- [ ] **Step 3: Implementar roteadores minimos por dominio e incluir no app**

```python
from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/ping")
def ping() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Reexecutar teste para validar sucesso**

Run: `pytest tests/test_routes_registration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/main.py api/routes/auth.py api/routes/gee.py api/routes/analytics.py api/routes/whatsapp.py tests/test_routes_registration.py
git commit -m "feat: add modular fastapi routes for core domains"
```

---

### Dia 5 - Qualidade minima, seguranca base e fechamento da fase

### Task 5: Qualidade e seguranca baseline

**Files:**
- Create: `pyproject.toml`
- Create: `pytest.ini`
- Create: `docs/security-baseline.md`
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

- [ ] **Step 1: Criar teste de pipeline local (falhando primeiro)**

```python
def test_ci_contract_marker_present():
    with open(".github/workflows/ci.yml", "r", encoding="utf-8") as f:
        content = f.read()
    assert "pytest" in content
```

- [ ] **Step 2: Rodar teste para confirmar falha inicial**

Run: `pytest tests/test_ci_contract.py -v`
Expected: FAIL (`ci.yml` nao existe).

- [ ] **Step 3: Implementar baseline de qualidade (lint/test) e seguranca minima**

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest -v
```

- [ ] **Step 4: Rodar validacao final da fase**

Run: `pytest -v && docker compose ps`
Expected: testes PASS e servicos principais ativos.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml pytest.ini docs/security-baseline.md .github/workflows/ci.yml README.md tests/test_ci_contract.py
git commit -m "chore: establish quality baseline ci and security checklist"
```

---

## Checkpoint de encerramento da Fase 0

- [ ] API responde `GET /health` com 200.
- [ ] Stack sobe com `docker compose up -d`.
- [ ] PostGIS habilitado e migracao inicial aplicada.
- [ ] Rotas base por dominio registradas.
- [ ] Suite smoke e integracao basica passando.

## Riscos e mitigacoes

- Dependencias externas (GCP/OpenAI/WhatsApp) ainda sem credencial: usar mocks nesta fase.
- Drift entre ambiente local e CI: padronizar comandos no `README.md` e no workflow.
- Falhas intermitentes no startup dos containers: adicionar healthchecks no compose.

## Handoff para proxima fase

- Proxima execucao: iniciar `Fase 1 - Cadastros essenciais`.
- Entrada minima: ambiente local estavel + migracao base + testes smoke verdes.
