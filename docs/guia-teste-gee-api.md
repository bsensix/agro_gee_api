# Guia rapido de teste da API GEE

Este guia mostra como validar a autenticacao no Google Earth Engine (GEE) e testar os endpoints da API quando voce puder voltar ao ambiente.

## 1) Subir servicos

No diretorio raiz do projeto, rode:

```bash
docker compose up -d --build db api
```

Verifique se subiram:

```bash
docker compose ps
```

Esperado:

- `agro-insight-db-1` em `0.0.0.0:15432->5432`
- `agro-insight-api-1` em `0.0.0.0:8000->8000`

## 2) Configurar credenciais GEE no `.env`

Crie/edite um arquivo `.env` na raiz do projeto com:

```env
GEE_AUTH_MODE=service_account
GEE_PROJECT_ID=seu-projeto-gcp
GEE_SERVICE_ACCOUNT_EMAIL=sua-sa@seu-projeto-gcp.iam.gserviceaccount.com
GEE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
GEE_AUTH_TEST_ENABLED=true
```

Observacoes:

- O runtime ja converte `\\n` para quebra de linha real na chave privada.
- Se quiser usar OAuth:
  - `GEE_AUTH_MODE=oauth`
  - `GEE_OAUTH_CLIENT_ID`, `GEE_OAUTH_CLIENT_SECRET`, `GEE_OAUTH_REFRESH_TOKEN`

## 3) Rebuild da API apos mudar `.env`

Sempre que alterar credenciais/env, rode:

```bash
docker compose up -d --build api
```

## 4) Abrir Swagger

- Docs: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`

## 5) Criar usuario para testar endpoint protegido

O endpoint `POST /gee/auth/test` exige `X-User-Id` com privilegio admin/internal.

### Criar usuario

No Swagger, use `POST /users` com payload exemplo:

```json
{
  "name": "Admin GEE",
  "email": "admin.gee@example.com",
  "role": "internal"
}
```

Guarde o `user_id` retornado.

## 6) Testar autenticacao GEE

No Swagger:

- Endpoint: `POST /gee/auth/test`
- Header: `X-User-Id: <user_id_internal_ou_admin>`

Resultados esperados:

- `200` com `{"status":"ok"}` quando autenticado no GEE
- `500` com `GEE_AUTH_FAILED` se credencial invalida
- `503` com `GEE_UNAVAILABLE` em falha externa/rede
- `404` se `GEE_AUTH_TEST_ENABLED=false`
- `403` se `X-User-Id` sem privilegio

## 7) Testar endpoints GEE de dados

No Swagger, valide estes endpoints:

- `GET /gee/datasets`
- `POST /gee/sentinel2/extract/point`
- `POST /gee/sentinel2/extract/polygon`
- `POST /gee/sentinel2/timeseries`
- `POST /gee/sentinel2/image`
- `POST /gee/sentinel2/stats`

### Payload exemplo: extract point

```json
{
  "coordinates": [-47.0, -15.0],
  "date_start": "2026-06-01",
  "date_end": "2026-06-10",
  "metric": "ndvi_mean"
}
```

### Payload exemplo: extract polygon / timeseries / image

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

### Payload exemplo: stats

```json
{
  "field_id": 10,
  "date_start": "2026-06-01",
  "date_end": "2026-06-10",
  "metric": "ndvi_mean"
}
```

Observacao: para `stats`, o `field_id` precisa existir e o `X-User-Id` precisa ter escopo para esse campo.

## 8) Troubleshooting rapido

### So aparece `/gee/ping` no Swagger

```bash
docker compose up -d --build api
```

Depois faca hard refresh no navegador (`Ctrl+F5`).

### Erro de conexao no banco em cliente SQL

Use:

- Host: `localhost`
- Porta: `15432`
- Database: `agro_insight`
- User: `postgres`
- Password: `postgres`

### Porta 15432 ocupada

Pare outro container Postgres antes de subir:

```bash
docker ps
docker stop <container>
```
