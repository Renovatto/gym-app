# Backlog aprovado

## ROT-001 — Implementar prévia editável e aplicação segura de rotinas

- **Escopo:** entregar os fluxos aprovados nos artefatos `rotinas-nivel-previa-e-equipamentos.html` e `rotinas-revisao-senior.html`: configuração de nível/equipamentos, prévia editável antes de gravar, aplicação para criar/renovar/copiar/substituir, preservação de contexto, feedback e traduções; incluir validação backend, persistência idempotente e testes.
- **Status:** concluído (implementação e validação local)
- **Aprovado em:** 2026-10-30
- **Correção de regressão (2026-10-31):** escolha rápida e prévia compartilham uma única entrada de Voltar; modais filhas consomem só sua própria profundidade; validado em E2E para adicionar, substituir e trocar exercício.
- **Correção do deploy (2026-10-31):** modelo declara `created_at` do recibo como timestamp com fuso, igual à migration; `alembic check` local sem diferenças.
