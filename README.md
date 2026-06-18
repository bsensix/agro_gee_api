# Agro GEE API

<p align="center">
  <img src="logo_api.png" width="300"/>
</p>

API backend focada exclusivamente em servicos HTTP para extracao de dados geoespaciais (Google Earth Engine), contratos do dominio `/agro` e endpoints de suporte de plataforma.

## Estado atual

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
- `POST /gee/sentinel1/extract/point`
- `POST /gee/sentinel1/extract/polygon`
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

Observacao: o fluxo principal da API e stateless e nao depende de banco relacional.

## Tutorial: cadastrar projeto no GEE para uso na API

Para os endpoints de extracao em `/gee` funcionarem, seu projeto no Google Cloud precisa estar habilitado no Earth Engine.

1. Crie (ou escolha) um projeto no Google Cloud
   - acesse `https://console.cloud.google.com/`
   - anote o ID do projeto (sera usado em `GEE_PROJECT_ID`)

2. Ative as APIs necessarias
   - no projeto, habilite:
     - `Earth Engine API`
     - `Google Cloud Storage` (recomendado para fluxos de export)

3. Registre/habilite o projeto no Earth Engine
   - acesse `https://code.earthengine.google.com/register`
   - selecione o mesmo projeto do passo 1
   - conclua o cadastro/aceite de termos da conta que vai operar a API

4. Escolha o modo de autenticacao da API

   Opcao A (recomendada em servidor): Service Account
   - crie uma Service Account no Google Cloud
   - gere uma chave JSON
   - configure:
     - `GEE_AUTH_MODE=service_account`
     - `GEE_PROJECT_ID=<seu-projeto>`
     - `GEE_SERVICE_ACCOUNT_EMAIL=<email-da-service-account>`
     - `GEE_PRIVATE_KEY=<private_key do JSON, com \n escapado>`

   Opcao B (desenvolvimento local): OAuth
   - crie credenciais OAuth Client no Google Cloud
   - obtenha refresh token da conta com acesso ao Earth Engine
   - configure:
     - `GEE_AUTH_MODE=oauth`
     - `GEE_PROJECT_ID=<seu-projeto>`
     - `GEE_OAUTH_CLIENT_ID=<client_id>`
     - `GEE_OAUTH_CLIENT_SECRET=<client_secret>`
     - `GEE_OAUTH_REFRESH_TOKEN=<refresh_token>`

5. Suba a API com as variaveis
   - via Docker Compose ou execucao local com `uvicorn`

6. Valide se o GEE esta operacional
   - chame um endpoint de extracao `/gee` com payload valido
   - se houver problema de credencial/projeto, a API retorna erro de autenticacao (ex.: `GEE_AUTH_FAILED`)

Exemplo minimo de variaveis para Service Account (`.env`):

```env
GEE_AUTH_MODE=service_account
GEE_PROJECT_ID=seu-projeto-gcp
GEE_SERVICE_ACCOUNT_EMAIL=sa-gee@seu-projeto-gcp.iam.gserviceaccount.com
GEE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```
