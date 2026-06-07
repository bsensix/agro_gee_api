# Roadmap de Implementacao - Agro Insight

> Este roadmap organiza o projeto em fases incrementais para permitir entrega continua de valor.
> Cada fase tem tarefas orientadas a agentes, criterios de pronto e dependencias.

## Como executar este roadmap

- Cadencia sugerida: 1 fase por vez, com checkpoints semanais.
- Regra de ouro: so avancar quando a fase atual estiver com criterios de pronto atendidos.
- Cada tarefa abaixo foi escrita para ser executada por um agente especializado (ou pessoa responsavel).

## Agentes e responsabilidades

- Agente Arquiteto: define padroes tecnicos, contratos entre modulos e decisoes de arquitetura.
- Agente Plataforma/DevOps: Docker, Compose, infraestrutura base, CI/CD e observabilidade.
- Agente Banco Geoespacial: modelagem PostgreSQL/PostGIS, migracoes, seeds e performance SQL.
- Agente Earth Engine: integracao com Google Earth Engine, extracao de dados e imagens.
- Agente ETL/Airflow: pipelines RAW/BRONZE/SILVER/GOLD e agendamentos.
- Agente API/FastAPI: endpoints, validacoes, autenticacao e integracao entre servicos.
- Agente IA/LLM: classificacao de intencao, geracao de SQL e orquestracao de agentes.
- Agente Agronomico: interpretacao dos indicadores e geracao de recomendacoes.
- Agente WhatsApp: webhook, mensageria e experiencia conversacional.
- Agente QA/Seguranca: testes, qualidade, controle de acesso, logs e monitoramento.

---

## Fase 0 - Fundacao do projeto (Semana 1)

**Objetivo:** criar base de repositorio, padroes e ambiente local funcional.

### Tasks por agente

- [x] **Agente Arquiteto:** definir arquitetura inicial por modulos (`api`, `services`, `database`, `airflow`, `tests`) e regras de comunicacao entre eles.
- [x] **Agente Plataforma/DevOps:** criar `docker-compose` com API, Postgres/PostGIS e Airflow em ambiente local.
- [x] **Agente Plataforma/DevOps:** configurar variaveis de ambiente e templates (`.env.example`) para OpenAI, GCP e WhatsApp.
- [x] **Agente API/FastAPI:** criar esqueleto da API com healthcheck (`/health`) e estrutura de rotas por dominio.
- [x] **Agente Banco Geoespacial:** inicializar esquema base e migracao inicial.
- [x] **Agente QA/Seguranca:** configurar testes iniciais (smoke tests) e checklist minimo de seguranca.

### Criterios de pronto

- Stack sobe localmente com um comando.
- API responde healthcheck.
- Banco PostGIS acessivel com migracao inicial aplicada.

---

## Fase 1 - Cadastros essenciais (MVP-Base) (Semanas 2-3)

**Objetivo:** permitir gestao de usuarios, fazendas e talhoes com geometria.

### Tasks por agente

- [x] **Agente Banco Geoespacial:** modelar tabelas `users`, `farms`, `fields` com chaves e geometria.
- [x] **Agente API/FastAPI:** implementar CRUD de usuarios, fazendas e talhoes.
- [x] **Agente API/FastAPI:** validar geometrias de entrada (SRID, poligono valido, area calculada).
- [x] **Agente QA/Seguranca:** criar testes de integracao para CRUD e validacao de geometria.
- [x] **Agente QA/Seguranca:** implementar autorizacao basica por usuario/empresa.

### Criterios de pronto

- Usuario cadastra fazenda e talhoes via API.
- Geometria persistida corretamente no PostGIS.
- Testes de integracao principais passando.

---

## Fase 2 - Integracao Google Earth Engine (MVP-Data) (Semanas 4-5)

**Objetivo:** buscar dados de satelite e extrair informacoes por ponto/poligono.

### Tasks por agente

