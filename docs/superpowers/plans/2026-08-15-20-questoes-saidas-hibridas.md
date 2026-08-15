# 20 Questions and Hybrid Study Outputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require 20 questions per new study session and generate a safely migrated, searchable study project with Markdown, interactive HTML, and polished PDF outputs.

**Architecture:** Keep `scripts/build_trilha.py` as the CLI and validation coordinator, extract derived-file layout, migration, and PDF generation into focused modules, and treat the manifest plus canonical session Markdown as sources of truth. Build every derived artifact in memory or temporary paths, validate the complete bundle, then publish with rollback; legacy trails migrate through a validated sibling copy and a ZIP backup.

**Tech Stack:** Python 3 standard library, ReportLab 4+, pypdf 5+, pdfplumber 0.11+, unittest, Playwright CLI for browser verification, Poppler for PDF visual verification when available.

## Global Constraints

- New sessions use exactly 20 questions total, presented together and corrected only after all 20 answers.
- A session that the learner abandons early remains `in_progress` and does not increase progress.
- New completed sessions use `question_target: 20`; legacy sessions without that field remain valid.
- Every targeted feedback names a valid topic, and every topic in the session is tested at least once.
- `trilha.json` and canonical session Markdown are sources; panels, topic extracts, consolidated materials, and apostilas are generated files.
- Generate Markdown, self-contained HTML, and PDF together without replacing valid outputs after any failure.
- HTML uses no CDN and remains navigable without JavaScript.
- PDF generation requires ReportLab; `--check` remains usable without PDF dependencies.
- Migration creates a ZIP backup, preserves IDs/status/content, validates before publish, rolls back on failure, and is idempotent.
- Keep unsafe URL schemes inactive and all filesystem paths contained inside the trail.
- Use TDD for code and RED-GREEN forward testing for the skill instructions.

---

## File responsibility map

- `scripts/build_trilha.py`: CLI parsing, manifest/session validation, progress calculations, Markdown/HTML orchestration, controlled exit codes.
- `scripts/trilha_outputs.py`: stable slugs/ordinals, hybrid path mapping, section extraction, derived Markdown bundle, multi-file transactional publish.
- `scripts/trilha_migration.py`: legacy detection, ZIP backup, staged migration, atomic directory swap, rollback.
- `scripts/trilha_pdf.py`: lazy ReportLab imports, PDF styles, bookmarks, links, pagination, deterministic PDF bytes.
- `tests/trilha_support.py`: shared temporary-trail builder and complete 20-question fixture.
- `tests/test_build_trilha.py`: existing regression coverage plus targeted-question validation.
- `tests/test_hybrid_outputs.py`: folder layout, derived materials, transaction rollback, HTML navigation/link integrity.
- `tests/test_migration.py`: legacy detection, migration, backup, rollback, idempotence.
- `tests/test_pdf_output.py`: missing dependency behavior, deterministic PDF, extracted text, page count, annotations.
- `requirements.txt`: PDF runtime and validation dependencies.
- `SKILL.md`, `references/trilha-e-apostila.md`, `agents/openai.yaml`, `README.md`: discovery metadata, tutoring contract, UI prompt, and public feature documentation.
- `assets/readme/apostila-preview.png`: real refreshed HTML preview after the renderer changes.

---

### Task 1: Establish the skill RED baseline and the 20-question contract

**Files:**
- Create: `.superpowers/sdd/baseline-20-questions.md` (execution evidence; do not commit)
- Create: `tests/trilha_support.py`
- Modify: `tests/test_build_trilha.py`
- Modify: `scripts/build_trilha.py`

**Interfaces:**
- Produces: `parse_question_feedback(text: str) -> tuple[list[QuestionFeedback], str]`
- Produces: targeted validation based on optional `session["question_target"]`
- `QuestionFeedback`: `number: int`, `topic_id: str | None`, `block: str`

- [ ] **Step 1: Run the no-guidance baseline before editing the skill**

Create a detached checkout at `/tmp/concurso-direito-baseline` on commit `cbe56b9` and use this fresh subagent prompt:

