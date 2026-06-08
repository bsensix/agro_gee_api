# Remover Endpoints Core e PostgreSQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remover os endpoints `users`, `farms`, `fields` e `whatsapp`, e garantir que a API rode e teste no fluxo padrao sem PostgreSQL.

**Architecture:** A aplicacao passa a operar em modo stateless no runtime principal. O `main.py` deixa de registrar rotas e handlers ligados ao banco, e a base de testes/docs/compose e alinhada para nao depender de `db`. Qualquer codigo legado de banco fica fora do caminho de importacao da API ativa.

**Tech Stack:** FastAPI, Pytest, Docker Compose, Python 3.12

---

## File Structure Map

### Runtime/API
- Modify: `agro_gee_api/main.py`
  - Remover routers `users/farms/fields/whatsapp`
  - Remover import e handler de `psycopg.OperationalError`

### Dependencias e ambiente
- Modify: `pyproject.toml`
  - Remover `psycopg[binary]` de runtime
- Modify: `docker-compose.yml`
  - Remover dependencia obrigatoria de `db` e envs `POSTGRES_*` do servico da API
- Modify: `.env.example`
  - Remover variaveis `POSTGRES_*` do baseline
- Create/Test: `tests/test_runtime_no_postgres_contract.py`

### CI/comando padrao
- Modify: `.github/workflows/ci.yml` (se necessario)
  - Garantir comando padrao de teste sem PostgreSQL

### Testes
- Modify: `tests/test_routes_registration.py`
  - Validar somente rotas de dominio ativas
  - Adicionar assercao explicita de 404 para rotas removidas
  - Adicionar contrato OpenAPI sem paths removidos
- Modify: `tests/test_platform_smoke.py`
  - Remover smoke de `pg_isready`
- Delete: `tests/test_db_resilience.py`
- Delete: `tests/test_core_crud_api_integration.py`
- Delete: `tests/test_database_extensions.py`
- Delete: `tests/test_core_entities_migration.py`
- Modify: `tests/conftest.py`
  - Remover fixtures e imports de DB
- Modify: `tests/test_gee_route.py` (se necessario)
  - Remover dependencias indiretas de `clean_core_tables`/entidades de DB

### Documentacao
- Modify: `README.md`
  - Atualizar stack, rotas principais e execucao sem PostgreSQL

### Verificacao final
- Use command checks on:
  - `pytest -v`
  - `python -m uvicorn agro_gee_api.main:app --port 8001`
  - Checagem HTTP de `/health` e 404 nas rotas removidas

---

### Task 1: Travar contrato de rotas sem DB (TDD)

**Files:**
- Modify: `tests/test_routes_registration.py`
- Test: `tests/test_routes_registration.py`

- [ ] **Step 1: Escrever teste que falha para rotas removidas**

```python
def test_removed_core_domains_return_404() -> None:
    client = TestClient(app)

    for path in ("/users", "/farms", "/fields", "/whatsapp/ping"):
        response = client.get(path)
        assert response.status_code == 404
```

- [ ] **Step 2: Ajustar teste de registro de rotas ativas**

```python
for path in ("/auth/ping", "/gee/ping", "/analytics/ping"):
    response = client.get(path)
    assert response.status_code == 200
```

- [ ] **Step 3: Adicionar teste automatizado de contrato OpenAPI**

```python
def test_openapi_does_not_expose_removed_core_domains() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json().get("paths", {})

    for prefix in ("/users", "/farms", "/fields", "/whatsapp"):
        assert not any(path == prefix or path.startswith(f"{prefix}/") for path in paths)
```

- [ ] **Step 4: Rodar teste para confirmar falha inicial**

Run: `pytest tests/test_routes_registration.py -v`
Expected: FAIL porque `main.py` ainda registra `whatsapp/users/farms/fields`

- [ ] **Step 5: Commit do teste vermelho**

```bash
git add tests/test_routes_registration.py
git commit -m "test: define 404 contract for removed core routes"
```

---

### Task 2: Remover routers e handler de PostgreSQL do runtime

**Files:**
- Modify: `agro_gee_api/main.py`
- Test: `tests/test_routes_registration.py`
- Test: `tests/test_platform_smoke.py`

- [ ] **Step 1: Remover imports de `psycopg` e routers core**

```python
from agro_gee_api.routes.analytics import router as analytics_router
from agro_gee_api.routes.auth import router as auth_router
from agro_gee_api.routes.gee import router as gee_router
```

- [ ] **Step 2: Remover include_router de dominios removidos**

```python
app.include_router(auth_router)
app.include_router(gee_router)
app.include_router(analytics_router)
```

- [ ] **Step 3: Remover exception handler de `psycopg.OperationalError`**

```python
# remover bloco @app.exception_handler(psycopg.OperationalError)
```

- [ ] **Step 4: Rodar testes focados para validar ajuste**

