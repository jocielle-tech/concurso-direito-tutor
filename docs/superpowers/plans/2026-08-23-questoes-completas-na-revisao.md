# Questões completas na revisão da apostila — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persistir enunciado e todas as alternativas junto de cada resposta corrigida e reproduzir esse bloco completo nos materiais Markdown, HTML e PDF.

**Architecture:** A sessão Markdown continua sendo a fonte única. O marcador opcional `question_content_version: 1` ativa validação estrutural somente para sessões novas concluídas; sessões antigas permanecem válidas. Os arquivos derivados copiam o bloco canônico, enquanto HTML e PDF ganham renderização específica para pergunta, alternativas e feedback.

**Tech Stack:** Python 3, biblioteca padrão, ReportLab, Markdown canônico, HTML/CSS/JavaScript autocontido, `unittest`, PyPDF, Playwright/controle de navegador para inspeção visual.

## Global Constraints

- Novas sessões principais persistem `question_target: 20`, `theory_briefing_version: 1` e `question_content_version: 1`.
- Uma sessão concluída com `question_content_version: 1` contém exatamente 20 blocos completos.
- Cada bloco mantém a ordem `Pergunta` → `Alternativas` → `Resposta e feedback`.
- Todas as alternativas apresentadas ao aluno são preservadas; o validador aceita duas ou mais opções rotuladas.
- Sessões legadas sem `question_content_version` continuam válidas sem migração.
- Não criar banco de questões, dependência externa ou cópia manual de arquivos derivados.
- Markdown, HTML e PDF apresentam a pergunta antes da resposta e do gabarito.

---

### Task 1: Contrato canônico e validação versionada

**Files:**
- Modify: `tests/trilha_support.py`
- Modify: `tests/test_build_trilha.py`
- Modify: `scripts/build_trilha.py`

**Interfaces:**
- Consumes: `session_sections(text, title)`, `parse_question_feedback(text)` e o manifesto schema v1 existentes.
- Produces: `validate_question_content(text: str, session: dict) -> None` e fixtures com blocos completos.

- [ ] **Step 1: Expandir a fixture sem quebrar testes legados**

Adicionar um parâmetro explícito ao helper:

```python
def question_feedback(number, topic_id="controle", include_content=False):
    content = ""
    if include_content:
        content = f"""\n#### Pergunta
Qual regra jurídica se aplica à situação {number}?

#### Alternativas
- A) Aplica-se a regra constitucional indicada.
- B) Afasta-se toda competência constitucional.
- C) A decisão independe de fundamento normativo.
- D) O controle é sempre administrativo.
- E) Não existe revisão possível.

#### Resposta e feedback
"""
    return f"""### Questão {number}
- Tópico: {topic_id}
{content}- Resposta: alternativa A
...
"""
```

Fazer `feedback_section(..., include_content=False)` encaminhar o parâmetro para os 20 blocos. O padrão `False` preserva os casos legados existentes.

- [ ] **Step 2: Escrever testes de manifesto e estrutura que falham**

Cobrir em `tests/test_build_trilha.py`:

```python
def test_question_content_version_must_be_integer_one(self):
    manifest = self.manifest()
    manifest["sessions"][0]["question_content_version"] = "1"
    self.write_manifest(manifest)
    result = self.run_builder()
    self.assertIn("question_content_version deve ser o inteiro 1", result.stderr)

def test_completed_versioned_session_accepts_complete_questions(self):
    manifest = self.manifest()
    manifest["sessions"][0]["question_content_version"] = 1
    self.write_manifest(manifest)
    self.write_session(feedback=feedback_section(include_content=True))
    self.assertEqual(self.run_builder().returncode, 0)
```

Adicionar subtestes que removem, duplicam ou reordenam `#### Pergunta`, `#### Alternativas` e `#### Resposta e feedback`, além de opções vazias, sem rótulo e com menos de duas alternativas. Confirmar também que uma sessão concluída sem o marcador continua válida.

- [ ] **Step 3: Executar os testes e confirmar a falha**

Run: `python3 -m unittest tests.test_build_trilha -v`

Expected: os novos testes falham porque o marcador e a estrutura ainda não são validados.

- [ ] **Step 4: Implementar o parser estrutural mínimo**

Em `scripts/build_trilha.py`, adicionar:

