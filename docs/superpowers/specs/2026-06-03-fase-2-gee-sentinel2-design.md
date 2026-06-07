# Fase 2 Design - GEE Sentinel-2 (MVP-Data)

## Contexto e objetivo

Esta especificacao cobre a primeira entrega da Fase 2 com foco em:

- autenticacao no Google Earth Engine via Service Account;
- suporte inicial ao dataset Sentinel-2;
- endpoint sincrono para extracao de metrica por poligono de talhao (`field_id`).

Escopo deliberadamente enxuto para acelerar entrega de valor e reduzir risco operacional.

## Decisoes de escopo

- **Autenticacao:** apenas Service Account nesta fase.
- **Dataset:** apenas Sentinel-2 nesta fase.
- **Persistencia de resultados:** nao (consulta on-demand).
- **Execucao:** sincrona HTTP (sem fila/job).
- **Metrica inicial:** `ndvi_mean`.

## Alinhamento com ROADMAP (Fase 2A/Fase 2B)

Este documento define a **Fase 2A** (primeira entrega de Fase 2), focada em autenticacao Service Account + extracao de metrica Sentinel-2 por poligono.

Itens de **Fase 2B** (ainda dentro da Fase 2 do roadmap, mas fora deste incremento):

- `GET /gee/datasets` (catalogo de datasets)
- `POST /gee/sentinel2/extract/point`
- `POST /gee/sentinel2/extract/polygon`
- `POST /gee/sentinel2/timeseries`
- `POST /gee/sentinel2/image`
- migracao + carga inicial do catalogo `gee_datasets`

Com isso, a marcacao de conclusao no roadmap deve considerar:

- Fase 2A concluida quando este escopo estiver entregue e testado;
- Fase 2 completa apenas apos entrega dos itens de Fase 2B.

## Arquitetura proposta

### Componentes

- `api/routes/gee.py`
  - recebe request HTTP, valida payload e devolve resposta padronizada.
- `api/services/gee_sentinel2.py` (novo)
  - encapsula autenticacao GEE, consulta da colecao e calculo NDVI.
- camada de acesso ao PostGIS (reuso de padrao atual)
  - busca geometria do `field_id` e valida acesso do usuario.

### Endpoint inicial

- `POST /gee/sentinel2/stats`

Payload:

- `field_id: int`
- `date_start: str (YYYY-MM-DD)`
- `date_end: str (YYYY-MM-DD)`
- `metric: Literal["ndvi_mean"]`

Resposta (200):

- `field_id`
- `date_start`
- `date_end`
- `dataset` (ex.: `COPERNICUS/S2_SR_HARMONIZED`)
- `metric` (ex.: `ndvi_mean`)
- `value` (float)
- `images_used` (int)

## Fluxo de dados

1. API recebe request e valida formato basico.
2. API resolve contexto de autorizacao via `X-User-Id` (reuso da Fase 1).
3. API consulta PostGIS para obter geometria do `field_id` e confirmar escopo de acesso.
4. Servico GEE autentica com Service Account.
5. Servico aplica filtros da colecao Sentinel-2 por periodo e regiao do talhao.
6. Servico calcula NDVI por imagem e agrega media temporal no periodo.
7. API retorna metadados + valor calculado.

## Regras de validacao

- `date_start <= date_end`.
- janela maxima de consulta: 365 dias.
- `metric` fora da lista permitida deve falhar.
- filtro de nuvem inicial fixo: `CLOUDY_PIXEL_PERCENTAGE < 20`.
- limite de area do talhao para extracao sincrona: `area_max_ha` (padrao: `10000` ha).
  - acima do limite deve retornar erro sem chamar processamento pesado.

## Contrato de erros

Schema padrao para toda resposta de erro:

- `error_code`: codigo estavel para cliente/observabilidade.
- `message`: mensagem legivel.
- `details`: objeto opcional com contexto tecnico seguro.
- `correlation_id`: id de rastreio do request.
- `retryable`: booleano para orientar cliente.

- `400`:
  - payload invalido;
  - intervalo de datas invalido;
  - `metric` nao suportada.
- `403`:
  - `field_id` existe, mas usuario nao autorizado.
- `404`:
  - `field_id` inexistente.
- `413`:
  - `field_id` acima de `area_max_ha` para modo sincrono.
- `422`:
  - sem imagens validas para periodo/area.
- `503`:
  - `GEE_UNAVAILABLE` (servico externo indisponivel).
- `504`:
  - `GEE_TIMEOUT` (timeout em consulta externa).
- `500`:
  - `GEE_AUTH_FAILED` ou erro interno nao classificado.

Mapeamentos iniciais sugeridos:

- `INVALID_REQUEST` -> `400`
- `FORBIDDEN_SCOPE` -> `403`
- `FIELD_NOT_FOUND` -> `404`
- `AREA_LIMIT_EXCEEDED` -> `413`
- `NO_IMAGERY` -> `422`
- `GEE_UNAVAILABLE` -> `503`
- `GEE_TIMEOUT` -> `504`
- `GEE_AUTH_FAILED` -> `500`

## Testes

### Unitarios (servico)

- autentica com credenciais esperadas de Service Account.
- aplica filtros de periodo/area/nuvem corretamente.
- calcula NDVI e media temporal.
- mapeia erro de "sem imagens" para excecao de dominio.
- valida limite de area antes de processar consulta GEE.

Separacao de dependencias para CI:

- definir interface `GEEClient` no servico.
- injetar implementacao real apenas em runtime de aplicacao.
- usar fake/mock de `GEEClient` em testes.
- incluir guarda de CI para impedir uso de credenciais reais/chamadas de rede ao GEE em testes.

### Integracao (rota)

- `403` para acesso fora de escopo do usuario.
- `404` para `field_id` inexistente.
- `400` para datas invalidas e metrica invalida.
- `413` para area acima do limite.
- `422` para consulta sem imagem valida.
- `503/504` para indisponibilidade/timeout do GEE.
- `200` no caminho feliz com schema esperado.

Observacao: CI nao deve depender do GEE real; usar dublês/mocks no nivel de servico.

## Evolucao planejada (fora deste escopo)

- suporte a multiplos datasets;
- operacoes `extract/point`, `timeseries` e `image` dedicadas;
- execucao assincrona por jobs para cargas mais pesadas;
- cache/persistencia de resultados.