Run: `pytest tests/test_routes_registration.py tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Commit da mudanca de runtime**

```bash
git add agro_gee_api/main.py tests/test_routes_registration.py
git commit -m "refactor: run API without core DB-backed routers"
```

---

### Task 3: Remover dependencia PostgreSQL de runtime e compose

**Files:**
- Modify: `pyproject.toml`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Create/Test: `tests/test_runtime_no_postgres_contract.py`

- [ ] **Step 1: Escrever teste vermelho de contrato sem PostgreSQL no runtime**

```python
from pathlib import Path


def test_runtime_contract_has_no_postgres_dependency_or_env_baseline() -> None:
    project_root = Path(__file__).resolve().parents[1]
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")
    env_example = (project_root / ".env.example").read_text(encoding="utf-8")
    compose = (project_root / "docker-compose.yml").read_text(encoding="utf-8")
    main_py = (project_root / "agro_gee_api" / "main.py").read_text(encoding="utf-8")

    assert "psycopg" not in pyproject
    assert "POSTGRES_" not in env_example
    assert "POSTGRES_" not in env_example
    assert "depends_on:" not in compose or "db:" not in compose
    assert "import psycopg" not in main_py


def test_active_runtime_modules_do_not_import_db_or_psycopg() -> None:
    project_root = Path(__file__).resolve().parents[1]
    forbidden = (
        "import psycopg",
        "from psycopg",
        "import agro_gee_api.db",
        "from agro_gee_api.db",
    )
    active_runtime_files = [
        project_root / "agro_gee_api" / "main.py",
        project_root / "agro_gee_api" / "routes" / "auth.py",
        project_root / "agro_gee_api" / "routes" / "analytics.py",
        project_root / "agro_gee_api" / "routes" / "gee.py",
    ]

    for file_path in active_runtime_files:
        text = file_path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), file_path
```

- [ ] **Step 2: Rodar teste para confirmar falha inicial**

Run: `pytest tests/test_runtime_no_postgres_contract.py -v`
Expected: FAIL antes das mudancas de dependencia/compose/env/runtime

- [ ] **Step 3: Remover `psycopg[binary]` de `pyproject.toml`**

```toml
dependencies = [
    "fastapi>=0.115,<1.0",
    "uvicorn[standard]>=0.30,<1.0",
    "earthengine-api>=1.5,<2.0",
]
```

- [ ] **Step 4: Remover servico `db` e `depends_on` do compose**

```yaml
services:
  agro_gee_api:
    build:
      context: .
      dockerfile: infrastructure/docker/api.Dockerfile
```

- [ ] **Step 5: Remover env vars `POSTGRES_*` do servico da API e `.env.example`**

```env
# manter apenas variaveis necessarias ao runtime atual
API_PORT=8000
```

- [ ] **Step 6: Rodar contrato sem PostgreSQL para validar green**

Run: `pytest tests/test_runtime_no_postgres_contract.py -v`
Expected: PASS validando runtime sem imports de DB e sem dependencia obrigatoria de POSTGRES no fluxo principal

- [ ] **Step 7: Se existir lockfile Python versionado, atualizar lock sem `psycopg`**

Run (somente se lockfile existir no repositorio):
- comando de lock padrao do projeto
- validar diff sem entrada `psycopg`

- [ ] **Step 8: Commit de dependencia/infra**

```bash
git add pyproject.toml docker-compose.yml .env.example tests/test_runtime_no_postgres_contract.py
git commit -m "chore: remove postgres runtime and compose requirements"
```

---

### Task 3.1: Alinhar CI/comando padrao sem PostgreSQL

**Files:**
- Modify: `.github/workflows/ci.yml` (se necessario)
- Test: `tests/test_ci_contract.py`

- [ ] **Step 1: Validar job padrao de testes sem servico DB**

Run: `pytest tests/test_ci_contract.py -v`
Expected: PASS com `pytest` em modo rapido sem exigir compose/db

- [ ] **Step 2: Se necessario, ajustar CI para explicitar baseline sem PostgreSQL**

```yaml
- name: Run fast tests
  run: pytest -v -m "not integration"
```

- [ ] **Step 3: Commit de alinhamento CI (somente se houver alteracao)**

```bash
git add .github/workflows/ci.yml tests/test_ci_contract.py
git commit -m "ci: keep default test flow postgres-free"
```

---

### Task 4: Limpar base de testes acoplada ao banco

**Files:**
- Modify: `tests/conftest.py`
- Delete: `tests/test_db_resilience.py`
- Delete: `tests/test_core_crud_api_integration.py`
- Delete: `tests/test_database_extensions.py`
- Delete: `tests/test_core_entities_migration.py`
- Modify: `tests/test_platform_smoke.py`
- Modify: `tests/test_gee_route.py` (apenas se houver fixture/fluxo de DB)

- [ ] **Step 1: Escrever/ajustar teste de smoke de compose sem DB**

```python
def test_api_healthcheck_on_exposed_port() -> None:
    ...

