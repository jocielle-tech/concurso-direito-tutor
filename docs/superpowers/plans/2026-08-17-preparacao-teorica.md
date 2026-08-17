# Preparação Teórica Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exigir uma aula teórica detalhada e confirmada pelo aluno antes das 20 questões de toda nova sessão principal.

**Architecture:** Reutilizar `## Conteúdo principal` como fonte canônica e adicionar o marcador opcional `theory_briefing_version: 1` ao manifesto. Validar apenas sessões opt-in, propagar a aula aos derivados e manter sessões legadas sem migração.

**Tech Stack:** Python 3, unittest, Markdown, HTML autocontido, ReportLab, Playwright CLI e Poppler.

## Global Constraints

- Apresentar a aula e aguardar confirmação antes de qualquer questão.
- Manter exatamente 20 questões juntas e corrigir apenas após as 20 respostas.
- Não aumentar progresso enquanto a sessão estiver `in_progress`.
- Preservar sessões legadas sem `theory_briefing_version`.
- Publicar somente após testes automatizados e inspeção real de HTML/PDF.

---

### Task 1: Contrato e validação

**Files:** `scripts/build_trilha.py`, `tests/test_build_trilha.py`, `tests/trilha_support.py`

- [ ] Escrever testes que rejeitem versão inválida e preparação incompleta, aceitem a versão 1 estruturada e preservem sessões legadas.
- [ ] Executar os testes e confirmar RED pelas regras ausentes.
- [ ] Implementar validação opt-in dos subtítulos obrigatórios.
- [ ] Executar testes focados e a suíte de build; commitar.

### Task 2: Outputs completos e hierarquia visual

**Files:** `scripts/trilha_outputs.py`, `scripts/trilha_html.py`, `scripts/trilha_pdf.py`, testes de outputs

- [ ] Escrever testes para incluir a aula nos resumos e preservar a ordem aula → resumo estratégico → questões em MD/HTML/PDF.
- [ ] Confirmar RED, implementar a propagação e renderizar subtítulos internos com hierarquia visual.
- [ ] Verificar testes focados, links, determinismo e renderização PDF; commitar.

### Task 3: Comportamento e documentação da skill

**Files:** `SKILL.md`, `references/trilha-e-apostila.md`, `agents/openai.yaml`, `README.md`, asset demonstrativo

- [ ] Registrar um teste de contrato que falhe com o fluxo anterior.
- [ ] Documentar a pausa obrigatória, a estrutura da aula, o marcador, os outputs e exemplos de uso.
- [ ] Atualizar a prévia pública com uma trilha real contendo preparação detalhada.
- [ ] Executar validação da skill, teste de contrato e inspeção Playwright; commitar.

### Task 4: Gate e publicação

- [ ] Executar suíte completa, validação rápida, sintaxe, diff-check, HTML e PDF reais.
- [ ] Revisar o diff, integrar na `main`, repetir o gate e enviar ao repositório público no GitHub.