```python
QUESTION_CONTENT_HEADINGS = ("Pergunta", "Alternativas", "Resposta e feedback")
OPTION_ITEM = re.compile(r"^\s*[-*]\s+([A-Z]|Certo|Errado)[).:]\s+\S", re.MULTILINE | re.IGNORECASE)

def validate_question_content(text, session):
    questions, _diagnosis = parse_question_feedback(text)
    for question in questions:
        headings = list(re.finditer(r"^####\s+(.+?)\s*$", question.block, re.MULTILINE))
        names = [heading.group(1) for heading in headings]
        if names != list(QUESTION_CONTENT_HEADINGS):
            raise ValidationError(
                f"sessão '{session['id']}': questão {question.number} deve conter "
                "Pergunta, Alternativas e Resposta e feedback, uma vez e nessa ordem"
            )
        bodies = {}
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(question.block)
            bodies[heading.group(1)] = question.block[heading.end():end].strip()
        if not bodies["Pergunta"]:
            raise ValidationError(f"sessão '{session['id']}': questão {question.number} sem pergunta")
        if len(OPTION_ITEM.findall(bodies["Alternativas"])) < 2:
            raise ValidationError(
                f"sessão '{session['id']}': questão {question.number} exige ao menos duas alternativas rotuladas"
            )
        missing = missing_feedback_fields(bodies["Resposta e feedback"], QUESTION_FIELDS)
        if missing:
            raise ValidationError(
                f"sessão '{session['id']}': questão sem campos obrigatórios: {', '.join(missing)}"
            )
```

Validar `question_content_version` junto dos outros marcadores e chamar `validate_question_content` apenas em sessões `completed` com valor `1`.

- [ ] **Step 5: Executar testes focados e corrigir somente o necessário**

Run: `python3 -m unittest tests.test_build_trilha -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_trilha.py tests/test_build_trilha.py tests/trilha_support.py
git commit -m "feat: validate complete question review blocks"
```

---

### Task 2: Propagação para materiais Markdown

**Files:**
- Modify: `tests/test_hybrid_outputs.py`
- Modify: `scripts/trilha_outputs.py` somente se o teste revelar perda do bloco canônico.

**Interfaces:**
- Consumes: blocos `### Questão N` validados pela Task 1.
- Produces: cópia integral nos arquivos `questoes.md`, `materiais/caderno-de-questoes.md` e `apostila/apostila.md`.

- [ ] **Step 1: Escrever teste de propagação que falha se houver perda ou reordenação**

Criar uma trilha versionada com `feedback_section(include_content=True)`, executar o build e verificar em cada saída:

```python
for relative in (
    "modulos/01-constitucional/topicos/01-controle/questoes.md",
    "materiais/caderno-de-questoes.md",
    "apostila/apostila.md",
):
    document = (self.trail / relative).read_text(encoding="utf-8")
    question = document.index("#### Pergunta")
    alternatives = document.index("#### Alternativas", question)
    answer = document.index("#### Resposta e feedback", alternatives)
    self.assertLess(question, alternatives)
    self.assertLess(alternatives, answer)
    self.assertIn("Qual regra jurídica se aplica", document)
    self.assertIn("- E) Não existe revisão possível.", document)
```

- [ ] **Step 2: Executar o teste focado**

Run: `python3 -m unittest tests.test_hybrid_outputs -v`

Expected: PASS com o extrator atual; se falhar, ajustar `_question_blocks` para encerrar somente no próximo `###`, preservando todos os `####` internos.

- [ ] **Step 3: Executar testes dos dois componentes**

Run: `python3 -m unittest tests.test_build_trilha tests.test_hybrid_outputs -v`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_hybrid_outputs.py scripts/trilha_outputs.py
git commit -m "test: preserve complete questions in markdown outputs"
```

---

### Task 3: Cartões completos no HTML interativo

**Files:**
- Modify: `tests/test_html_dashboard.py`
- Modify: `tests/test_hybrid_outputs.py`
- Modify: `scripts/trilha_html.py`

**Interfaces:**
- Consumes: linhas internas de cada bloco canônico.
- Produces: `_question_card(title: str, lines: list[str], local_fragments: set[str]) -> str` com regiões `.question-prompt`, `.question-options` e `.question-feedback`.

- [ ] **Step 1: Escrever testes de estrutura, ordem e escape**

Exigir que o HTML gerado contenha uma estrutura equivalente a:

```html
<section class="question-card">
  <h5>Questão 1</h5>
  <div class="question-prompt"><h6>Pergunta</h6>...</div>
  <div class="question-options"><h6>Alternativas</h6>...</div>
  <div class="question-feedback"><h6>Resposta e feedback</h6>...</div>
