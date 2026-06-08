# Design: remover cloud_pct das respostas meteo

## Contexto

Os endpoints meteo (`era5-land` e `ifs-forecast`) retornam `series[]` com o campo `cloud_pct`, que nao e necessario para o fluxo atual. O objetivo e simplificar o contrato de resposta removendo esse campo em todos os endpoints meteo.

## Objetivo

Remover `cloud_pct` de `series[]` nas respostas meteo de:

- `POST /gee/era5-land/extract/point`
- `POST /gee/era5-land/extract/polygon`
- `POST /gee/ifs-forecast/extract/point`
- `POST /gee/ifs-forecast/extract/polygon`

## Fora de escopo

- Alterar logica de extracao/consulta no GEE
- Alterar regras de validacao de input
- Alterar endpoints Sentinel-2
- Adicionar flags de compatibilidade no payload

## Arquitetura da mudanca

### 1) Contrato de resposta meteo

Arquivo alvo: `agro_gee_api/routes/gee.py`.

- Atualizar `MeteoExtractSeriesItemResponse` para conter apenas:
  - `date: str`
  - `value: float`
- Remover declaracao de `cloud_pct` do model Pydantic.

### 2) Serializacao da resposta

No mapeamento de `extract_result["series"]` para `MeteoExtractSeriesItemResponse`, garantir que o schema final nao exponha `cloud_pct`.

Como o model deixara de ter este campo, itens com `cloud_pct` vindos de camadas internas serao ignorados na resposta final.

### 3) Contrato de teste

Arquivos alvo: `tests/test_gee_route.py` (principal) e ajustes adicionais em testes meteo se necessario.

Validacoes minimas:

- Respostas de `era5-land` e `ifs-forecast` continuam `200` nos cenarios de sucesso.
- Cada item de `series[]` contem `date` e `value`.
- Cada item de `series[]` **nao** contem `cloud_pct`.
- `openapi.json` nao deve listar `cloud_pct` no schema de series meteo.

## Fluxo de dados

Sem mudanca de fluxo funcional:

- input -> validacao -> service de extracao -> mapeamento de resposta.

Mudanca somente no contrato de output HTTP para meteo.

## Compatibilidade

Breaking change controlada de payload para clientes que dependiam de `cloud_pct`.

Mitigacao:

- Registrar no changelog/PR que `cloud_pct` foi removido de respostas meteo.
- Fornecer orientacao para clientes consumirem apenas `date` e `value` em `series[]`.

## Riscos e mitigacoes

- Risco: algum endpoint meteo manter `cloud_pct` por regressao parcial.
  - Mitigacao: teste de contrato cobrindo os 4 endpoints meteo.
- Risco: schema OpenAPI desatualizado em cache local.
  - Mitigacao: rebuild/restart do container e validacao de `openapi.json`.

## Testes

1. Atualizar testes meteo de rota para validar ausencia de `cloud_pct`.
2. Rodar testes focados:
   - `pytest tests/test_gee_route.py -v`
   - `pytest tests/test_routes_registration.py -v` (sanidade de contratos de rotas)
3. Validar schema:
   - `GET /openapi.json` sem `cloud_pct` no modelo de series meteo.

## Plano resumido

1. Ajustar model meteo em `agro_gee_api/routes/gee.py`.
2. Atualizar testes de contrato em `tests/test_gee_route.py`.
3. Rodar testes focados e validar OpenAPI.
