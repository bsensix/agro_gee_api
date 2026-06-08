# Design: Segmentacao Swagger por tipo de dado GEE

## Contexto

Hoje as rotas de extracao e catalogo do dominio GEE aparecem sob uma unica tag (`gee`) no Swagger, o que dificulta navegacao por tipo de dado. O objetivo e segmentar a visualizacao por categorias de dataset sem alterar paths nem comportamento da API.

## Objetivo

Organizar a documentacao OpenAPI/Swagger em grupos claros por tipo de dado:

- `gee-core`
- `sentinel2`
- `era5-land`
- `ifs-forecast`

## Fora de escopo

- Mudar URLs existentes (`/gee/...`)
- Renomear endpoints
- Alterar contratos de request/response
- Criar novos endpoints

## Arquitetura da mudanca

### 1) Tag por operacao no router GEE

Arquivo alvo: `agro_gee_api/routes/gee.py`.

Importante: o `APIRouter` GEE nao deve manter tag padrao generica (`tags=["gee"]`), porque isso pode misturar `gee` com as tags de operacao no OpenAPI. O design exige remover a tag generica no router e definir tag explicitamente em cada endpoint.

Cada endpoint recebe `tags=[...]` explicita no decorator.

Mapeamento:

- `gee-core`
  - `GET /gee/ping`
  - `POST /gee/auth/test`
  - `GET /gee/datasets`
- `sentinel2`
  - `POST /gee/sentinel2/extract/point`
  - `POST /gee/sentinel2/extract/polygon`
- `era5-land`
  - `POST /gee/era5-land/extract/point`
  - `POST /gee/era5-land/extract/polygon`
  - `GET /gee/datasets/era5-land/variables`
- `ifs-forecast`
  - `POST /gee/ifs-forecast/extract/point`
  - `POST /gee/ifs-forecast/extract/polygon`
  - `GET /gee/datasets/ifs-forecast/variables`

### 2) Ordenacao e descricoes das tags no OpenAPI

Arquivo alvo: `agro_gee_api/main.py`.

Definir `openapi_tags` no `FastAPI(...)` para controlar ordem e descricao dos grupos no Swagger UI.

Ordem recomendada:

1. `auth`
2. `analytics`
3. `gee-core`
4. `sentinel2`
5. `era5-land`
6. `ifs-forecast`

Regra de consistencia: os nomes em `openapi_tags` devem ser exatamente os mesmos usados em `tags=[...]` dos endpoints.

## Fluxo de dados e comportamento

Nao ha alteracao de fluxo funcional. Somente metadados OpenAPI serao alterados (`tags` por operacao e lista de tags globais). O runtime de extracao GEE permanece inalterado.

## Compatibilidade

- Backward compatible para clientes HTTP (paths/metodos iguais)
- Mudanca apenas visual/documentacao no Swagger/OpenAPI

## Erros e riscos

Risco principal: endpoint ficar sem tag esperada devido a esquecimento no decorator.

Risco adicional: divergencia entre `openapi_tags` (ordem/descricao) e tags realmente usadas nas operacoes.

Mitigacao:

- teste de contrato em `openapi.json` validando:
  - inexistencia da tag generica `gee` nas operacoes de `/gee/*`
  - presenca das quatro tags novas
  - associacao exata esperada de tag por `path+method`
  - toda operacao `/gee/*` tem exatamente 1 tag permitida: `gee-core|sentinel2|era5-land|ifs-forecast`
  - `openapi_tags` contem nomes/ordem esperados e descricoes nao vazias

## Testes

1. Atualizar/estender testes de contrato de rotas em `tests/test_routes_registration.py` (ou novo teste dedicado de OpenAPI tags).
2. Validar `/openapi.json` com asserts exatos por `path+method -> tag` para todos endpoints `/gee/*` atuais.
3. Validar que nenhuma operacao `/gee/*` carrega tag `gee`.
4. Validar metadados globais de tags (`openapi_tags`) com ordem e nomes esperados.
5. Manter smoke de status 200 apenas para endpoints de ping/contrato local, sem exigir chamada real ao GEE externo.

## Plano de implementacao resumido

1. Ajustar decorators em `agro_gee_api/routes/gee.py` com `tags=[...]` por operacao.
2. Configurar `openapi_tags` em `agro_gee_api/main.py`.
3. Implementar/ajustar testes de contrato OpenAPI.
4. Rodar testes focados e revisar Swagger em execucao local.