```text
Use $concurso-direito-tutor at /tmp/concurso-direito-baseline/SKILL.md para conduzir uma sessão principal sobre controle de constitucionalidade e direitos fundamentais. Prepare a prática, explique quando corrigirá, e informe quais arquivos serão gerados ao final.
```

Record the response verbatim. Score these failures: no exact 20-question requirement; correction timing open or split; no hybrid tree; no PDF; no scroll-synchronized sidebar.

- [ ] **Step 2: Add shared fixtures and failing tests**

Create `tests/trilha_support.py`:

```python
def question_feedback(number, topic_id="controle"):
    return f"""### Questão {number}
- Tópico: {topic_id}
- Resposta: alternativa A
- Resultado: correta; gabarito A
- Fundamento: Constituição Federal.
- Alternativas úteis: B ignora a competência.
- Tipo de erro: nenhum
- Prevenção: manter a revisão.
- Fonte: https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm
- Revisão: em sete dias.
"""


def feedback_section(count=20, topic_ids=("controle",)):
    blocks = [question_feedback(n, topic_ids[(n - 1) % len(topic_ids)]) for n in range(1, count + 1)]
    blocks.append("""### Diagnóstico agregado
- Acertos: 20/20 (100%).
- Padrões de erro: nenhum.
- Prioridade: consolidar competência.
- Próxima revisão: em sete dias.
""")
    return "\n".join(blocks)
```

Add these tests to `tests/test_build_trilha.py`:

```python
def test_targeted_completed_session_requires_exactly_twenty_questions(self):
    manifest = self.valid_manifest()
    manifest["sessions"][0]["question_target"] = 20
    self.write_manifest(manifest)
    self.write_session("001.md", valid_session("Controle difuso", question_count=19))
    result = self.run_build("--check")
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("exatamente 20 questões", result.stderr)


def test_targeted_questions_cover_every_session_topic(self):
    manifest = self.valid_manifest()
    session = manifest["sessions"][0]
    session.update(question_target=20, topic_ids=["controle", "direitos"])
    manifest["modules"][0]["topics"][1]["sessions"].append("s001")
    self.write_manifest(manifest)
    self.write_session("001.md", valid_session("Controle difuso", topic_ids=("controle",)))
    result = self.run_build("--check")
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("tópico sem questão: direitos", result.stderr)


def test_legacy_completed_session_without_question_target_remains_valid(self):
    self.write_valid_trail()
    result = self.run_build("--check")
    self.assertEqual(result.returncode, 0, result.stderr)
```

Also test duplicate `Questão 7`, skipped `Questão 11`, invalid `Tópico`, non-integer target, and target other than 20. Invalid input must preserve prior outputs and omit tracebacks.

- [ ] **Step 3: Run the targeted test and verify RED**

```bash
python3 -B -m unittest tests.test_build_trilha.BuildTrilhaTests.test_targeted_completed_session_requires_exactly_twenty_questions -v
```

Expected: FAIL because `question_target` is ignored and 19 questions are accepted.

- [ ] **Step 4: Implement the minimal parser and validation**

Add to `scripts/build_trilha.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionFeedback:
    number: int
    topic_id: str | None
    block: str


TARGETED_QUESTION_FIELDS = QUESTION_FIELDS + ("Tópico",)


def field_value(block, field):
    match = re.search(rf"^\s*[-*]\s+{re.escape(field)}:\s*(\S.*?)\s*$", block, re.MULTILINE)
    return match.group(1) if match else None


def parse_question_feedback(text):
    headings = list(re.finditer(r"^###\s+(.+?)\s*$", text, re.MULTILINE))
    questions, diagnosis = [], ""
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end():end]
        question = re.fullmatch(r"Questão\s+(\d+)", heading.group(1))
        if question:
            questions.append(QuestionFeedback(int(question.group(1)), field_value(block, "Tópico"), block))
        elif heading.group(1) == "Diagnóstico agregado":
            diagnosis = block
    return questions, diagnosis
```

Validate the target with:

