# Agro GEE API

<p align="center">
  <img src="logo_api.png" width="300"/>
</p>

API backend do projeto Agro Insight para extracao de dados geoespaciais (Google Earth Engine), contratos agrometeorologicos em `/agro` e endpoints de suporte de plataforma.

## Estado atual do projeto

Arquitetura atual:

- API unica em FastAPI (`agro_gee_api/main.py`)
- runtime stateless (sem PostgreSQL no fluxo principal)
- integracao com Google Earth Engine para datasets e extracoes
- dominio `/agro` com endpoints v1 para fenologia, agua e risco termico
- healthcheck (`/health`) e servico de SPA (`/app` e `/assets/*`)

Dominios ativos:

- `/auth` (ping)
- `/analytics` (ping)
- `/gee` (catalogo e extracoes)
- `/agro` (contratos agrometeorologicos)
- `/health`
- `/app` e `/assets/*`

## Stack

- Python 3.12+
- FastAPI + Uvicorn
- Earth Engine API
- Pytest
- Docker + Docker Compose

Arquivos de referencia:

- `agro_gee_api/main.py`
- `agro_gee_api/routes/gee.py`
- `agro_gee_api/routes/agro.py`
- `docker-compose.yml`
- `infrastructure/docker/api.Dockerfile`
- `pyproject.toml`

## Endpoints principais

### Core

- `GET /health`
- `GET /auth/ping`
- `GET /analytics/ping`

### GEE

- `GET /gee/ping`
- `GET /gee/datasets`
- `POST /gee/sentinel2/extract/point`
- `POST /gee/sentinel2/extract/polygon`
- `POST /gee/era5-land/extract/point`
- `POST /gee/era5-land/extract/polygon`
- `POST /gee/ifs-forecast/extract/point`
- `POST /gee/ifs-forecast/extract/polygon`
- `POST /gee/satellite-embedding-annual/extract/point`
- `POST /gee/satellite-embedding-annual/extract/polygon`
- `GET /gee/datasets/era5-land/variables`
- `GET /gee/datasets/ifs-forecast/variables`
- `GET /gee/datasets/satellite-embedding-annual/variables`
- `POST /gee/auth/test` (habilitado por ambiente/flag e escopo)

### Agro (v1)

- `POST /agro/phenology/estimate/point`
- `POST /agro/phenology/estimate/polygon`
- `POST /agro/et0-etc/point`
- `POST /agro/et0-etc/polygon`
- `POST /agro/water-balance/simple/point`
- `POST /agro/water-balance/simple/polygon`
- `POST /agro/water-status/point`
- `POST /agro/water-status/polygon`
- `POST /agro/thermal-risk/point`
- `POST /agro/thermal-risk/polygon`

Assuncoes atuais da v1:

- perfis agronomicos `v1_default` para `soybean`, `corn`, `cotton`
- ET0 por Hargreaves-Samani
- balanco hidrico por bucket model simples
- `date_harvest` validado, mas com papel informativo no calculo

## Como rodar localmente

No diretorio raiz:

```bash
pip install -e .[dev]
uvicorn agro_gee_api.main:app --reload
```

Documentacao interativa:

- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

## Como rodar com Docker

No diretorio raiz:

```bash
docker compose up -d --build
docker compose ps
```

Parar stack:

```bash
docker compose down
```

## Variaveis de ambiente (principais)

- `APP_NAME`
- `ENVIRONMENT` ou `APP_ENV`
- `API_PORT` (padrao `8000`)
- `GEE_AUTH_MODE`
- `GEE_PROJECT_ID`
- `GEE_SERVICE_ACCOUNT_EMAIL`
- `GEE_PRIVATE_KEY`
- `GEE_OAUTH_CLIENT_ID`
- `GEE_OAUTH_CLIENT_SECRET`
- `GEE_OAUTH_REFRESH_TOKEN`
- `GEE_AUTH_TEST_ENABLED`

Observacao: `POSTGRES_*` nao e obrigatorio no fluxo principal atual.

## Como implementar e evoluir esta API

Este projeto esta organizado para evolucao por dominio (`routes` + `services`). Um fluxo pratico para implementar novas features:

1. Defina o contrato HTTP primeiro
   - payload de entrada (Pydantic), resposta e codigos de erro.
   - mantenha nomenclatura consistente com os dominios atuais.

2. Implemente a regra de negocio em `services`
   - extraia calculos/integracoes para `agro_gee_api/services/*`.
   - deixe a rota fina: validacao, chamada de servico, mapeamento de erro.

3. Exponha a rota em `routes`
   - adicione endpoint no arquivo do dominio (`routes/agro.py`, `routes/gee.py` etc.).
   - reaproveite o padrao de `DomainError` + `JSONResponse` ja usado no projeto.

4. Registre no app principal
   - inclua o router em `agro_gee_api/main.py` (se for dominio novo).
   - ajuste tags OpenAPI para manter a documentacao organizada.

5. Cubra com testes
   - adicione testes de contrato e cenarios de erro em `tests/`.
   - rode `pytest -v` antes de publicar.

6. Entregue por ambiente
   - valide local com `uvicorn`.
   - valide container com `docker compose up -d --build`.
   - use `/health` e `/docs` como checks rapidos de deploy.

### Exemplo de extensao (novo endpoint `/agro`)

- criar request/response em `agro_gee_api/routes/agro.py`
- criar calculo em `agro_gee_api/services/agro_engine.py` (ou novo servico dedicado)
- mapear erros para `error_code` estavel
- adicionar testes para `200`, `400` e erros de dominio (`422/503/504` quando aplicavel)
- validar contrato no `openapi.json`

## Testes

```bash
pip install -e .[dev]
pytest -v
```

## Notas de compatibilidade

- endpoints legados removidos: `/users`, `/farms`, `/fields`, `/whatsapp`
- clientes devem usar os dominios atuais (`/auth`, `/analytics`, `/gee`, `/agro`, `/health`)

## Seguranca baseline

Checklist inicial em `docs/security-baseline.md` para:

- gestao de segredos
- atualizacao de dependencias
- validacao por CI
