# agro_gee_api

![Logo da API](logo_api.png)

API backend do projeto Agro Insight, focada em operacoes de dados agricolas e integracao com Google Earth Engine (GEE).

## Contexto da API

Esta API organiza os fluxos principais da plataforma em um unico servico FastAPI:

- autenticacao e autorizacao de usuarios
- cadastro e consulta de usuarios, fazendas e talhoes
- endpoints de analytics
- integracao com GEE para extracao e estatisticas Sentinel-2
- endpoint de saude para monitoramento (`/health`)

Rotas principais por dominio:

- `auth`: `/auth`
- `users`: `/users`
- `farms`: `/farms`
- `fields`: `/fields`
- `analytics`: `/analytics`
- `whatsapp`: `/whatsapp`
- `gee`: `/gee`

## Stack e arquitetura

- Framework: FastAPI
- Banco: PostgreSQL + PostGIS
- Containerizacao: Docker + Docker Compose
- Testes: Pytest

Arquivos de referencia:

- App entrypoint: `agro_gee_api/main.py`
- Compose local: `docker-compose.yml`
- Dockerfile da API: `infrastructure/docker/api.Dockerfile`

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

## Rodando testes localmente

```bash
pip install -e .[dev]
pytest -v
```

## Seguranca baseline

Checklist inicial em `docs/security-baseline.md` com praticas minimas para:

- gestao de segredos
- atualizacao de dependencias
- validacao por CI
