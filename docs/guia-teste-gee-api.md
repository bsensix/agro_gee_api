# Guia rapido de teste da API GEE

Este guia mostra como validar autenticacao no Google Earth Engine (GEE) e testar os endpoints ativos da API.

## 1) Subir a API

No diretorio raiz do projeto:

```bash
docker compose up -d --build
docker compose ps
```

Esperado: servico da API em execucao na porta `8000`.

## 2) Configurar credenciais GEE no `.env`

Crie/edite `.env` na raiz com:

```env
GEE_AUTH_MODE=service_account
GEE_PROJECT_ID=seu-projeto-gcp
GEE_SERVICE_ACCOUNT_EMAIL=sua-sa@seu-projeto-gcp.iam.gserviceaccount.com
GEE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
GEE_AUTH_TEST_ENABLED=true
```

Opcao OAuth (desenvolvimento):

- `GEE_AUTH_MODE=oauth`
- `GEE_OAUTH_CLIENT_ID`
- `GEE_OAUTH_CLIENT_SECRET`
- `GEE_OAUTH_REFRESH_TOKEN`

## 3) Rebuild apos alterar variaveis

```bash
docker compose up -d --build
```

## 4) Abrir documentacao

- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

## 5) Testar autenticacao GEE

Endpoint: `POST /gee/auth/test`

Headers:

- `X-User-Id: 1`
- `X-Requester-Role: internal` (ou `admin`)

Resultados esperados:

- `200` com `{"status":"ok"}` quando autenticado
- `500` com `GEE_AUTH_FAILED` se credencial invalida
- `503` com `GEE_UNAVAILABLE` em indisponibilidade externa
- `404` se `GEE_AUTH_TEST_ENABLED=false`
- `403` sem permissao de role

## 6) Testar endpoints de dados

Valide no Swagger:

- `GET /gee/datasets`
- `POST /gee/sentinel2/extract/point`
- `POST /gee/sentinel2/extract/polygon`
- `POST /gee/era5-land/extract/point`
- `POST /gee/era5-land/extract/polygon`

### Payload exemplo: Sentinel-2 point

```json
{
  "coordinates": [-47.0, -15.0],
  "date_start": "2026-06-01",
  "date_end": "2026-06-10",
  "metric": "ndvi_mean"
}
```

### Payload exemplo: Sentinel-2 polygon

```json
{
  "geometry": {
    "type": "Polygon",
    "coordinates": [
      [[-47.0, -15.0], [-46.9, -15.0], [-46.9, -15.1], [-47.0, -15.0]]
    ]
  },
  "date_start": "2026-06-01",
  "date_end": "2026-06-10",
  "metric": "ndvi_mean"
}
```

## 7) Troubleshooting rapido

### So aparece `/gee/ping` no Swagger

```bash
docker compose up -d --build
```

Depois faca refresh forcado no navegador (`Ctrl+F5`).