```python
target = session.get("question_target")
if target is not None and (type(target) is not int or target != 20):
    raise ValidationError(f"sessão '{session['id']}': question_target deve ser o inteiro 20")
```

For completed targeted sessions, require `numbers == list(range(1, 21))`, all nine fields, valid topic IDs, full topic coverage, and a posterior diagnosis. Preserve the legacy path when the field is absent.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -B -m unittest tests.test_build_trilha -v
python3 -B -m unittest discover -s tests -v
git add scripts/build_trilha.py tests/test_build_trilha.py tests/trilha_support.py
git commit -m "feat: require 20 questions in new sessions"
```

Expected: all targeted tests and the existing 16 regressions PASS.

---

### Task 2: Generate the hybrid folder structure and derived Markdown

**Files:**
- Create: `scripts/trilha_outputs.py`
- Create: `tests/test_hybrid_outputs.py`
- Modify: `scripts/build_trilha.py`

**Interfaces:**
- Produces: `build_output_bundle(trail: Path, manifest: dict, session_files: dict[str, str], apostila_md: str, apostila_html: str, apostila_pdf: bytes | None = None) -> dict[Path, bytes]`
- Produces: `publish_bundle(trail: Path, outputs: dict[Path, bytes]) -> None`
- Produces: `canonical_session_relative_path(manifest, session) -> Path`

- [ ] **Step 1: Write failing layout and rollback tests**

Assert the build creates:

```python
expected = {
    "painel/indice.md", "painel/progresso.md", "painel/agenda-de-revisoes.md",
    "materiais/resumos.md", "materiais/mapas-mentais.md", "materiais/caderno-de-questoes.md",
    "revisoes/agenda.md", "apostila/apostila.md", "apostila/apostila.html",
    "modulos/01-direito-constitucional/topicos/01-controle-difuso/resumo.md",
    "modulos/01-direito-constitucional/topicos/01-controle-difuso/mapa-mental.md",
    "modulos/01-direito-constitucional/topicos/01-controle-difuso/questoes.md",
}
self.assertTrue(expected <= {str(p.relative_to(self.trail)) for p in self.trail.rglob("*") if p.is_file()})
```

Every derived Markdown must start with `<!-- GERADO AUTOMATICAMENTE. NÃO EDITE. -->`. Inject a replace failure on the third file and assert every prior output is restored byte for byte.

- [ ] **Step 2: Run the new suite and verify RED**

```bash
python3 -B -m unittest tests.test_hybrid_outputs -v
```

Expected: FAIL because outputs still live at the trail root.

- [ ] **Step 3: Implement stable path helpers**

Create `scripts/trilha_outputs.py`:

```python
import re
import tempfile
import unicodedata
from pathlib import Path

GENERATED_NOTICE = "<!-- GERADO AUTOMATICAMENTE. NÃO EDITE. -->\n\n"


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "item"


def ordered_segment(index, title):
    return f"{index:02d}-{slugify(title)}"


def canonical_session_relative_path(manifest, session):
    module_index = next(i for i, item in enumerate(manifest["modules"], 1) if item["id"] == session["module_id"])
    module = manifest["modules"][module_index - 1]
    topic_id = session["topic_ids"][0]
    topic_index = next(i for i, item in enumerate(module["topics"], 1) if item["id"] == topic_id)
    topic = module["topics"][topic_index - 1]
    session_index = next(i for i, item in enumerate(manifest["sessions"], 1) if item["id"] == session["id"])
    return (Path("modulos") / ordered_segment(module_index, module["title"]) / "topicos"
            / ordered_segment(topic_index, topic["title"]) / "sessoes"
            / f"{session_index:03d}-{slugify(session['title'])}.md")
```

Implement `build_output_bundle` for the exact tree. Topic question files contain only feedback blocks tagged with that topic. A multi-topic session has one canonical source under its first topic; other topic derivatives link to it.

- [ ] **Step 4: Implement transactional multi-file publishing**

```python
def publish_bundle(trail, outputs, replace_file=lambda source, target: source.replace(target)):
    prepared, previous = {}, {}
    try:
        for relative, content in outputs.items():
            target = trail / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            previous[target] = target.read_bytes() if target.exists() else None
            handle = tempfile.NamedTemporaryFile(dir=target.parent, delete=False)
            with handle:
                handle.write(content)
            prepared[target] = Path(handle.name)
        for target, source in prepared.items():
            replace_file(source, target)
    except Exception:
        for target, content in previous.items():
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(content)
        raise
    finally:
        for source in prepared.values():
            source.unlink(missing_ok=True)
