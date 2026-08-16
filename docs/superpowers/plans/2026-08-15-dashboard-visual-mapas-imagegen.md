# Dashboard Visual and Native Algorithmic Mind Maps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the generated HTML and PDF into a consistent modern dashboard and add one cached, native-imagegen algorithmic mind map per completed topic, with deterministic accessible fallbacks.

**Architecture:** A new standard-library visual-map module aggregates validated textual maps, computes content-addressed paths, prepares native `imagegen` prompts, and validates persisted PNGs. The Python build never calls a model: it consumes cached image bytes or renders deterministic HTML/ReportLab fallbacks, preserving reproducibility and transactional publishing. Skill instructions invoke native `imagegen` only when a completed topic lacks a valid current image.

**Tech Stack:** Python 3 standard library, ReportLab 4.x, pypdf, pdfplumber, self-contained HTML/CSS/JavaScript, Codex built-in `imagegen`, Playwright, Poppler.

## Global Constraints

- Generate at most one current PNG per completed topic content hash.
- Use native `imagegen`; never request `OPENAI_API_KEY`, an image API, a CDN, or an external image service.
- Target a horizontal 3:2 composition designed for a 1536 × 1024 canvas; accept only validated landscape PNGs with a near-3:2 ratio.
- Keep the textual map as the authoritative, searchable, accessible legal source.
- Do not generate images for quick questions, incomplete sessions, or incomplete topics.
- The build must never call a model, access the network, rename canonical sources, or delete stale cached images.
- The same manifest, sessions, and cached image bytes must generate byte-identical Markdown, HTML, and PDF.
- HTML remains self-contained, navigable without JavaScript, printable, keyboard accessible, and free of remote assets.
- Missing, invalid, or rejected images use a deterministic algorithmic fallback and do not block session closure.
- Existing schema-v1 trails, hierarchical maps, 20-question behavior, migration, rollback, and canonical paths remain compatible.
- The approved visual identity is Dashboard Moderno: violet/blue accents, subtle gradients, cards, strong study hierarchy, and restrained motion.

---

### Task 1: Add the deterministic visual-map model, cache contract, and preparation CLI

**Files:**
- Create: `scripts/trilha_visual_maps.py`
- Create: `scripts/prepare_visual_map.py`
- Create: `tests/test_visual_maps.py`
- Modify: `tests/trilha_support.py`

**Interfaces:**
- Produces: `VisualMapSpec(topic_id: str, source_hash: str, expected_path: Path, prompt: str, alt_text: str, algorithm_lines: tuple[str, ...])`
- Produces: `VisualMapAsset(spec: VisualMapSpec, status: Literal["ready", "missing", "invalid"], png_bytes: bytes | None, error: str | None)`
- Produces: `build_visual_map_specs(manifest: dict, session_files: dict[str, str]) -> dict[str, VisualMapSpec]`
- Produces: `load_visual_map_assets(trail: Path, specs: dict[str, VisualMapSpec]) -> dict[str, VisualMapAsset]`
- Produces CLI: `python3 scripts/prepare_visual_map.py TRAIL --topic TOPIC_ID`

- [ ] **Step 1: Add a reusable, valid landscape PNG fixture without Pillow**

Add to `tests/trilha_support.py`:

```python
import struct
import zlib


def png_bytes(width=1536, height=1024, rgb=(99, 91, 255)):
    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    row = b"\x00" + bytes(rgb) * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, level=9))
        + chunk(b"IEND", b"")
    )
```

- [ ] **Step 2: Write failing aggregation, cache, validation, and CLI tests**

Create `tests/test_visual_maps.py` with focused cases:

