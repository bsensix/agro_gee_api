# GEE Runtime Auth Design

## Objetivo

Conectar a API ao Google Earth Engine em runtime usando `ee.Initialize(...)`, permitindo validar autenticacao via endpoint dedicado e habilitar consultas reais nos endpoints GEE ja existentes.

## Escopo

Inclui:

- endpoint de diagnostico de autenticacao (`POST /gee/auth/test`), sem trafego de segredos em payload
- inicializacao real do Earth Engine via Service Account (com fallback OAuth opcional)
- adaptacao do cliente GEE para executar operacoes reais (`stats`, `extract`, `timeseries`, `image`)
- mapeamento de falhas para contrato de erro padronizado da API
- configuracao de ambiente Docker para fornecer credenciais ao container `api`

Nao inclui:

- persistencia de tokens/credenciais em banco
- onboarding de IAM/GCP dentro da API
- fluxo interativo OAuth browser-based

## Arquitetura

### 1. Runtime de autenticacao

Criar `api/services/gee_runtime.py` com um componente de runtime responsavel por:

- resolver modo de autenticacao (`service_account` padrao, `oauth` opcional)
- construir credenciais a partir de variaveis de ambiente
- chamar `ee.Initialize(credentials=..., project=...)`
- manter estado em memoria (`initialized`, `auth_mode`, `project_id`, `last_error`)
- prover `ensure_initialized()` para uso pelos servicos de dominio

Regras de resolucao de modo (deterministicas):

- `GEE_AUTH_MODE=service_account`: exige `GEE_SERVICE_ACCOUNT_EMAIL` e `GEE_PRIVATE_KEY`; nao tenta OAuth.
- `GEE_AUTH_MODE=oauth`: exige `GEE_OAUTH_CLIENT_ID`, `GEE_OAUTH_CLIENT_SECRET`, `GEE_OAUTH_REFRESH_TOKEN`; nao tenta Service Account.
- `GEE_AUTH_MODE=auto` ou ausente: tenta Service Account primeiro; se credenciais ausentes, tenta OAuth.
- `GEE_PROJECT_ID` e obrigatorio em qualquer modo para inicializacao explicita do projeto.

Politica de estado/re-inicializacao:

- runtime usa lock para impedir corrida em inicializacao concorrente.
- `ensure_initialized()` reutiliza estado valido.
- em erro de autenticacao, estado fica invalido e proxima chamada reavalia credenciais.
- em erro transiente (`GEE_UNAVAILABLE`/timeout), runtime nao invalida credenciais, mas permite nova tentativa imediata.
- `POST /gee/auth/test` sempre executa verificacao ativa (forca recheck) e atualiza `last_error`.

Esse modulo centraliza comportamento de autenticacao e evita duplicacao de `ee.Initialize(...)` em cada endpoint.

### 2. Endpoint de autenticacao/diagnostico

Adicionar em `api/routes/gee.py`:

- `POST /gee/auth/test`

Fluxo:

1. runtime tenta inicializar GEE
2. runtime executa consulta minima (`ee.Number(1).getInfo()`)
3. retorna status de diagnostico

Controle de acesso:

- endpoint protegido por `X-User-Id` + autorizacao de escopo interno/admin (mesma base de authz da API).
- desabilitavel por ambiente com `GEE_AUTH_TEST_ENABLED` (padrao: habilitado em dev, desabilitado em prod).
- recomendacao operacional: aplicar rate limit no gateway/reverse proxy.

Resposta de sucesso:

```json
{
  "status": "ok",
  "initialized": true,
  "auth_mode": "service_account",
  "project_id": "<gcp-project>",
  "message": "Earth Engine initialized successfully"
}
```

Resposta de falha segue contrato de erro existente (`error_code`, `message`, `correlation_id`, `retryable`).

### 3. Cliente GEE real

Evoluir `api/services/gee_client.py` para:

- conter implementação concreta com chamadas `ee.ImageCollection(...)`
- usar `gee_runtime.ensure_initialized()` antes de consultas
- mapear excecoes para:
  - `GEE_AUTH_FAILED` (credenciais/authorization)
  - `GEE_TIMEOUT` (timeout)
  - `GEE_UNAVAILABLE` (rede/servico externo)
  - `GEE_INTERNAL_ERROR` (falha inesperada do SDK/cliente, sanitizada)

Contrato canonico de erro:

- `gee_client` e a unica camada que traduz excecoes do SDK `ee` para erros de dominio.
- services (`gee_sentinel2.py`, `gee_sentinel2_extract.py`) nao remapeiam mensagens sensiveis; apenas propagam erro de dominio.
- todas as operacoes (`ndvi_mean`, `extract_point`, `extract_polygon`, `timeseries`, `image`) seguem o mesmo mapeamento.
- excecoes desconhecidas do SDK devem cair no fallback `GEE_INTERNAL_ERROR`.

Operacoes alvo:

- `ndvi_mean(...)`
- `extract_point(...)`
- `extract_polygon(...)`
- `timeseries(...)`
- `image(...)`

### 4. Reuso nos endpoints existentes

Substituir clientes `_NotConfigured*` em `api/routes/gee.py` por factories que retornam servicos baseados no cliente GEE real.

Com isso:

- `/gee/sentinel2/stats`
- `/gee/sentinel2/extract/point`
- `/gee/sentinel2/extract/polygon`
- `/gee/sentinel2/timeseries`
- `/gee/sentinel2/image`

passam a usar dados reais do Earth Engine.

## Configuracao

### Variaveis de ambiente

No `docker-compose.yml` (servico `api`) incluir:

- `GEE_AUTH_MODE` (`auto` padrao, `service_account`, `oauth`)
- `GEE_PROJECT_ID`
- `GEE_SERVICE_ACCOUNT_EMAIL`
- `GEE_PRIVATE_KEY`
- `GEE_OAUTH_CLIENT_ID` (opcional)
- `GEE_OAUTH_CLIENT_SECRET` (opcional)
- `GEE_OAUTH_REFRESH_TOKEN` (opcional)

### Dependencias

`earthengine-api` ja esta no projeto; manter imagem Docker com rebuild para carregar codigo atualizado.

## Contratos de erro

- manter schema padrao atual de erros no router GEE
- mapear falhas de init/login para `GEE_AUTH_FAILED` (500, `retryable=false`)
- mapear indisponibilidade externa para `GEE_UNAVAILABLE` (503, `retryable=true`)
- mapear timeout para `GEE_TIMEOUT` (504, `retryable=true`)
- mapear falhas inesperadas para `GEE_INTERNAL_ERROR` (500, `retryable=false`)

Higiene de seguranca:

- nunca retornar ou logar `private_key`, `refresh_token`, `client_secret`.
- mensagens externas devem ser sanitizadas para texto generico (sem dump de stack/SDK).
- normalizar `GEE_PRIVATE_KEY` com suporte a `\\n` sem expor valor bruto em resposta/log.

## Testes

### Unitarios

Criar testes para runtime e cliente real com mocks de `ee`:

- init com service account valido
- init com OAuth valido
- credenciais ausentes
- erro no `ee.Initialize`
- erro na consulta de health (`getInfo`)
- concorrencia de `ensure_initialized()` (idempotencia com lock)
- teste de sanitizacao de erro (sem vazamento de segredos)
- excecao desconhecida do SDK mapeada para `GEE_INTERNAL_ERROR`

### Rota

Expandir `tests/test_gee_route.py` para `POST /gee/auth/test`:

- sucesso 200
- erro de autenticacao mapeado
- indisponibilidade mapeada
- endpoint bloqueado quando `GEE_AUTH_TEST_ENABLED=false`
- endpoint bloqueado para usuario sem escopo administrativo
- erro desconhecido mapeado para `GEE_INTERNAL_ERROR`

### Integracao

Manter cobertura existente e adicionar:

- smoke da autenticacao com monkeypatch do runtime para evitar dependencia de credenciais reais nos testes de CI.
- cobertura de erro mapeado nos endpoints de dados GEE apos runtime real (auth/unavailable/timeout).

## Operacao

Fluxo recomendado para teste manual:

1. configurar `.env` com credenciais GEE
2. `docker compose up -d --build api`
3. chamar `POST /gee/auth/test` no `/docs`
4. se retornar `ok`, testar endpoints de dados GEE

## Riscos e mitigacoes

- segredo mal formatado (chave privada multiline): documentar formato esperado no `.env.example`
- inicializacao concorrente: proteger `ensure_initialized()` com lock simples no runtime
- degradacao por falhas transientes: cachear estado e permitir retentativa via endpoint `/gee/auth/test`