</section>
```

Verificar que a posição de `question-prompt` antecede `question-options`, que antecede `question-feedback`, e que `<script>` presente em um enunciado aparece escapado como `&lt;script&gt;`.

- [ ] **Step 2: Executar os testes e confirmar a falha**

Run: `python3 -m unittest tests.test_html_dashboard tests.test_hybrid_outputs -v`

Expected: FAIL porque `_question_card` ainda transforma os subtítulos em parágrafos genéricos.

- [ ] **Step 3: Implementar parser e componentes do cartão**

Separar metadados anteriores ao primeiro `####`, localizar os três subtítulos internos e renderizar:

```python
prompt = '<div class="question-prompt"><h6>Pergunta</h6>' + render_body(parts["Pergunta"]) + "</div>"
options = '<div class="question-options"><h6>Alternativas</h6>' + render_options(parts["Alternativas"]) + "</div>"
feedback = '<div class="question-feedback"><h6>Resposta e feedback</h6>' + render_fields(parts["Resposta e feedback"]) + "</div>"
```

Manter o caminho legado quando não houver subtítulos `####`, para que apostilas antigas continuem com a aparência atual. Usar `safe_inline` em todo conteúdo e preservar links locais válidos.

- [ ] **Step 4: Adicionar CSS autocontido e estilos de impressão**

Adicionar estilos para:

```css
.question-prompt { background:#EEF2FF; border-left:4px solid #4F46E5; }
.question-options { background:#F8FAFC; }
.question-options ul { list-style:none; padding-left:0; }
.question-feedback { background:#FAF5FF; border-left:4px solid #8B5CF6; }
.question-card h6 { margin:.2rem 0 .55rem; color:#312E81; }
```

No `@media print`, impedir que o título fique isolado do início da pergunta e evitar quebra interna de alternativas curtas quando possível.

- [ ] **Step 5: Executar testes HTML e regressões de links/índice**

Run: `python3 -m unittest tests.test_html_dashboard tests.test_hybrid_outputs -v`

Expected: PASS, inclusive índice lateral, navegação sem JavaScript e links existentes.

- [ ] **Step 6: Commit**

```bash
git add scripts/trilha_html.py tests/test_html_dashboard.py tests/test_hybrid_outputs.py
git commit -m "feat: render complete question cards in html"
```

---

### Task 4: Paginação e revisão completa no PDF

**Files:**
- Modify: `tests/test_pdf_output.py`
- Modify: `scripts/trilha_pdf.py`

**Interfaces:**
- Consumes: os mesmos blocos canônicos usados pelo HTML.
- Produces: grupos estruturados com metadados, pergunta, alternativas e feedback, usados por `render_pdf`.

- [ ] **Step 1: Escrever teste de texto e ordem no PDF**

Construir uma sessão versionada, extrair texto com `PdfReader` e verificar:

```python
text = "\n".join(page.extract_text() or "" for page in reader.pages)
self.assertLess(text.index("Pergunta"), text.index("Alternativas"))
self.assertLess(text.index("Alternativas"), text.index("Resposta e feedback"))
self.assertLess(text.index("Resposta e feedback"), text.index("Resultado:"))
self.assertIn("Qual regra jurídica se aplica", text)
self.assertIn("E) Não existe revisão possível.", text)
```

Manter o teste de bytes determinísticos e o teste de links externos.

- [ ] **Step 2: Executar o teste e confirmar a falha**

Run: `python3 -m unittest tests.test_pdf_output -v`

Expected: FAIL porque `_question_groups` devolve apenas linhas indiferenciadas.

- [ ] **Step 3: Estruturar os grupos e renderizar áreas distintas**

Fazer `_question_groups` reconhecer os subtítulos `####` e devolver um objeto ou dicionário com `metadata`, `question`, `alternatives` e `feedback`. Para blocos legados, devolver a representação anterior.

No renderer:

```python
intro = [
    Paragraph(_paragraph_markup(question_title), styles["QuestionTitle"]),
    Paragraph("Pergunta", styles["QuestionPartTitle"]),
    Paragraph(_paragraph_markup(prompt), styles["TrailBody"]),
]
story.append(KeepTogether(intro))
```

