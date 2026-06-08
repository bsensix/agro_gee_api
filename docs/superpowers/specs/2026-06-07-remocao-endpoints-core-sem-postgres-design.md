# Design: remocao de endpoints core e execucao sem PostgreSQL

## Contexto

O projeto atual expoe os dominios `users`, `farms`, `fields` e `whatsapp` e possui dependencia direta de PostgreSQL/`psycopg` no runtime e na suite de testes. O objetivo desta mudanca e simplificar a API para funcionar sem banco de dados, removendo esses quatro dominios e eliminando a necessidade de PostgreSQL para subir e executar localmente.

## Objetivo

- Remover os endpoints `users`, `farms`, `fields` e `whatsapp` do runtime da API.
- Eliminar a necessidade de PostgreSQL para executar a aplicacao.
- Eliminar dependencias de PostgreSQL do caminho de startup/request da API e da execucao padrao de testes.
- Manter os endpoints/fluxos stateless existentes (por exemplo, `health` e demais rotas sem persistencia).
- Atualizar documentacao e testes para refletir o novo comportamento.

## Fora de escopo

- Migrar persistencia para outro banco (ex.: SQLite).
- Criar camada de armazenamento em memoria para substituir os dominios removidos.
- Preservar compatibilidade de contrato HTTP das rotas removidas (retornos `410/501`).

## Abordagem escolhida

Abordagem de **remocao direta + modo stateless**:

1. Remover os routers de `users`, `farms`, `fields` e `whatsapp` da montagem da aplicacao.
2. Remover ou desacoplar imports/handlers de erro ligados a `psycopg` que impactam inicializacao e caminho de requisicao.
3. Garantir que a API inicie sem `POSTGRES_*` e sem servico de banco em compose.
4. Ajustar README e testes para o novo escopo funcional.
5. Tratar a mudanca como breaking change de API para clientes que usam as rotas removidas.

## Arquitetura alvo

### Runtime da API

- A aplicacao FastAPI sobe sem dependencias de banco.
- Rotas dependentes de dados persistidos deixam de existir no roteamento.
- Rotas stateless continuam operando sem alteracao de contrato, quando aplicavel.

### Dependencias

- Remover `psycopg` e qualquer dependencia de PostgreSQL do `pyproject.toml` no grupo principal de runtime.
- Se existir lockfile, atualizar para refletir a remocao dessas dependencias.
- Nenhum modulo carregado por startup/request pode importar `psycopg` ou `agro_gee_api.db`.

### Ambiente local

- `docker-compose.yml` deixa de exigir container PostgreSQL para fluxo basico da API.
- Variaveis `POSTGRES_*` deixam de ser prerequisito para execucao principal.

## Componentes e mudancas

### `agro_gee_api/main.py`

- Remover `include_router` de `users`, `farms`, `fields` e `whatsapp`.
- Remover tratamento global de excecao `psycopg.OperationalError` se ele nao for mais relevante no runtime.

### `agro_gee_api/routes/*` e modulos de suporte

- Remover os modulos de rota `users`, `farms`, `fields` e `whatsapp` do runtime (nao podem ser importados por `main.py` nem por rotas ativas).
- Para utilitarios exclusivos de CRUD/DB (ex.: `_crud_common.py`), remover quando nao houver uso por rotas ativas. Se mantidos temporariamente, devem ficar totalmente fora da arvore de imports do runtime.

### Dependencias e infra

- Atualizar `pyproject.toml` e lockfile para remover dependencias de PostgreSQL do runtime.
- Atualizar `docker-compose.yml` para fluxo principal sem PostgreSQL; opcionalmente manter servico DB apenas em perfil/comando explicitamente nao padrao.
- Definir comando padrao de desenvolvimento/teste que nao sobe banco.

### Documentacao

- Atualizar `README.md` (stack, rotas principais, instrucoes de execucao).
- Remover referencias obrigatorias a PostgreSQL em guias basicos.

### Testes

- Remover/ajustar testes de CRUD de `users`, `farms`, `fields` e fluxos de `whatsapp`.
- Remover/ajustar testes que validam resiliencia/conectividade de PostgreSQL.
- Manter e validar testes de rotas/stateless que permanecerem no produto.
- Ajustar `tests/conftest.py` e fixtures para nao exigir conexao DB no fluxo padrao.
- Garantir que CI/comando de teste padrao execute sem servico PostgreSQL.

### Contrato e comunicacao

- Registrar explicitamente que a remocao de `users`, `farms`, `fields` e `whatsapp` e uma breaking change.
- Atualizar OpenAPI e README para remover mencoes dessas rotas.
- Se houver consumidores externos, incluir nota de deprecacao/remocao no changelog da entrega.

## Fluxo de requisicao e comportamento esperado

- Requisicoes para endpoints removidos devem responder `404 Not Found` (rota inexistente).
- Nao deve haver tentativa de conexao com banco durante startup nem durante requests das rotas remanescentes.
- O `openapi.json` e a UI em `/docs` nao devem listar rotas `users`, `farms`, `fields` e `whatsapp`.

## Tratamento de erros

- Remover caminhos de erro relacionados a indisponibilidade de PostgreSQL no runtime principal.
- Manter tratamento de erros HTTP genericos e de validacao de entrada conforme comportamento atual.

## Riscos e mitigacoes

- **Risco:** algum modulo remanescente ainda importar `db.py`/`psycopg` indiretamente.  
  **Mitigacao:** busca global por imports e execucao de testes/smoke sem variaveis `POSTGRES_*`.

- **Risco:** suites de teste falharem por expectativa antiga de endpoints removidos.  
  **Mitigacao:** alinhar testes ao novo escopo funcional e remover cenarios fora de escopo.

- **Risco:** documentacao ficar inconsistente com a API real.  
  **Mitigacao:** atualizar README e validar rotas publicadas em `/docs`.

- **Risco:** impacto em clientes que consomem endpoints removidos.  
  **Mitigacao:** registrar breaking change no changelog e comunicar remocao no release.

## Estrategia de validacao

1. Subir a API localmente sem servico PostgreSQL.
2. Verificar disponibilidade de `/health` (e demais rotas stateless mantidas).
3. Confirmar que `/users`, `/farms`, `/fields`, `/whatsapp` nao existem mais (404).
4. Confirmar que `openapi.json` e `/docs` nao expoem as rotas removidas.
5. Rodar testes atualizados e garantir que nenhum teste dependa de PostgreSQL no fluxo principal.
6. Executar smoke sem `POSTGRES_*` e validar ausencia de tentativas de import/conexao DB no startup/request path.

## Criterios de sucesso

- API inicia e responde sem PostgreSQL.
- Endpoints `users`, `farms`, `fields` e `whatsapp` removidos do roteamento.
- Nenhuma dependencia obrigatoria de PostgreSQL no caminho principal de execucao e no comando padrao de testes.
- Documentacao e testes coerentes com o novo escopo.