```python
class VisualMapTests(unittest.TestCase):
    def test_completed_topic_spec_aggregates_sessions_in_manifest_order(self):
        specs = build_visual_map_specs(self.manifest, self.session_files)
        spec = specs["controle"]
        self.assertEqual(spec.topic_id, "controle")
        self.assertIn("ENTRADA: existe caso concreto?", spec.algorithm_lines)
        self.assertIn('Use case: infographic-diagram', spec.prompt)
        self.assertIn('Text (verbatim):', spec.prompt)
        self.assertRegex(spec.expected_path.as_posix(), r"^assets/mapas/controle-[0-9a-f]{8}/[0-9a-f]{64}\.png$")

    def test_incomplete_topic_has_no_visual_map_spec(self):
        self.manifest["modules"][0]["topics"][0]["status"] = "in_progress"
        self.assertEqual(build_visual_map_specs(self.manifest, self.session_files), {})

    def test_hash_changes_only_when_visual_source_or_template_changes(self):
        first = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        renamed = copy.deepcopy(self.manifest)
        renamed["modules"][0]["title"] = "Título novo"
        renamed["modules"][0]["topics"][0]["title"] = "Tópico novo"
        same = build_visual_map_specs(renamed, self.session_files)["controle"]
        self.assertEqual(first.source_hash, same.source_hash)
        changed_files = dict(self.session_files)
        changed_files["s001"] = changed_files["s001"].replace("SE SIM", "SE PRESENTE")
        changed = build_visual_map_specs(self.manifest, changed_files)["controle"]
        self.assertNotEqual(first.source_hash, changed.source_hash)

    def test_asset_loader_reports_ready_missing_and_invalid(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        assets = load_visual_map_assets(self.trail, {"controle": spec})
        self.assertEqual(assets["controle"].status, "missing")
        target = self.trail / spec.expected_path
        target.parent.mkdir(parents=True)
        target.write_bytes(png_bytes())
        self.assertEqual(load_visual_map_assets(self.trail, {"controle": spec})["controle"].status, "ready")
        target.write_bytes(png_bytes(1024, 1024))
        invalid = load_visual_map_assets(self.trail, {"controle": spec})["controle"]
        self.assertEqual(invalid.status, "invalid")
        self.assertIn("proporção", invalid.error)

    def test_cli_emits_machine_readable_native_image_request_without_writes(self):
        before = snapshot_tree(self.trail)
        result = subprocess.run(
            ["python3", str(PREPARE), str(self.trail), "--topic", "controle"],
            text=True, capture_output=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "missing")
        self.assertEqual(payload["generator"], "imagegen-built-in")
        self.assertNotIn("OPENAI_API_KEY", result.stdout)
        self.assertEqual(snapshot_tree(self.trail), before)
```

Also cover invalid PNG signature, truncated IHDR, portrait ratio, path containment, unknown topic, legacy hierarchical map acceptance, and two completed sessions linked to the same topic.

- [ ] **Step 3: Run the new suite and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_visual_maps -v
```

Expected: import failure because `scripts.trilha_visual_maps` and `scripts.prepare_visual_map` do not exist.

- [ ] **Step 4: Implement the model and content-addressed paths**

Create `scripts/trilha_visual_maps.py` with these public definitions:

```python
from __future__ import annotations

import hashlib
import json
import re
import struct
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


VISUAL_TEMPLATE_VERSION = "dashboard-modern-v1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class VisualMapSpec:
    topic_id: str
    source_hash: str
    expected_path: Path
    prompt: str
    alt_text: str
    algorithm_lines: tuple[str, ...]


@dataclass(frozen=True)
class VisualMapAsset:
    spec: VisualMapSpec
    status: Literal["ready", "missing", "invalid"]
    png_bytes: bytes | None
    error: str | None


def _sections(text):
    headings = list(SECTION.finditer(text))
    return {
        heading.group(1): text[
            heading.end(): headings[index + 1].start() if index + 1 < len(headings) else len(text)
        ].strip()
        for index, heading in enumerate(headings)
    }