Renderizar alternativas imediatamente depois e o feedback em tabela com fundo lilás claro. Não envolver uma questão inteira em `KeepTogether`, pois enunciados longos precisam paginar.

- [ ] **Step 4: Executar testes PDF**

Run: `python3 -m unittest tests.test_pdf_output -v`

Expected: PASS com texto pesquisável na ordem canônica, links e bytes determinísticos.

- [ ] **Step 5: Commit**

```bash
git add scripts/trilha_pdf.py tests/test_pdf_output.py
git commit -m "feat: render complete questions in pdf"
```

---

### Task 5: Contrato da skill, README e exemplo visual

**Files:**
- Modify: `SKILL.md`
- Modify: `references/trilha-e-apostila.md`
- Modify: `README.md`
- Modify: `agents/openai.yaml`
- Modify: `tests/test_skill_contract.py`
- Modify: `assets/readme/apostila-preview.png`

**Interfaces:**
- Consumes: contrato e classes entregues nas Tasks 1–4.
- Produces: instruções públicas e operacionais coerentes com `question_content_version: 1`.

- [ ] **Step 1: Escrever testes de contrato que falham**

Exigir em `tests/test_skill_contract.py`:

```python
self.assertIn("question_content_version: 1", skill)
self.assertIn("enunciado integral", skill)
self.assertIn("todas as alternativas", skill)
self.assertIn("materiais/caderno-de-questoes.md", readme)
self.assertIn("pergunta e todas as alternativas", readme.lower())
```

Também verificar que a referência mostra os três subtítulos na ordem correta e documenta a compatibilidade legada.

- [ ] **Step 2: Executar o teste e confirmar a falha**

Run: `python3 -m unittest tests.test_skill_contract -v`

Expected: FAIL porque a documentação ainda descreve apenas feedbacks.

- [ ] **Step 3: Atualizar o contrato operacional e público**

No `SKILL.md`, exigir o novo marcador na abertura e o registro fiel de enunciado e alternativas após as respostas. Na referência, atualizar o JSON, o fluxo, o modelo canônico e a regra de compatibilidade. No README, destacar revisão autossuficiente e listar os caminhos exatos. Em `agents/openai.yaml`, acrescentar a revisão completa à descrição curta sem remover teoria, 20 questões, mapas, HTML e PDF.

- [ ] **Step 4: Executar testes de contrato**

Run: `python3 -m unittest tests.test_skill_contract -v`

Expected: PASS.

- [ ] **Step 5: Atualizar e inspecionar a captura real**

Gerar uma apostila de exemplo com `question_content_version: 1`, servir o diretório localmente e capturar `assets/readme/apostila-preview.png` em largura de 1280 px. A imagem deve mostrar índice lateral, progresso e ao menos um cartão com pergunta, alternativas e feedback. Inspecionar o PNG antes do commit e remover arquivos temporários.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md references/trilha-e-apostila.md README.md agents/openai.yaml tests/test_skill_contract.py assets/readme/apostila-preview.png
git commit -m "docs: explain complete question review outputs"
```

---

### Task 6: Verificação integrada e publicação

**Files:**
- Modify: somente arquivos das Tasks 1–5 se uma falha revelar defeito dentro do escopo.

**Interfaces:**
- Consumes: todos os componentes implementados.
- Produces: branch `main` limpa, validada e sincronizada com o repositório público.

- [ ] **Step 1: Executar a suíte completa**

Run: `python3 -m unittest discover -s tests -v`

Expected: todos os testes PASS.

- [ ] **Step 2: Executar a validação rápida da skill**

Run: `python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/testes/.codex/skills/concurso-direito-tutor`

Expected: `Skill is valid!`

- [ ] **Step 3: Verificar qualidade do repositório**

Run: `git diff --check && git status --short && git log --oneline -8`

Expected: sem erro de whitespace; apenas alterações intencionais já commitadas.

- [ ] **Step 4: Publicar no GitHub**

Run: `git push origin main`

Expected: `main` atualizada em `jocielle-tech/concurso-direito-tutor`.

- [ ] **Step 5: Confirmar sincronização**

Run: `git status --short --branch && git rev-parse HEAD && git rev-parse origin/main`

Expected: worktree limpa e os dois hashes idênticos.