```

Build every string/byte before publishing.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -B -m unittest tests.test_hybrid_outputs -v
python3 -B -m unittest discover -s tests -v
git add scripts/build_trilha.py scripts/trilha_outputs.py tests/test_hybrid_outputs.py
git commit -m "feat: generate hybrid study material layout"
```

---

### Task 3: Migrate legacy trails with backup and rollback

**Files:**
- Create: `scripts/trilha_migration.py`
- Create: `tests/test_migration.py`
- Modify: `scripts/build_trilha.py`

**Interfaces:**
- Produces: `is_legacy_trail(trail: Path, manifest: dict) -> bool`
- Produces: `migrate_legacy_trail(trail, build_staged, canonical_path, now) -> None`
- CLI adds mutually exclusive `--check` and `--migrate`; `MIGRATION_REQUIRED_EXIT = 3`

- [ ] **Step 1: Write failing migration tests**

```python
def test_check_reports_migration_required_without_writes(self):
    self.write_legacy_trail()
    before = snapshot_tree(self.trail)
    result = self.run_build("--check")
    self.assertEqual(result.returncode, 3)
    self.assertEqual(result.stderr.strip(), "MIGRATION_REQUIRED")
    self.assertEqual(snapshot_tree(self.trail), before)


def test_migrate_preserves_sessions_and_creates_single_backup(self):
    self.write_legacy_trail()
    result = self.run_build("--migrate")
    self.assertEqual(result.returncode, 0, result.stderr)
    manifest = json.loads((self.trail / "trilha.json").read_text())
    self.assertTrue(manifest["sessions"][0]["file"].startswith("modulos/"))
    self.assertEqual(len(list((self.trail / "backups").glob("migracao-*.zip"))), 1)
```

Also test build failure rollback, second-run idempotence, preservation of IDs/status/text, and ZIP contents including the old manifest, sessions, and root apostilas.

- [ ] **Step 2: Run tests and verify RED**

```bash
python3 -B -m unittest tests.test_migration -v
```

Expected: FAIL because `--migrate` and exit code 3 do not exist.

- [ ] **Step 3: Implement staged migration**

Create a sibling staged copy, archive the original into `backups/migracao-YYYYMMDD-HHMMSS.zip`, copy sessions to canonical paths, update only `session.file`, build/validate the staged tree, then swap directories. Rename the original to a unique sibling before promoting the staged copy; restore it on any promotion failure. Delete legacy files only inside the staged copy and only after replacements and ZIP validation.

Use this detection function:

```python
def is_legacy_trail(trail, manifest):
    return any(Path(session["file"]).parts[:1] == ("sessoes",) for session in manifest["sessions"])
```

Reject a pre-existing swap path with a controlled error rather than overwriting it.

- [ ] **Step 4: Wire CLI semantics**

Use a mutually exclusive argparse group. `--check` on a valid legacy trail prints exactly `MIGRATION_REQUIRED` to stderr and returns 3 without importing PDF dependencies. Normal build does the same. `--migrate` performs the staged migration; the skill invokes it automatically after informing the learner.

- [ ] **Step 5: Run tests and commit**

```bash
python3 -B -m unittest tests.test_migration -v
python3 -B -m unittest discover -s tests -v
git add scripts/build_trilha.py scripts/trilha_migration.py tests/test_migration.py
git commit -m "feat: migrate legacy trails safely"
```

---

### Task 4: Build the interactive HTML sidebar and validate links

**Files:**
- Modify: `scripts/build_trilha.py`
- Modify: `tests/test_hybrid_outputs.py`