def _safe_segment(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "topico"
    return f"{slug}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"


def _algorithm_source(manifest, session_files, topic_id):
    blocks = []
    for session in manifest["sessions"]:
        if session["status"] == "completed" and topic_id in session["topic_ids"]:
            mind_map = _sections(session_files[session["id"]]).get("Mapa mental", "").strip()
            if mind_map:
                blocks.append(mind_map)
    return "\n\n".join(blocks)


def build_visual_map_specs(manifest, session_files):
    specs = {}
    for module in manifest["modules"]:
        for topic in module["topics"]:
            if topic["status"] != "completed":
                continue
            source = _algorithm_source(manifest, session_files, topic["id"])
            if not source:
                continue
            normalized = "\n".join(line.rstrip() for line in source.splitlines()).strip()
            digest_input = json.dumps(
                {
                    "topic_id": topic["id"],
                    "template": VISUAL_TEMPLATE_VERSION,
                    "ratio": "3:2",
                    "source": normalized,
                },
                ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            ).encode("utf-8")
            source_hash = hashlib.sha256(digest_input).hexdigest()
            expected = Path("assets/mapas") / _safe_segment(topic["id"]) / f"{source_hash}.png"
            lines = tuple(line.strip() for line in normalized.splitlines() if line.strip())
            specs[topic["id"]] = VisualMapSpec(
                topic_id=topic["id"], source_hash=source_hash, expected_path=expected,
                prompt=_visual_prompt(topic["title"], lines),
                alt_text=f"Fluxograma algorítmico do tópico {topic['title']}. " + " ".join(lines),
                algorithm_lines=lines,
            )
    return specs
```

Implement `_visual_prompt`, `_png_dimensions`, `_contained_path`, and `load_visual_map_assets`. Accept only a valid PNG whose width and height are at least 640 px, width is greater than height, and ratio is between 1.4 and 1.6. Never decode or rewrite the image.

- [ ] **Step 5: Implement the read-only preparation CLI**

Create `scripts/prepare_visual_map.py`:

```python
#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

try:
    from scripts.build_trilha import ValidationError, load_and_validate
    from scripts.trilha_visual_maps import build_visual_map_specs, load_visual_map_assets
except ModuleNotFoundError:
    from build_trilha import ValidationError, load_and_validate
    from trilha_visual_maps import build_visual_map_specs, load_visual_map_assets


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("trail", type=Path)
    parser.add_argument("--topic", required=True)
    args = parser.parse_args(argv)
    try:
        manifest, session_files = load_and_validate(args.trail.resolve())
        specs = build_visual_map_specs(manifest, session_files)
        if args.topic not in specs:
            raise ValidationError("tópico não concluído ou sem mapa mental")
        spec = specs[args.topic]
        asset = load_visual_map_assets(args.trail.resolve(), {args.topic: spec})[args.topic]
        print(json.dumps({
            "generator": "imagegen-built-in",
            "topic_id": spec.topic_id,
            "source_hash": spec.source_hash,
            "expected_path": spec.expected_path.as_posix(),
            "prompt": spec.prompt,
            "alt_text": spec.alt_text,
            "status": asset.status,
            "error": asset.error,
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run focused and full tests**

Run:

```bash
python3 -B -m unittest tests.test_visual_maps -v
python3 -B -m unittest discover -s tests -v
git diff --check
```

Expected: all tests pass; no whitespace errors.

- [ ] **Step 7: Commit**

```bash
git add scripts/trilha_visual_maps.py scripts/prepare_visual_map.py tests/test_visual_maps.py tests/trilha_support.py
git commit -m "feat: prepare cached native visual maps"
```

---

### Task 2: Build the self-contained Dashboard Moderno HTML renderer

**Files:**
- Create: `scripts/trilha_html.py`
- Modify: `scripts/build_trilha.py`
- Modify: `tests/test_hybrid_outputs.py`
- Create: `tests/test_html_dashboard.py`

**Interfaces:**
- Consumes: `dict[str, VisualMapAsset]` from Task 1.
- Produces: `render_html(manifest: dict, session_files: dict[str, str], visual_maps: dict[str, VisualMapAsset]) -> str`
- Preserves wrapper: `html_document(manifest, session_files, visual_maps=None) -> str`
- HTML markers: `#dashboard-hero`, `[data-metric]`, `.study-card`, `.question-card`, `[data-visual-map]`, `#map-dialog`, `[data-map-open]`.

- [ ] **Step 1: Write failing dashboard, embedded-image, fallback, and accessibility tests**

Create `tests/test_html_dashboard.py`:

```python
class HtmlDashboardTests(unittest.TestCase):
    def test_ready_visual_map_is_embedded_in_self_contained_dashboard(self):
        manifest, session_files, assets = self.ready_visual_fixture()
        html = render_html(manifest, session_files, assets)
        for marker in (
            'id="dashboard-hero"', 'data-metric="global-progress"',
            'class="study-card', 'class="question-card',
            'data-visual-map="controle"', 'id="map-dialog"',
            'aria-modal="true"', 'data-map-open="controle"',
        ):
            self.assertIn(marker, html)
        self.assertRegex(html, r'src="data:image/png;base64,[A-Za-z0-9+/=]+"')
        self.assertNotIn("https://fonts.", html)
        self.assertNotIn("<script src=", html)

    def test_missing_or_invalid_image_uses_algorithmic_html_fallback(self):
        manifest, session_files, assets = self.missing_visual_fixture()
        html = render_html(manifest, session_files, assets)
        self.assertIn('class="algorithm-flow"', html)
        self.assertIn('class="algorithm-node algorithm-decision"', html)
        self.assertIn("ENTRADA", html)
        self.assertNotIn("data:image/png;base64", html)

    def test_dialog_and_sidebar_are_keyboard_accessible_with_no_js_fallback(self):
        html = self.build_html()
        self.assertIn("dialog.showModal()", html)
        self.assertIn("dialog.close()", html)
        self.assertIn("event.key === 'Escape'", html)
        self.assertIn("prefers-reduced-motion: reduce", html)
        self.assertIn(".no-js-map-link", html)
        self.assertIn("@media print", html)
```

Extend the existing fragment parser assertions so every dashboard/local/modal control target is unique. Add a viewport-independent assertion for WCAG-AA palette pairs using a small contrast-ratio helper in the test.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_html_dashboard -v
```

Expected: FAIL because the current renderer has no dashboard hero, metrics, visual-map image, or dialog.

- [ ] **Step 3: Extract the renderer behind a compatibility wrapper**

Create `scripts/trilha_html.py` and change `scripts/build_trilha.py`:

```python
def html_document(manifest, session_files, visual_maps=None):
    return render_html(manifest, session_files, visual_maps or {})
```

Move rendering-only helpers (`safe_inline`, `html_map`, `html_session`, navigation shell) into `trilha_html.py`. Keep validation and Markdown generation in `build_trilha.py`. Preserve all existing IDs, data attributes, fragment encoding, scrollspy behavior, safe-link filtering, mobile no-JS navigation, and print rules.

- [ ] **Step 4: Implement dashboard data and self-contained image embedding**

In `scripts/trilha_html.py`, add:

```python
import base64
import html


PALETTE = {
    "ink": "#101828", "muted": "#475467", "surface": "#FFFFFF",
    "canvas": "#F4F7FB", "violet": "#635BFF", "blue": "#0284C7",
    "success": "#15803D", "warning": "#B45309", "danger": "#B42318",
}


def _data_uri(png_bytes):
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _visual_map_html(topic, asset):
    if asset and asset.status == "ready":
        source = _data_uri(asset.png_bytes)
        escaped_alt = html.escape(asset.spec.alt_text, quote=True)
        return (
            f'<figure class="visual-map-card" data-visual-map="{html.escape(topic["id"], quote=True)}">'
            f'<button type="button" class="map-open" data-map-open="{html.escape(topic["id"], quote=True)}" '
            f'aria-haspopup="dialog"><img src="{source}" alt="{escaped_alt}" loading="lazy"></button>'
            f'<figcaption>Mapa algorítmico — clique para ampliar</figcaption></figure>'
        )
    return _algorithm_fallback(topic, asset.spec.algorithm_lines if asset else ())
```

Create metric cards for global progress, completed sessions, completed topics, and next review. Render content sections as `.study-card`; render each `### Questão N` block as `.question-card` with topic/result chips parsed from validated fields.

- [ ] **Step 5: Implement the Dashboard Moderno CSS and modal controller**

Use only inline CSS/JS. Define CSS variables, violet/blue hero gradient, rounded cards, subtle shadows, responsive grid, visible focus, print flattening, and reduced-motion override. Add one shared dialog at the end of the document:

```html
<dialog id="map-dialog" aria-modal="true" aria-labelledby="map-dialog-title">
  <div class="dialog-toolbar">
    <h2 id="map-dialog-title">Mapa algorítmico</h2>
    <button type="button" data-map-close aria-label="Fechar mapa">×</button>
  </div>
  <img id="map-dialog-image" alt="">
</dialog>
```

The controller copies the selected data URI and alt text, calls `showModal()`, closes on the close button/backdrop/Escape, and returns focus to the opener. With JavaScript disabled, the full inline figure and textual algorithm remain visible.

- [ ] **Step 6: Run focused and regression suites**

Run:

```bash
python3 -B -m unittest tests.test_html_dashboard tests.test_hybrid_outputs tests.test_build_trilha -v
python3 -B -m unittest discover -s tests -v
git diff --check
```

Expected: dashboard tests and every existing HTML/validation test pass.

- [ ] **Step 7: Commit**

```bash
git add scripts/trilha_html.py scripts/build_trilha.py tests/test_html_dashboard.py tests/test_hybrid_outputs.py
git commit -m "feat: render modern self-contained study dashboard"
```

---

### Task 3: Redesign the deterministic PDF and embed visual maps

**Files:**
- Modify: `scripts/trilha_pdf.py`
- Modify: `tests/test_pdf_output.py`

**Interfaces:**
- Consumes: `dict[str, VisualMapAsset]` from Task 1.
- Changes: `render_pdf(manifest: dict, session_files: dict[str, str], visual_maps: dict[str, VisualMapAsset] | None = None) -> bytes`
- Preserves: lazy ReportLab loading, invariant canvas, internal/external links, outline hierarchy, and searchable textual maps.

- [ ] **Step 1: Add failing PDF image, fallback, visual hierarchy, and determinism tests**

Extend `tests/test_pdf_output.py`:

```python
def test_pdf_embeds_ready_visual_map_and_keeps_textual_algorithm(self):
    manifest, session_files, assets = self.ready_visual_fixture()
    pdf = render_pdf(manifest, session_files, assets)
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    image_xobjects = [
        obj
        for page in reader.pages
        for obj in (page.get("/Resources", {}).get("/XObject", {}) or {}).values()
        if obj.get_object().get("/Subtype") == "/Image"
    ]
    self.assertTrue(image_xobjects)
    self.assertIn("ENTRADA: existe caso concreto?", text)
    self.assertIn("Progresso global", text)

def test_pdf_missing_visual_map_uses_searchable_fallback(self):
    manifest, session_files, assets = self.missing_visual_fixture()
    text = pdf_text(render_pdf(manifest, session_files, assets))
    self.assertIn("Mapa algorítmico", text)
    self.assertIn("SE SIM", text)

def test_visual_pdf_is_byte_identical_across_two_builds(self):
    manifest, session_files, assets = self.ready_visual_fixture()
    first = render_pdf(manifest, session_files, assets)
    second = render_pdf(manifest, session_files, assets)
    self.assertEqual(second, first)
```

Also assert title metadata, page numbers, bookmarks, annotations, and that a question heading remains with its first two lines.

- [ ] **Step 2: Run the focused suite and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_pdf_output -v
```

Expected: FAIL because `render_pdf` neither accepts visual assets nor embeds images/dashboard metrics.

- [ ] **Step 3: Extend lazy ReportLab imports for modern components**

Update `load_reportlab()` to lazily import and return `Image`, `Table`, `TableStyle`, and `HRFlowable`. Keep the stable dependency error unchanged.

- [ ] **Step 4: Add reusable PDF components**

Implement focused helpers:

```python
def _metric_table(metrics, Table, TableStyle, Paragraph, styles, colors):
    cells = [
        Paragraph(f"<b>{_paragraph_markup(value)}</b><br/>{_paragraph_markup(label)}", styles["MetricLabel"])
        for label, value in metrics
    ]
    table = Table([cells], colWidths=[46 * mm] * len(cells))
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0EFFF")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7C4FF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9D7FF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def _map_flowables(topic, asset, Image, Paragraph, KeepTogether, styles, max_width):
    flowables = [Paragraph("Mapa algorítmico", styles["SectionLabel"])]
    if asset and asset.status == "ready":
        image = Image(io.BytesIO(asset.png_bytes))
        image._restrictSize(max_width, 108 * mm)
        flowables.append(image)
    else:
        flowables.extend(_algorithm_fallback_flowables(asset, Paragraph, styles))
    if asset:
        flowables.extend(Paragraph(_paragraph_markup(line), styles["AlgorithmText"])
                         for line in asset.spec.algorithm_lines)
    return flowables
```

Do not use private image dimensions to crop; scale proportionally with `_restrictSize`.

- [ ] **Step 5: Apply the Dashboard Moderno PDF system**

Add styles for cover, eyebrow, metric label/value, module, topic, section label, question, feedback, and algorithm text. In the page callback, draw a restrained violet/blue header rule and footer page chip. The cover uses vector rectangles/gradients approximated with deterministic solid bands, not raster or remote fonts.

For each topic, emit its visual map once before canonical session details. Keep map text after the image. Render legal category callouts with the existing semantic colors and question feedback in lightly tinted tables/cards.

- [ ] **Step 6: Run focused, full, and render checks**

Run:

```bash
python3 -B -m unittest tests.test_pdf_output -v
python3 -B -m unittest discover -s tests -v
git diff --check
```

Render a representative PDF with `pdftoppm`, inspect the cover, a map page, and a question-heavy page for cropping, overlap, glyph defects, and bad page breaks.

- [ ] **Step 7: Commit**

```bash
git add scripts/trilha_pdf.py tests/test_pdf_output.py
git commit -m "feat: style PDF dashboard and visual maps"
```

---

### Task 4: Wire cached assets into the transactional build

**Files:**
- Modify: `scripts/build_trilha.py`
- Modify: `scripts/trilha_outputs.py`
- Modify: `tests/test_visual_maps.py`
- Modify: `tests/test_hybrid_outputs.py`

**Interfaces:**
- Consumes Task 1: `build_visual_map_specs`, `load_visual_map_assets`.
- Consumes Task 2: `render_html(..., visual_maps)`.
- Consumes Task 3: `render_pdf(..., visual_maps)`.
- Preserves CLI: `build_trilha.py [--check | --migrate] TRAIL`.

- [ ] **Step 1: Write failing integrated cache/fallback/transaction tests**

Add tests that assert:

```python
def test_build_reuses_cached_map_without_modifying_source_asset(self):
    expected = self.write_ready_visual_map()
    before = expected.read_bytes()
    first = self.run_build()
    first_outputs = generated_snapshot(self.trail)
    second = self.run_build()
    self.assertEqual((first.returncode, second.returncode), (0, 0))
    self.assertEqual(expected.read_bytes(), before)
    self.assertEqual(generated_snapshot(self.trail), first_outputs)

def test_invalid_map_falls_back_without_partial_publication(self):
    target = self.write_invalid_visual_map()
    sentinel = self.seed_generated_outputs()
    result = self.run_build()
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(target.read_bytes(), b"invalid-png")
    self.assert_fallback_present_in_html_and_pdf()
    self.assert_all_outputs_replaced_as_one_valid_bundle(sentinel)

def test_check_never_creates_or_modifies_visual_assets(self):
    before = snapshot_tree(self.trail)
    result = self.run_build("--check")
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(snapshot_tree(self.trail), before)
```

Also cover a stale old-hash image remaining untouched while the current hash reports `missing` and uses fallback.

- [ ] **Step 2: Run integrated tests and verify RED**

Run:

```bash
python3 -B -m unittest tests.test_visual_maps tests.test_hybrid_outputs -v
```

Expected: FAIL because `build_trail` does not load or pass visual assets.

- [ ] **Step 3: Wire a single validated visual-map snapshot into both renderers**

Update `build_trail`:

```python
def build_trail(trail):
    manifest, session_files = load_and_validate(trail)
    specs = build_visual_map_specs(manifest, session_files)
    visual_maps = load_visual_map_assets(trail, specs)
    markdown = markdown_document(manifest, session_files)
    html = html_document(manifest, session_files, visual_maps)
    pdf = render_pdf(manifest, session_files, visual_maps)
    outputs = build_output_bundle(trail, manifest, session_files, markdown, html, pdf)
    publish_bundle(trail, outputs)
```

Perform all validation and byte rendering before `publish_bundle`. Do not include source images in the generated output bundle and never delete assets not referenced by the current hash.

- [ ] **Step 4: Keep `--check` read-only while validating current assets**

`--check` must validate manifest/session structure and inspect any current cached PNG, but it must not create directories, rewrite PNGs, render PDF, or publish outputs. Invalid/missing images are non-fatal because fallback is defined.

- [ ] **Step 5: Run regression and determinism gates**

Run:

```bash
python3 -B -m unittest tests.test_visual_maps tests.test_hybrid_outputs tests.test_migration tests.test_pdf_output -v
python3 -B -m unittest discover -s tests -v
git diff --check
```

Expected: all tests pass; two builds with the same sources and PNG bytes produce byte-identical outputs.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_trilha.py scripts/trilha_outputs.py tests/test_visual_maps.py tests/test_hybrid_outputs.py
git commit -m "feat: integrate visual map cache into study builds"
```

---

### Task 5: Teach and forward-test the native imagegen workflow

**Files:**
- Modify: `SKILL.md`
- Modify: `references/trilha-e-apostila.md`
- Modify: `agents/openai.yaml`
- Modify: `README.md`
- Create: `assets/readme/mapa-algoritmico-preview.png`
- Modify: `assets/readme/apostila-preview.png`

**Interfaces:**
- Consumes CLI from Task 1 to obtain prompt and `expected_path`.
- Skill behavior: call required native sub-skill `imagegen`, inspect output, persist selected PNG, and rebuild.
- Fallback behavior: do not request CLI/API/key; build deterministic visual and mark native image as pending.

- [ ] **Step 1: Run a fresh-agent RED baseline before editing the skill**

Use a fresh-context agent with the current skill and this realistic prompt:

```text
Use $concurso-direito-tutor para concluir um tópico de controle de constitucionalidade com 20 respostas já recebidas. Gere todos os materiais finais, inclusive o novo mapa visual, e explique qualquer dependência necessária.
```

Score literal behavior. RED requires at least one current failure: no native `imagegen` call, no content-hash cache, no `assets/mapas/` path, no validation/retry/fallback contract, or request for an external dependency. Save raw evidence under `.superpowers/sdd/baseline-native-map.md`; do not commit it.

- [ ] **Step 2: Update the concise skill contract**

In `SKILL.md`, add only the opening/closing behavior and route details to the reference. Use an explicit conditional:

```markdown
Ao fechar um tópico `completed`, ler a especificação visual preparada pelo utilitário. Se o status for `missing` ou `invalid`, usar obrigatoriamente a sub-skill nativa `imagegen`; não solicitar API key, CLI ou serviço externo. Inspecionar o resultado, salvar no `expected_path` e reconstruir as apostilas. Se a geração nativa não estiver disponível ou falhar após uma correção, concluir com o fallback determinístico.
```

Expand the frontmatter trigger description to include native algorithmic visual maps without summarizing the workflow.

- [ ] **Step 3: Document the exact native workflow in the reference**

Add to `references/trilha-e-apostila.md`:

```markdown
## Mapa algorítmico nativo

Para cada tópico recém-concluído:

1. Executar `python3 <skill-dir>/scripts/prepare_visual_map.py <trail_dir> --topic <topic_id>`.
2. Se `status` for `ready`, reutilizar e não chamar geração.
3. Se `status` for `missing` ou `invalid`, usar **REQUIRED SUB-SKILL: imagegen** em modo nativo com o `prompt` retornado.
4. Inspecionar a imagem contra `algorithm_lines` e `alt_text`. Repetir uma vez somente para corrigir erro concreto.
5. Copiar o PNG aprovado para `expected_path`; nunca deixar asset referenciado apenas no diretório global de imagens geradas.
6. Não usar fallback CLI, não solicitar `OPENAI_API_KEY` e não chamar serviço externo.
7. Se a ferramenta nativa estiver indisponível ou a segunda imagem continuar incorreta, não salvar a imagem e executar o build com fallback determinístico.
```

Document algorithm markers, cache behavior, source authority, image path, HTML Base64 embedding, PDF behavior, and incomplete-session exclusion.

- [ ] **Step 4: Update UI metadata and README**

Set:

```yaml
interface:
  display_name: "Tutor de Concursos de Direito"
  short_description: "20 questões, mapas visuais nativos e apostilas HTML/PDF"
  default_prompt: "Use $concurso-direito-tutor para criar uma trilha jurídica com 20 questões, mapas algorítmicos gerados nativamente, progresso e apostilas modernas em Markdown, HTML e PDF."
```

README must add a visible section explaining that native image generation requires no API key, show the cache/fallback flow, add `assets/mapas/` to the tree, describe the modern HTML/PDF system, and retain installation instructions for ReportLab PDF dependencies.

- [ ] **Step 5: Generate and validate a real native example image**

Use the Task 1 CLI prompt for a completed example topic, then call the built-in `imagegen` tool with taxonomy `infographic-diagram`. Inspect the returned image visually. If correct, copy it into `assets/readme/mapa-algoritmico-preview.png`; if incorrect, make one targeted retry. Record the final prompt and built-in mode in the task report.

Do not use the CLI fallback or request an API key.

- [ ] **Step 6: Forward-test GREEN with fresh context**

Repeat the baseline prompt with only the updated skill/reference available. PASS requires the fresh agent to:

- invoke native `imagegen` for a missing completed-topic map;
- use the preparation CLI and expected path;
- avoid API key/external dependency requests;
- inspect and allow one targeted retry;
- reuse `ready` cache without generation;
- use deterministic fallback when native generation is unavailable;
- avoid generating for incomplete topics.

Tighten the positive recipe and rerun from fresh context if any requirement is omitted.

- [ ] **Step 7: Refresh the real Dashboard Moderno screenshot**

Build a two-topic example with a valid cached native PNG, serve `apostila/apostila.html`, and capture `assets/readme/apostila-preview.png` at 1280 px using Playwright. The screenshot must visibly show hero metrics, sidebar active state, progress, visual-map card, and question cards. Inspect it before committing.

- [ ] **Step 8: Validate and commit**

Run:

```bash
python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 -B -m unittest discover -s tests -v
git diff --check
```

Then commit:

```bash
git add SKILL.md references/trilha-e-apostila.md agents/openai.yaml README.md assets/readme/mapa-algoritmico-preview.png assets/readme/apostila-preview.png
git commit -m "docs: teach native visual study maps"
```

---

### Task 6: Run integrated browser, PDF, cache, fallback, and release verification

**Files:**
- Create: `.superpowers/sdd/native-map-integration-report.md` (execution evidence; do not commit)
- Modify Task 1–5 files only if a regression-first integrated fix is necessary.

**Interfaces:**
- Exercises public skill instructions, preparation CLI, build CLI, HTML, PDF, and cached source image.
- Adds no new production interface.

- [ ] **Step 1: Create realistic ready/missing/invalid fixtures**

Create temporary trails with two modules, three topics, one completed 20-question multi-topic session, one incomplete session, algorithmic maps, and:

- a valid current PNG;
- no PNG;
- an invalid square PNG;
- a stale previous-hash PNG.

Snapshot manifests, canonical sessions, cached image bytes, and generated outputs.

- [ ] **Step 2: Verify preparation and cache semantics**

Run the preparation CLI for each topic. Require exact machine-readable states, stable hashes, no writes, no generation for the incomplete topic, and no modification/deletion of stale assets.

- [ ] **Step 3: Verify build determinism and transaction behavior**

Build every fixture twice. Require byte-identical generated outputs per fixture, source images unchanged, valid image embedded in both formats, and missing/invalid/stale cases rendered via fallback. Inject a publish failure and confirm all prior derivatives are restored.

- [ ] **Step 4: Exercise HTML in Playwright**

At 1280 px and 390 px:

- navigate by sidebar and scrollspy;
- inspect hero metrics and active topic;
- open/close the map dialog by mouse and keyboard;
- verify Escape, focus return, alt text, no broken fragments, and no console errors except optional favicon;
- disable JavaScript and confirm sidebar, map, text, and content remain accessible;
- emulate reduced motion and confirm animation suppression;
- inspect print preview structure.

- [ ] **Step 5: Inspect PDF text, links, images, and rendered pages**

Use `pdfinfo`, `pdftotext`, `pypdf`, and `pdftoppm`. Require title metadata, multiple pages, image XObject in the ready fixture, searchable algorithm text in every fixture, Questão 20, internal/external annotations, and bookmarks. Visually inspect cover, index, map, fallback, and question-heavy pages.

- [ ] **Step 6: Run the complete verification gate**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 python3 /Users/testes/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
python3 -B - <<'PY'
from pathlib import Path
for path in (
    "scripts/build_trilha.py", "scripts/trilha_outputs.py", "scripts/trilha_migration.py",
    "scripts/trilha_pdf.py", "scripts/trilha_html.py", "scripts/trilha_visual_maps.py",
    "scripts/prepare_visual_map.py",
):
    compile(Path(path).read_text(encoding="utf-8"), path, "exec")
print("syntax: 7 files OK")
PY
git diff --check
git status --short
```

Expected: all tests, validation, syntax, whitespace, and worktree checks pass. Only explicitly documented `.superpowers/sdd` reports may remain uncommitted.

- [ ] **Step 7: Request a whole-branch review**

Generate a review package from the merge base with `main`. Dispatch a read-only reviewer against the approved design and this plan. Fix every Critical or Important finding with a failing regression first; repeat until the reviewer returns `READY TO MERGE`.

- [ ] **Step 8: Commit integration-only fixes if needed**

Stage only named production/test/documentation files and commit:

```bash
git commit -m "fix: close native visual map integration gaps"
```

If no integrated fix is needed, record that fact only in the uncommitted report.

---

## Release handoff

After every task has a clean review and the final verification is fresh, use `superpowers:finishing-a-development-branch`. Merge or create a PR only after the user's selection, rerun the complete suite on the integrated branch, and publish the verified result to `jocielle-tech/concurso-direito-tutor` when authorized.
