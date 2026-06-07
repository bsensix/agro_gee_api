# Security Baseline

Este checklist define o baseline de seguranca para a Fase 0.

## Secrets e configuracao

- Nunca versionar credenciais reais; usar apenas `.env.example` como referencia.
- Configurar segredos no ambiente de execucao e no provedor de CI.
- Rotacionar credenciais expostas e invalidar tokens comprometidos.

## Dependencias e atualizacoes

- Declarar dependencias no `pyproject.toml` com faixas de versao.
- Atualizar dependencias regularmente para corrigir vulnerabilidades conhecidas.
- Revisar changelogs antes de adotar versoes maiores.

## CI e qualidade

- Executar `pytest -v` em push e pull request.
- Bloquear merge quando pipeline de testes falhar.
- Manter testes de contrato para garantir que o workflow siga o baseline.

## Boas praticas operacionais

- Aplicar principio de menor privilegio para usuarios e servicos.
- Evitar logs com dados sensiveis (tokens, senhas, segredos).
- Documentar incidentes e acoes de mitigacao para rastreabilidade.