**Interfaces:**
- `html_document(manifest, session_files) -> str` retains its signature.
- HTML markers: `[data-topic-link]`, `[data-topic-section]`, `#trail-sidebar`, `#sidebar-toggle`.

- [ ] **Step 1: Add failing HTML structure tests**

```python
self.assertIn('id="trail-sidebar"', html)
self.assertIn('id="sidebar-toggle"', html)
self.assertIn('data-topic-link="controle"', html)
self.assertIn('data-topic-section="controle"', html)
self.assertIn("new IntersectionObserver", html)
self.assertIn("history.replaceState", html)
self.assertIn("@media (max-width: 800px)", html)
self.assertIn("@media print", html)
```

Parse with an `HTMLParser` subclass, collect every local fragment link and `id`, and assert every fragment has exactly one target. Assert duplicate IDs and active `javascript:` links are absent.

- [ ] **Step 2: Run the test and verify RED**

```bash
python3 -B -m unittest tests.test_hybrid_outputs.HybridOutputTests.test_html_sidebar_links_and_scrollspy -v
```

Expected: FAIL because the current index is inline and has no scrollspy.

- [ ] **Step 3: Implement accessible structure and scrollspy**

Build `navigation_html` and `content_html` first, then render this page shell:

```python
page = f'''<button id="sidebar-toggle" type="button" aria-controls="trail-sidebar" aria-expanded="false">Índice</button>
<aside id="trail-sidebar" aria-label="Índice da apostila"><nav>{navigation_html}</nav></aside>
<main id="trail-content">{content_html}</main>'''
```

Embed this behavior locally:

```javascript
const links = new Map([...document.querySelectorAll('[data-topic-link]')]
  .map(link => [link.dataset.topicLink, link]));
const sections = [...document.querySelectorAll('[data-topic-section]')];
const activate = id => {
  links.forEach((link, key) => {
    const active = key === id;
    link.classList.toggle('is-active', active);
    if (active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  if (id) history.replaceState(null, '', `#topico-${encodeURIComponent(id)}`);
};
const observer = new IntersectionObserver(entries => {
  const visible = entries.filter(entry => entry.isIntersecting)
    .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if (visible) activate(visible.target.dataset.topicSection);
}, {rootMargin: '-20% 0px -65% 0px', threshold: [0, 0.1, 0.5]});
sections.forEach(section => observer.observe(section));
```

Add sticky desktop CSS, mobile drawer behavior, focus-visible styles, textual active state, and print rules hiding navigation controls. Continue routing every content link through `safe_inline`.

- [ ] **Step 4: Run tests and commit**

```bash
python3 -B -m unittest tests.test_hybrid_outputs -v
python3 -B -m unittest discover -s tests -v
git add scripts/build_trilha.py tests/test_hybrid_outputs.py
git commit -m "feat: add scroll-synced HTML study index"
```

---

### Task 5: Generate deterministic, linked PDFs with ReportLab

**Files:**
- Create: `requirements.txt`
- Create: `scripts/trilha_pdf.py`
- Create: `tests/test_pdf_output.py`
- Modify: `scripts/build_trilha.py`

**Interfaces:**
- Produces: `render_pdf(manifest: dict, session_files: dict[str, str]) -> bytes`
- Produces: `PdfDependencyError(RuntimeError)` with a stable installation command.

- [ ] **Step 1: Declare and install dependencies**

Create `requirements.txt`:

```text
reportlab>=4,<5
pypdf>=5,<7
pdfplumber>=0.11,<1
```

Run:

```bash
python3 -m pip install -r requirements.txt
```

- [ ] **Step 2: Write failing PDF tests**

```python
pdf = (self.trail / "apostila/apostila.pdf").read_bytes()
reader = PdfReader(io.BytesIO(pdf))
self.assertGreaterEqual(len(reader.pages), 2)
text = "\n".join(page.extract_text() or "" for page in reader.pages)
self.assertIn("Trilha de Direito Constitucional", text)
self.assertIn("Questão 20", text)
self.assertTrue(any("/Annots" in page for page in reader.pages))
```

Build twice and assert identical bytes. Simulate `ModuleNotFoundError` from the dependency loader and assert the error contains `python3 -m pip install -r requirements.txt` while all prior outputs remain unchanged.

- [ ] **Step 3: Run tests and verify RED**

```bash
python3 -B -m unittest tests.test_pdf_output -v
```

Expected: FAIL because no PDF is generated.

- [ ] **Step 4: Implement lazy loading and PDF rendering**

Create `scripts/trilha_pdf.py`:

```python
class PdfDependencyError(RuntimeError):
    pass