- [x] **Agente Earth Engine:** implementar autenticacao GCP/OAuth para GEE.
  - [x] Fase 2A: autenticacao via Service Account entregue para consulta Sentinel-2 stats.
  - [x] Fase 2B: suporte adicional de configuracao OAuth por variaveis de ambiente.
  - [x] Runtime real com `ee.Initialize(...)` e validacao de credenciais via `POST /gee/auth/test`.
- [x] **Agente Earth Engine:** criar servico com operacoes `datasets`, `extract/point`, `extract/polygon`, `timeseries`, `image`.
  - [x] Fase 2A: operacao inicial `POST /gee/sentinel2/stats` com `ndvi_mean`.
  - [x] Fase 2B: implementar `datasets`, `extract/point`, `extract/polygon`, `timeseries` e `image`.
- [x] **Agente API/FastAPI:** expor endpoints para consumo do servico GEE.
  - [x] Fase 2A: endpoint `POST /gee/sentinel2/stats` com contrato de erro rastreavel.
  - [x] Fase 2B: expor endpoints restantes de extracao e imagem.
  - [x] Endpoint de diagnostico `POST /gee/auth/test` com controle de acesso admin/internal.
- [x] **Agente Banco Geoespacial:** criar catalogo `gee_datasets` para datasets utilizados.
- [x] **Agente QA/Seguranca:** testar cenarios com limites de area, datas invalidas e indisponibilidade do GEE.
  - [x] Fase 2A: cobertura automatizada de area, datas e indisponibilidade/timeout no endpoint stats.
  - [x] Fase 2B: cobertura automatizada de `extract/*`, `timeseries`, `image` e `datasets` em testes de servico/rota.
  - [x] Fase 2B: ampliar cobertura de integracao para todos os endpoints de extracao e imagem (contrato de API).

### Criterios de pronto

- API retorna extracoes por ponto e poligono para Sentinel-2.
- Endpoint de imagem gera saida utilizavel.
- Falhas externas (GEE fora) retornam erros tratados e rastreaveis.

---

## Fase 3 - Pipeline de dados e camada analitica (MVP-Analytics) (Semanas 6-8)

**Objetivo:** automatizar ingestao e disponibilizar indicadores prontos (com foco inicial em NDVI).

### Tasks por agente

- [ ] **Agente ETL/Airflow:** criar DAG de ingestao periodica do GEE para camada RAW.
- [ ] **Agente ETL/Airflow:** implementar transformacoes BRONZE e SILVER (padronizacao de datas, CRS e metadados).
- [ ] **Agente ETL/Airflow:** criar camada GOLD inicial com `gold_ndvi`.
- [ ] **Agente Banco Geoespacial:** criar estrutura de grade (`grids`) e observacoes (`observations`).
- [ ] **Agente Banco Geoespacial:** otimizar indices espaciais e temporais para consultas frequentes.
- [ ] **Agente QA/Seguranca:** validar qualidade de dados (completude, consistencia temporal, valores fora de faixa).

### Criterios de pronto

- Pipeline agendado executa sem intervencao manual.
- NDVI fica disponivel para consulta analitica.
- Execucoes e falhas sao auditaveis em logs.

---

## Fase 4 - IA para perguntas em linguagem natural (MVP-IA) (Semanas 9-10)

**Objetivo:** transformar perguntas em SQL e retornar resposta interpretada.

### Tasks por agente

- [ ] **Agente IA/LLM:** implementar classificador de intencao e extracao de entidades (fazenda, periodo, indicador).
- [ ] **Agente IA/LLM:** criar agente SQL com regras de seguranca (somente leitura, limite de linhas, timeout).
- [ ] **Agente IA/LLM:** configurar prompt engineering para traducao pergunta -> SQL -> resposta estruturada.
- [ ] **Agente Agronomico:** implementar interpretacao do resultado NDVI com linguagem acessivel.
- [ ] **Agente QA/Seguranca:** criar suite de testes de prompts e consultas maliciosas (SQL injection prompt-based).

### Criterios de pronto

