# Agro GEE API

<p align="center">
  <img src="logo_api.png" width="300"/>
</p>

API backend do projeto Agro Insight, focada em analytics e integracao com Google Earth Engine (GEE).

## Contexto da API

Esta API organiza os fluxos principais da plataforma em um unico servico FastAPI stateless:

- autenticacao e autorizacao de usuarios
- endpoints de analytics
- integracao com GEE para extracao e estatisticas Sentinel-2
- endpoint de saude para monitoramento (`/health`)
- sem dependencia de PostgreSQL no fluxo principal de runtime

Rotas principais por dominio:

- `auth`: `/auth`
- `analytics`: `/analytics`
- `gee`: `/gee`
- `health`: `/health`

## Stack e arquitetura

- Framework: FastAPI
- Runtime: stateless (sem PostgreSQL no fluxo principal)
- Containerizacao: Docker + Docker Compose
- Testes: Pytest

Arquivos de referencia:

- App entrypoint: `agro_gee_api/main.py`
- Compose local: `docker-compose.yml`
- Dockerfile da API: `infrastructure/docker/api.Dockerfile`

## Como rodar localmente

No diretorio raiz do projeto:

```bash
pip install -e .[dev]
uvicorn agro_gee_api.main:app --reload
```

## Como rodar com Docker

No diretorio raiz do projeto:

```bash
docker compose up -d --build
```

Verifique os containers:

```bash
docker compose ps
```

Docs interativas:

- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

Observacao: o app inicia sem variaveis `POSTGRES_*`.

## Rodando testes localmente

```bash
pip install -e .[dev]
pytest -v
```

## Validacoes realizadas

- `pytest tests/test_routes_registration.py tests/test_smoke.py -v`
  - esperado: confirmar runtime sem dependencia de PostgreSQL e contratos de rotas ativas/removidas
  - observado: 5 testes passaram (`5 passed`)
- Healthcheck sem variaveis `POSTGRES_*`:
  - comando: `python -c "import os; [os.environ.pop(k, None) for k in list(os.environ) if k.startswith('POSTGRES_')]; from fastapi.testclient import TestClient; from agro_gee_api.main import app; r=TestClient(app).get('/health'); print(f'status={r.status_code} body={r.json()}'); raise SystemExit(0 if r.status_code==200 else 1)"`
  - esperado: aplicacao subir e responder `200` em `/health` sem `POSTGRES_*`
  - observado: `status=200 body={'status': 'ok'}`
- Rotas removidas (`/users`, `/farms`, `/fields`, `/whatsapp/ping`):
  - esperado: retornar `404` e nao aparecer no `openapi.json`
  - observado: validacao confirmada em `test_removed_core_domains_return_404` e `test_openapi_does_not_expose_removed_core_domains`

## Breaking change

- Endpoints removidos: `/users`, `/farms`, `/fields`, `/whatsapp`.
- Runtime padrao sem PostgreSQL: o fluxo principal da API nao depende mais de `psycopg` nem de `POSTGRES_*`.
- Clientes que consumiam os endpoints removidos precisam migrar para os dominios ativos (`/auth`, `/analytics`, `/gee`, `/health`).

## Seguranca baseline

Checklist inicial em `docs/security-baseline.md` com praticas minimas para:

- gestao de segredos
- atualizacao de dependencias
- validacao por CI