def load_reportlab():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
    except ModuleNotFoundError as exc:
        raise PdfDependencyError(
            "dependência PDF ausente; execute: python3 -m pip install -r requirements.txt"
        ) from exc
    return colors, A4, getSampleStyleSheet, ParagraphStyle, mm, SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
```

Implement `render_pdf` with `io.BytesIO`, `invariant=1`, stable title/author metadata, A4 margins, named anchors, internal/external `Paragraph` links, outline bookmarks, page breaks between modules, colored map callouts, `KeepTogether` around question headings and their first feedback lines, and a page callback for header/footer/page numbers. Escape ReportLab paragraph markup separately from HTML escaping.

- [ ] **Step 5: Add PDF to the single transaction**

Call `render_pdf` before `publish_bundle`, then add its bytes at `Path("apostila/apostila.pdf")`. Do not publish Markdown or HTML until PDF generation succeeds.

- [ ] **Step 6: Run tests and commit**

```bash
python3 -B -m unittest tests.test_pdf_output -v
python3 -B -m unittest discover -s tests -v
git add requirements.txt scripts/build_trilha.py scripts/trilha_pdf.py tests/test_pdf_output.py
git commit -m "feat: generate polished PDF study booklets"
```

---

### Task 6: Update skill discovery, tutoring contract, UI metadata, and README

**Files:**
- Modify: `SKILL.md`
- Modify: `references/trilha-e-apostila.md`
- Modify: `agents/openai.yaml`
- Modify: `README.md`
- Modify: `assets/readme/apostila-preview.png`

**Interfaces:**
- New session: announce features, set `question_target: 20`, present 20 questions, wait, tag feedback topics, build all outputs.
- Resume: run `--check`; on exact `MIGRATION_REQUIRED`, notify and run `--migrate`.

- [ ] **Step 1: Repeat the acceptance scenario before editing**

Run the Task 1 prompt with a fresh subagent against the current branch. Expected: it still omits at least one approved behavior. Store the raw output with baseline evidence.

- [ ] **Step 2: Update the discovery metadata and contract**

Use this frontmatter description:

```yaml
description: Use when a user needs tutoring for Brazilian public-service law exams, including 20-question study sessions, organized study materials, interactive HTML or PDF apostilas, trail progress, mind maps, edital analysis, simulados, corrections, or discursivas.
```

Keep `SKILL.md` concise and route detailed behavior to `references/trilha-e-apostila.md`. The reference must state the 20-question sequence, no-early-correction rule, abandoned-session state, `question_target`, `Tópico`, hybrid tree, migration flow, and three apostila formats.

- [ ] **Step 3: Update UI metadata and README**

Use:

```yaml
interface:
  display_name: "Tutor de Concursos de Direito"
  short_description: "20 questões, trilha organizada e apostila em Markdown, HTML e PDF"
  default_prompt: "Use $concurso-direito-tutor para iniciar uma trilha jurídica com 20 questões por sessão, materiais organizados, progresso e apostila interativa em Markdown, HTML e PDF."