- Perguntas de NDVI em linguagem natural retornam resposta coerente.
- SQL gerado respeita escopo de seguranca.
- Resposta textual inclui contexto agronomico minimo.

---

## Fase 5 - Integracao WhatsApp (MVP-Go Live Interno) (Semanas 11-12)

**Objetivo:** permitir interacao ponta a ponta via WhatsApp com resposta textual e mapa.

### Tasks por agente

- [ ] **Agente WhatsApp:** configurar webhook de recebimento e envio.
- [ ] **Agente API/FastAPI:** integrar fluxo WhatsApp -> IA -> Banco -> Resposta.
- [ ] **Agente Earth Engine:** anexar mapa (imagem) quando consulta exigir visualizacao espacial.
- [ ] **Agente QA/Seguranca:** validar idempotencia de mensagens, retries e tratamento de duplicidade.
- [ ] **Agente Plataforma/DevOps:** configurar observabilidade de ponta a ponta (correlation id por mensagem).

### Criterios de pronto

- Usuario envia pergunta no WhatsApp e recebe resposta completa.
- Quando aplicavel, resposta inclui mapa anexado.
- Fluxo completo rastreavel em logs.

---

## Fase 6 - Versao 1.0 (Semanas 13-16)

**Objetivo:** expandir indicadores e robustez operacional.

### Tasks por agente

- [ ] **Agente ETL/Airflow:** adicionar NDWI, EVI, chuva e temperatura na camada GOLD.
- [ ] **Agente IA/LLM:** adaptar agente SQL para novos indicadores e series temporais.
- [ ] **Agente Agronomico:** evoluir interpretacoes por indicador e combinacoes basicas.
- [ ] **Agente QA/Seguranca:** testes de carga, regressao e validacao de performance.
- [ ] **Agente Plataforma/DevOps:** preparar ambiente de producao e rotinas de backup/restore.

### Criterios de pronto

- Consultas multi-indicador funcionam com tempos aceitaveis.
- Plataforma pronta para primeiros usuarios reais.

---

## Fase 7 - Versao 2.0 (evolucao) (Pos-MVP)

**Objetivo:** plataforma preditiva e prescritiva com multiagentes e integracoes externas.

### Tasks por agente

- [ ] **Agente IA/LLM:** implementar orquestracao multiagente (SQL + Agronomico + Alertas).
- [ ] **Agente IA/LLM:** criar deteccao de anomalias e gatilhos de alertas automaticos.
- [ ] **Agente Agronomico:** gerar recomendacoes agronomicas contextualizadas por talhao.
- [ ] **Agente Integracoes:** conectar estacoes meteorologicas, sensores IoT e colhedoras.
- [ ] **Agente QA/Seguranca:** reforcar governanca de dados e trilhas de auditoria.

### Criterios de pronto

- Sistema envia alertas proativos com justificativa.
- Dados externos enriquecem as analises de forma confiavel.

---

## Backlog tecnico transversal (executar em paralelo)

- [ ] Padronizar logs estruturados para API, ETL, IA e WhatsApp.
- [ ] Definir estrategia de versionamento de prompts e modelos.
- [ ] Criar politicas de permissao por empresa, fazenda e talhao (RBAC).
- [ ] Definir SLOs (latencia, disponibilidade, taxa de erro) e alertas.
- [ ] Criar estrategia de custos (OpenAI, GCP/GEE, armazenamento e mensageria).

## Priorizacao recomendada para iniciar agora

1. Fase 0 (fundacao)
2. Fase 1 (cadastros)
3. Fase 2 (Earth Engine com Sentinel-2)
4. Fase 3 (NDVI em pipeline GOLD)
5. Fase 4 + Fase 5 (IA + WhatsApp)

## Definicao de pronto global do MVP

- Usuario autenticado pergunta no WhatsApp sobre NDVI por fazenda/talhao e periodo.
- Sistema retorna resposta textual interpretada + mapa.
- Fluxo completo auditavel e com testes essenciais passando.