# remover teste test_postgres_ready_inside_compose
```

- [ ] **Step 2: Rodar testes de smoke para confirmar falha antes da limpeza completa**

Run: `pytest tests/test_platform_smoke.py -v`
Expected: FAIL enquanto existir teste postgres

- [ ] **Step 3: Remover fixtures de banco de `tests/conftest.py`**

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

- [ ] **Step 4: Excluir suites estritamente DB-backed**

Delete files:
- `tests/test_db_resilience.py`
- `tests/test_core_crud_api_integration.py`
- `tests/test_database_extensions.py`
- `tests/test_core_entities_migration.py`

- [ ] **Step 5: Verificar `tests/test_gee_route.py` para dependencia de `clean_core_tables` e ajustar se necessario**

```python
# remover parametro clean_core_tables dos testes que nao precisam dele
def test_gee_datasets_returns_seeded_active_catalog() -> None:
    ...
```

- [ ] **Step 6: Rodar subset de testes afetados**

Run: `pytest tests/test_platform_smoke.py tests/test_gee_route.py -v`
Expected: PASS

- [ ] **Step 7: Commit da limpeza de testes**

```bash
git add tests/conftest.py tests/test_platform_smoke.py tests/test_gee_route.py
git rm tests/test_db_resilience.py tests/test_core_crud_api_integration.py tests/test_database_extensions.py tests/test_core_entities_migration.py
git commit -m "test: remove postgres-coupled suites and fixtures"
```

---

### Task 5: Atualizar documentacao e validar OpenAPI

**Files:**
- Modify: `README.md`
- Test: runtime local (`uvicorn`)

- [ ] **Step 1: Atualizar secoes de stack e rotas principais no README**

```md
- Banco: nao aplicavel no runtime principal
- Rotas principais: auth, analytics, gee
```

- [ ] **Step 2: Atualizar instrucoes de execucao para fluxo sem PostgreSQL**

```md
docker compose up -d --build
```

- [ ] **Step 3: Subir API local sem `POSTGRES_*`**

Run: `python -m uvicorn agro_gee_api.main:app --port 8001`
Expected: startup sem erro de import/conexao DB

- [ ] **Step 4: Validar contratos HTTP principais (comando portavel em Python)**

Run:
- `python - <<'PY'
from urllib.request import urlopen
from urllib.error import HTTPError

def status(url: str) -> int:
    try:
        with urlopen(url, timeout=3) as response:
            return response.status
    except HTTPError as exc:
        return exc.code

print('/health', status('http://127.0.0.1:8001/health'))
for path in ('/users', '/farms', '/fields', '/whatsapp/ping'):
    print(path, status(f'http://127.0.0.1:8001{path}'))
PY`

Expected:
- `/health` -> 200
- rotas removidas -> 404

- [ ] **Step 5: Validar OpenAPI e `/docs` sem rotas removidas**

Run: `curl http://127.0.0.1:8001/openapi.json`
Run: `curl http://127.0.0.1:8001/docs`
Expected: JSON/UI carregam e nao expoem paths iniciados por `/users`, `/farms`, `/fields`, `/whatsapp`

- [ ] **Step 6: Commit de documentacao**

```bash
git add README.md
git commit -m "docs: align API docs with stateless runtime"
```

---

### Task 6: Verificacao final de regressao

**Files:**
- No file changes expected

- [ ] **Step 1: Rodar suite padrao completa**

Run: `pytest -v`
Expected: PASS sem dependencia de PostgreSQL

- [ ] **Step 2: Revisar `git status` e diffs para garantir escopo**

Run: `git status --short`
Expected: arvore limpa apos commits ou apenas alteracoes planejadas

- [ ] **Step 3: Preparar nota de breaking change para PR/changelog**

Texto sugerido:

```md
Breaking change: endpoints `/users`, `/farms`, `/fields` e `/whatsapp` foram removidos.
O runtime padrao da API nao depende mais de PostgreSQL.
```

- [ ] **Step 4: Verificar startup/request path sem import de DB**

Run: `pytest tests/test_runtime_no_postgres_contract.py tests/test_routes_registration.py -v`
Expected: PASS com ausencia de `psycopg`/`POSTGRES_*` no runtime principal e 404 nas rotas removidas

- [ ] **Step 5: Rodar varredura abrangente de imports proibidos no caminho ativo**

Run: `rg "agro_gee_api\.db|psycopg" agro_gee_api`
Expected: sem ocorrencias em `agro_gee_api/main.py`, `agro_gee_api/routes/auth.py`, `agro_gee_api/routes/analytics.py`, `agro_gee_api/routes/gee.py`

---

## Sequencia de execucao recomendada

1. Task 1 -> Task 2 (contrato de rotas e runtime)
2. Task 3 (dependencias/compose/env)
3. Task 4 (limpeza de testes)
4. Task 5 (docs e OpenAPI)
5. Task 6 (regressao final)

## Observacoes de implementacao

- Evitar refatoracao ampla de modulos nao usados; aplicar YAGNI e manter foco na remocao solicitada.
- Se algum modulo legado de DB permanecer no repositorio, garantir que nao seja importado por `agro_gee_api/main.py` nem por rotas ativas.
- Se `tests/test_gee_route.py` ficar grande para ajuste, extrair somente o minimo necessario em arquivo dedicado para nao misturar comportamentos.