```

README must add a visible “Novidades” section, show 20 questions together, document the hybrid tree and migration, replace the standard-library-only dependency claim, provide the requirements installation command, and explain the scroll-synchronized HTML and PDF.

- [ ] **Step 4: Forward-test GREEN**

Repeat the realistic prompt with only the updated skill available. PASS requires: announces the approved features; presents all 20 before correction; waits without gabarito; describes hybrid paths and three formats; persists `question_target: 20` and topic-tagged feedback. Tighten the positive contract and rerun if any item is absent.

- [ ] **Step 5: Refresh the real HTML screenshot**

Generate a final integrated HTML example, serve it locally, and use Playwright CLI at 1280 px width. Capture a real PNG showing the sidebar, active topic, progress, map, and formatted question headings. Replace only `assets/readme/apostila-preview.png`, inspect it visually, and remove `.playwright-cli`.

- [ ] **Step 6: Validate and commit**

```bash
python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 -B -m unittest discover -s tests -v
git diff --check
git add SKILL.md references/trilha-e-apostila.md agents/openai.yaml README.md assets/readme/apostila-preview.png
git commit -m "docs: present 20-question organized study workflow"
```

---

### Task 7: Run integrated migration, browser, PDF, and release verification

**Files:**
- Modify only Task 1-6 files if an integrated test exposes a gap.
- Create: `.superpowers/sdd/integration-report.md` (execution evidence; do not commit).

**Interfaces:**
- Exercises the public CLI and skill end to end; adds no new interface.

- [ ] **Step 1: Build a realistic legacy fixture**

Create a temporary trail with two modules, three topics, one completed legacy session, root `apostila.md/html`, and one planned session. Snapshot IDs, statuses, weights, manifest data, and session bytes.

- [ ] **Step 2: Verify detection and migration**

```bash
python3 scripts/build_trilha.py --check /tmp/concurso-direito-legacy
python3 scripts/build_trilha.py --migrate /tmp/concurso-direito-legacy
python3 scripts/build_trilha.py --check /tmp/concurso-direito-legacy
```

Expected: first exits 3 with only `MIGRATION_REQUIRED`; migration exits 0; final check exits 0. Compare snapshots and inspect the ZIP.

- [ ] **Step 3: Complete a new targeted session**

Add `question_target: 20`, two topic IDs, 20 sequential feedback blocks, both topic IDs represented, and the aggregate diagnosis. Build twice and compare every generated byte for determinism.

- [ ] **Step 4: Exercise HTML in Playwright**

Serve the HTML, click a topic link and verify its fragment/heading, scroll to another topic and verify `aria-current="location"`, test the toggle at 390 px, require no console errors except optional favicon, and verify every internal target.

- [ ] **Step 5: Inspect PDF text and rendering**

```bash
pdfinfo /tmp/concurso-direito-legacy/apostila/apostila.pdf
pdftotext /tmp/concurso-direito-legacy/apostila/apostila.pdf -
pdftoppm -png -f 1 -l 3 /tmp/concurso-direito-legacy/apostila/apostila.pdf /tmp/concurso-direito-pdf-page
```

Require title metadata, multiple pages, “Questão 20” in text, and visually inspect pages 1-3 plus a question-heavy page for clipping, overlap, glyph defects, headers, footers, numbering, and transitions.

- [ ] **Step 6: Run the complete verification gate**

```bash
python3 -B -m unittest discover -s tests -v
python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
git diff --check
git status --short
```

Additionally compile `scripts/build_trilha.py`, `scripts/trilha_outputs.py`, `scripts/trilha_migration.py`, and `scripts/trilha_pdf.py` by reading each with `Path(path).read_text(encoding="utf-8")` and calling `compile(source, path, "exec")`, so no `__pycache__` is created. Expected: tests, syntax, skill validation, whitespace, and worktree checks all pass.

- [ ] **Step 7: Request whole-branch review**

Generate a review package from the merge base with `main`. Dispatch a read-only reviewer against the design and plan. Fix every Critical or Important finding with a failing regression first, and repeat until the reviewer returns ready to merge.

- [ ] **Step 8: Commit integration-only fixes if needed**

```bash
git add scripts tests SKILL.md references agents README.md assets/readme/apostila-preview.png requirements.txt
git commit -m "fix: close integrated study output gaps"
```

If the index is clean, record that no integration commit was needed.

---

## Release handoff

After every task has a clean review and final verification is fresh, use `superpowers:finishing-a-development-branch`. Offer merge/PR choices, merge only after user selection, rerun the suite on integrated `main`, and push the verified commit to `jocielle-tech/concurso-direito-tutor` when authorized.
