import io
import json
import re
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from importlib.util import find_spec
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

import scripts.build_trilha as build_trilha
from scripts.build_trilha import load_and_validate
from scripts.trilha_visual_maps import build_visual_map_specs, load_visual_map_assets
from tests.trilha_support import png_bytes

from tests.test_build_trilha import valid_session


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_trilha.py"
GENERATED_NOTICE = "<!-- GERADO AUTOMATICAMENTE. NÃO EDITE. -->\n\n"


class FragmentLinkParser(HTMLParser):
    """Collect IDs and in-document links from generated HTML."""

    def __init__(self):
        super().__init__()
        self.fragment_links = []
        self.ids = []
        self.javascript_links = []

    def handle_starttag(self, _tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.append(attributes["id"])
        href = attributes.get("href")
        if href and href.startswith("#"):
            self.fragment_links.append(href[1:])
        if href and href.lower().startswith("javascript:"):
            self.javascript_links.append(href)


class HybridOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trail = Path(self.tmp.name) / "trilha"
        self.trail.mkdir()
        self.write_trail()

    def tearDown(self):
        self.tmp.cleanup()

    def write_trail(self):
        manifest = {
            "schema_version": 1,
            "title": "Trilha de Direito Constitucional",
            "slug": "direito-constitucional",
            "source": "provisional",
            "exam": None,
            "banca": None,
            "recalibrated": False,
            "modules": [{
                "id": "constitucional",
                "title": "Direito Constitucional",
                "topics": [{
                    "id": "controle",
                    "title": "Controle difuso",
                    "weight": 1,
                    "status": "completed",
                    "sessions": ["s001"],
                }],
            }],
            "sessions": [{
                "id": "s001",
                "title": "Controle difuso",
                "date": "2026-08-10",
                "status": "completed",
                "module_id": "constitucional",
                "topic_ids": ["controle"],
                "file": "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md",
            }],
        }
        (self.trail / "trilha.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        session_path = self.trail / "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(
            valid_session("Controle difuso"), encoding="utf-8"
        )

    def run_build(self):
        return subprocess.run(
            ["python3", str(SCRIPT), str(self.trail)], text=True, capture_output=True
        )

    def tree_snapshot(self):
        return {
            path.relative_to(self.trail).as_posix(): (
                "directory" if path.is_dir() else path.read_bytes()
            )
            for path in self.trail.rglob("*")
        }

    def visual_map_target(self):
        manifest, session_files = load_and_validate(self.trail)
        spec = build_visual_map_specs(manifest, session_files)["controle"]
        return self.trail / spec.expected_path

    def generated_snapshot(self):
        generated_roots = {"apostila", "painel", "materiais", "revisoes"}
        return {
            path.relative_to(self.trail).as_posix(): path.read_bytes()
            for path in self.trail.rglob("*")
            if path.is_file()
            and (
                path.relative_to(self.trail).parts[0] in generated_roots
                or path.name in {"resumo.md", "mapa-mental.md", "questoes.md"}
            )
        }

    def seed_generated_outputs(self):
        sentinel = b"sentinel-derived-output"
        for relative in (
            "apostila/apostila.md", "apostila/apostila.html", "apostila/apostila.pdf",
            "painel/indice.md", "materiais/mapas-mentais.md", "revisoes/agenda.md",
        ):
            target = self.trail / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(sentinel)
        return sentinel

    def assert_html_and_pdf_fallback(self):
        document = (self.trail / "apostila/apostila.html").read_text(encoding="utf-8")
        pdf = PdfReader(io.BytesIO((self.trail / "apostila/apostila.pdf").read_bytes()))
        pdf_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        self.assertIn('class="algorithm-flow"', document)
        self.assertNotIn("data:image/png;base64", document)
        self.assertIn("Fluxo textual verificável", pdf_text)

    def test_build_reuses_cached_map_without_modifying_source_asset(self):
        expected = self.visual_map_target()
        expected.parent.mkdir(parents=True)
        expected.write_bytes(png_bytes())
        before = expected.read_bytes()

        first = self.run_build()
        first_outputs = self.generated_snapshot()
        second = self.run_build()

        self.assertEqual((first.returncode, second.returncode), (0, 0), second.stderr)
        self.assertEqual(expected.read_bytes(), before)
        self.assertEqual(self.generated_snapshot(), first_outputs)
        self.assertIn("data:image/png;base64", (self.trail / "apostila/apostila.html").read_text(encoding="utf-8"))

    def test_invalid_map_falls_back_and_replaces_the_complete_bundle(self):
        target = self.visual_map_target()
        target.parent.mkdir(parents=True)
        target.write_bytes(b"invalid-png")
        sentinel = self.seed_generated_outputs()

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_bytes(), b"invalid-png")
        self.assert_html_and_pdf_fallback()
        self.assertTrue(self.generated_snapshot())
        self.assertTrue(all(content != sentinel for content in self.generated_snapshot().values()))

    def test_check_inspects_visual_assets_without_creating_or_modifying_them(self):
        target = self.visual_map_target()
        target.parent.mkdir(parents=True)
        target.write_bytes(b"invalid-png")
        before = {
            path.relative_to(self.trail).as_posix(): path.read_bytes()
            for path in self.trail.rglob("*") if path.is_file()
        }

        result = subprocess.run(
            ["python3", str(SCRIPT), "--check", str(self.trail)], text=True, capture_output=True
        )

        after = {
            path.relative_to(self.trail).as_posix(): path.read_bytes()
            for path in self.trail.rglob("*") if path.is_file()
        }
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(after, before)

    def test_check_without_visual_cache_leaves_the_complete_tree_unchanged(self):
        self.assertFalse((self.trail / "assets").exists())
        before = self.tree_snapshot()

        result = subprocess.run(
            ["python3", str(SCRIPT), "--check", str(self.trail)], text=True, capture_output=True
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.tree_snapshot(), before)
        self.assertFalse((self.trail / "assets").exists())

    def test_check_never_imports_reportlab_in_a_clean_process(self):
        guard = """
import builtins
import sys

original_import = builtins.__import__
def guarded_import(name, *args, **kwargs):
    if name == 'reportlab' or name.startswith('reportlab.'):
        raise AssertionError('reportlab importado durante --check')
    return original_import(name, *args, **kwargs)

builtins.__import__ = guarded_import
from scripts.build_trilha import main
raise SystemExit(main(['--check', sys.argv[1]]))
"""

        result = subprocess.run(
            ["python3", "-B", "-c", guard, str(self.trail)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_loads_visual_cache_without_rendering_or_publishing(self):
        with (
            patch.object(
                build_trilha, "load_visual_map_assets", wraps=load_visual_map_assets
            ) as loader,
            patch.object(build_trilha, "render_pdf") as pdf,
            patch.object(build_trilha, "publish_bundle") as publish,
        ):
            result = build_trilha.main(["--check", str(self.trail)])

        self.assertEqual(result, 0)
        loader.assert_called_once()
        pdf.assert_not_called()
        publish.assert_not_called()

    def test_builds_hybrid_layout_with_generated_markdown_notices(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        expected = {
            "painel/indice.md", "painel/progresso.md", "painel/agenda-de-revisoes.md",
            "materiais/resumos.md", "materiais/mapas-mentais.md", "materiais/caderno-de-questoes.md",
            "revisoes/agenda.md", "apostila/apostila.md", "apostila/apostila.html",
            "modulos/01-direito-constitucional/topicos/01-controle-difuso/resumo.md",
            "modulos/01-direito-constitucional/topicos/01-controle-difuso/mapa-mental.md",
            "modulos/01-direito-constitucional/topicos/01-controle-difuso/questoes.md",
        }
        generated = {str(path.relative_to(self.trail)) for path in self.trail.rglob("*") if path.is_file()}
        self.assertTrue(expected <= generated)
        for relative in expected:
            if relative.endswith(".md"):
                self.assertTrue((self.trail / relative).read_text(encoding="utf-8").startswith(GENERATED_NOTICE))
        self.assertTrue(
            (self.trail / "apostila/apostila.html").read_text(encoding="utf-8").startswith(
                "<!-- GERADO AUTOMATICAMENTE. NÃO EDITE. -->"
            )
        )

    def test_build_keeps_recorded_session_path_after_manifest_reordering_and_renames(self):
        manifest_path = self.trail / "trilha.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        session = manifest["sessions"][0]
        recorded = Path(session["file"])
        original_source = self.trail / recorded
        module = manifest["modules"][0]
        topic = module["topics"][0]

        module["title"] = "Constitucional renomeado"
        topic["title"] = "Controle renomeado"
        session["title"] = "Sessão renomeada"
        original_source.write_text(valid_session("Sessão renomeada"), encoding="utf-8")
        module["topics"].insert(0, {
            "id": "direitos",
            "title": "Direitos fundamentais",
            "weight": 1,
            "status": "not_started",
            "sessions": [],
        })
        manifest["modules"].insert(0, {
            "id": "administrativo",
            "title": "Direito Administrativo",
            "topics": [{
                "id": "atos",
                "title": "Atos administrativos",
                "weight": 1,
                "status": "not_started",
                "sessions": ["s000"],
            }],
        })
        planned_path = Path(
            "modulos/09-estavel/topicos/09-estavel/sessoes/009-sessao-planejada.md"
        )
        planned = {
            "id": "s000",
            "title": "Sessão planejada",
            "date": "2026-08-09",
            "status": "not_started",
            "module_id": "administrativo",
            "topic_ids": ["atos"],
            "file": planned_path.as_posix(),
        }
        manifest["sessions"].insert(0, planned)
        planned_source = self.trail / planned_path
        planned_source.parent.mkdir(parents=True)
        planned_source.write_text("# Sessão planejada\n\nConteúdo pendente.\n", encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        recomputed = self.trail / (
            "modulos/02-constitucional-renomeado/topicos/02-controle-renomeado/"
            "sessoes/002-sessao-renomeada.md"
        )
        self.assertTrue(original_source.is_file())
        self.assertFalse(recomputed.exists())
        session_sources = sorted(path.relative_to(self.trail) for path in self.trail.glob("modulos/**/sessoes/*.md"))
        self.assertEqual(session_sources, sorted((recorded, planned_path)))
        index = (self.trail / "painel/indice.md").read_text(encoding="utf-8")
        self.assertIn(f"](../{recorded.as_posix()})", index)

    def test_canonical_build_does_not_create_root_apostila_duplicates(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.trail / "apostila/apostila.md").is_file())
        self.assertTrue((self.trail / "apostila/apostila.html").is_file())
        self.assertFalse((self.trail / "apostila.md").exists())
        self.assertFalse((self.trail / "apostila.html").exists())

    def test_html_sidebar_links_and_scrollspy(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        document = (self.trail / "apostila/apostila.html").read_text(encoding="utf-8")
        for marker in (
            'id="trail-sidebar"',
            'id="sidebar-toggle"',
            'data-topic-link="controle"',
            'data-topic-section="controle"',
            "new IntersectionObserver",
            "history.replaceState",
            "@media (max-width: 800px)",
            "@media print",
        ):
            self.assertIn(marker, document)

        parser = FragmentLinkParser()
        parser.feed(document)
        self.assertEqual(len(parser.ids), len(set(parser.ids)), "IDs duplicados no HTML")
        for fragment in parser.fragment_links:
            self.assertEqual(
                parser.ids.count(fragment), 1,
                f"fragmento #{fragment} deve apontar para exatamente um id",
            )
        self.assertFalse(parser.javascript_links, "links javascript: ativos não são permitidos")

    def test_html_deactivates_unknown_session_fragment_links(self):
        session_path = self.trail / (
            "modulos/01-direito-constitucional/topicos/01-controle-difuso/"
            "sessoes/001-controle-difuso.md"
        )
        session_path.write_text(
            valid_session("Controle difuso").replace(
                "Texto de estudo.",
                "Texto de estudo. [conhecido](#topico-controle) [ver](#inexistente)",
            ),
            encoding="utf-8",
        )

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        document = (self.trail / "apostila/apostila.html").read_text(encoding="utf-8")
        parser = FragmentLinkParser()
        parser.feed(document)
        self.assertIn('<a href="#topico-controle">conhecido</a>', document)
        self.assertIn('<a href="#topico-controle">conhecido</a> ver', document)
        self.assertNotIn("inexistente", parser.fragment_links)
        for fragment in parser.fragment_links:
            self.assertEqual(parser.ids.count(fragment), 1)

    def test_mobile_closed_sidebar_is_hidden_and_inert(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        document = (self.trail / "apostila/apostila.html").read_text(encoding="utf-8")
        for behavior in (
            "window.matchMedia('(max-width: 800px)')",
            "sidebar.hidden = mobile && !open;",
            "sidebar.inert = mobile && !open;",
            "mobileQuery.addEventListener('change', () => setSidebarState(false));",
            "setSidebarState(false);",
        ):
            self.assertIn(behavior, document)
        self.assertIn(
            "#sidebar-toggle { display: block; margin: 1rem; position: relative; z-index: 2; }",
            document,
        )

    def test_mobile_sidebar_stays_available_without_javascript(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        document = (self.trail / "apostila/apostila.html").read_text(encoding="utf-8")
        mobile_css = document.split("@media (max-width: 800px) {", 1)[1].split(
            "@media print", 1
        )[0]
        self.assertRegex(mobile_css, r"(?m)^  #trail-sidebar \{ position: static;")
        self.assertNotRegex(
            mobile_css,
            r"(?m)^  #trail-sidebar \{[^\n]*transform: translateX\(-105%\)",
        )
        self.assertRegex(
            mobile_css,
            r"(?m)^  \.js #trail-sidebar \{[^\n]*transform: translateX\(-105%\)",
        )
        self.assertIn("  .js #sidebar-toggle { display: block;", mobile_css)
        self.assertIn(
            "setSidebarState(false);\ndocument.documentElement.classList.add('js');",
            document,
        )

    def test_index_scrolling_respects_reduced_motion(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        document = (self.trail / "apostila/apostila.html").read_text(encoding="utf-8")
        self.assertIn("html { scroll-behavior: smooth; }", document)
        self.assertIn(
            "@media (prefers-reduced-motion: reduce) { "
            "html { scroll-behavior: auto; } }",
            document,
        )

    @unittest.skipUnless(find_spec("scripts.trilha_outputs"), "output publisher not implemented yet")
    def test_publish_bundle_restores_every_prior_file_when_a_replace_fails(self):
        from scripts.trilha_outputs import publish_bundle

        outputs = {
            Path("painel/indice.md"): b"new index",
            Path("materiais/resumos.md"): b"new summaries",
            Path("apostila/apostila.md"): b"new booklet",
        }
        before = {
            Path("painel/indice.md"): b"old index",
            Path("materiais/resumos.md"): b"old summaries",
        }
        for relative, content in before.items():
            target = self.trail / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)

        calls = 0

        def fail_on_third_replace(source, target):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("replace failure")
            source.replace(target)

        with self.assertRaisesRegex(OSError, "replace failure"):
            publish_bundle(self.trail, outputs, replace_file=fail_on_third_replace)

        self.assertEqual((self.trail / "painel/indice.md").read_bytes(), b"old index")
        self.assertEqual((self.trail / "materiais/resumos.md").read_bytes(), b"old summaries")
        self.assertFalse((self.trail / "apostila/apostila.md").exists())

    def test_publish_bundle_refuses_visual_map_source_assets(self):
        from scripts.trilha_outputs import publish_bundle

        target = self.trail / "assets/mapas/controle-cache/mapa.png"

        with self.assertRaisesRegex(ValueError, "fonte"):
            publish_bundle(self.trail, {target.relative_to(self.trail): b"derived image"})

        self.assertFalse(target.exists())

    def test_publish_bundle_rejects_normalized_visual_map_source_paths(self):
        from scripts.trilha_outputs import publish_bundle

        variants = (
            ("assets/mapas/controle-cache/mapa-1.png", "mapa-1.png"),
            ("temporario/../assets/mapas/controle-cache/mapa-2.png", "mapa-2.png"),
            ("./assets/mapas/controle-cache/mapa-3.png", "mapa-3.png"),
            ("assets/outro/../mapas/controle-cache/mapa-4.png", "mapa-4.png"),
        )
        for relative, filename in variants:
            with self.subTest(relative=relative):
                target = self.trail / "assets/mapas/controle-cache" / filename
                with self.assertRaisesRegex(ValueError, "fonte"):
                    publish_bundle(self.trail, {Path(relative): b"derived image"})
                self.assertFalse(target.exists())

    def test_publish_bundle_still_rejects_paths_that_escape_the_trail(self):
        from scripts.trilha_outputs import publish_bundle

        escaped = self.trail.parent / "outside-derived.md"

        with self.assertRaisesRegex(ValueError, "contido"):
            publish_bundle(self.trail, {Path("../outside-derived.md"): b"derived output"})

        self.assertFalse(escaped.exists())

    def test_secondary_topic_links_to_the_single_canonical_session_source(self):
        manifest = json.loads((self.trail / "trilha.json").read_text(encoding="utf-8"))
        manifest["modules"][0]["topics"].append({
            "id": "direitos",
            "title": "Direitos fundamentais",
            "weight": 1,
            "status": "completed",
            "sessions": ["s001"],
        })
        manifest["sessions"][0]["topic_ids"] = ["controle", "direitos"]
        (self.trail / "trilha.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        (self.trail / "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md").write_text(
            valid_session("Controle difuso", topic_ids=("controle", "direitos")), encoding="utf-8"
        )

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        canonical = self.trail / (
            "modulos/01-direito-constitucional/topicos/01-controle-difuso/"
            "sessoes/001-controle-difuso.md"
        )
        secondary = self.trail / (
            "modulos/01-direito-constitucional/topicos/02-direitos-fundamentais/questoes.md"
        )
        self.assertTrue(canonical.exists())
        self.assertFalse((secondary.parent / "sessoes/001-controle-difuso.md").exists())
        questions = secondary.read_text(encoding="utf-8")
        self.assertIn("../01-controle-difuso/sessoes/001-controle-difuso.md", questions)
        self.assertIn("### Questão 2", questions)
        self.assertNotRegex(questions, r"(?m)^### Questão 1$")
        self.assertNotIn("### Diagnóstico agregado", questions)
        self.assert_every_local_link_resolves()

    def test_html_secondary_topic_discloses_shared_session(self):
        manifest = json.loads((self.trail / "trilha.json").read_text(encoding="utf-8"))
        manifest["modules"][0]["topics"].append({
            "id": "direitos",
            "title": "Direitos fundamentais",
            "weight": 1,
            "status": "completed",
            "sessions": ["s001"],
        })
        manifest["sessions"][0]["topic_ids"] = ["controle", "direitos"]
        (self.trail / "trilha.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        session_path = self.trail / (
            "modulos/01-direito-constitucional/topicos/01-controle-difuso/"
            "sessoes/001-controle-difuso.md"
        )
        session_path.write_text(
            valid_session("Controle difuso", topic_ids=("controle", "direitos")), encoding="utf-8"
        )

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        document = (self.trail / "apostila/apostila.html").read_text(encoding="utf-8")
        secondary = re.search(
            r'<section id="topico-direitos".*?</section>', document, re.DOTALL
        )
        self.assertIsNotNone(secondary)
        self.assertIn("Sessão compartilhada", secondary.group(0))
        self.assertIn('href="#sessao-s001"', secondary.group(0))
        self.assertIn("let navigationTarget = null;", document)
        self.assertIn("navigationTarget = key;", document)
        self.assertIn("if (navigationTarget) return;", document)

    def test_panels_link_the_tree_and_agendas_use_review_details_not_session_dates(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        index = (self.trail / "painel/indice.md").read_text(encoding="utf-8")
        progress = (self.trail / "painel/progresso.md").read_text(encoding="utf-8")
        for label, relative in {
            "Direito Constitucional": "../modulos/01-direito-constitucional/",
            "Controle difuso": "../modulos/01-direito-constitucional/topicos/01-controle-difuso/resumo.md",
            "Resumos": "../materiais/resumos.md",
            "Mapas mentais": "../materiais/mapas-mentais.md",
            "Caderno de questões": "../materiais/caderno-de-questoes.md",
        }.items():
            self.assertIn(f"[{label}]({relative})", index)
        self.assertIn("Progresso global: 100%", progress)
        self.assertIn("Direito Constitucional: 100%", progress)
        self.assertIn("Direito Constitucional / Controle difuso: 100%", progress)
        for relative in ("painel/agenda-de-revisoes.md", "revisoes/agenda.md"):
            agenda = (self.trail / relative).read_text(encoding="utf-8")
            self.assertIn("Controle difuso", agenda)
            self.assertIn("Próxima revisão: Em sete dias.", agenda)
            self.assertIn("Prioridade: consolidar competência.", agenda)
            self.assertNotIn("2026-08-10", agenda)
        self.assert_every_local_link_resolves()

    def test_agendas_sort_by_review_date_then_stable_priority(self):
        manifest_path = self.trail / "trilha.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        topic = manifest["modules"][0]["topics"][0]
        cases = (
            ("s-invalid", "Data inválida", "quando possível", "alta"),
            ("s-late", "Data posterior", "2026-09-01", "média"),
            ("s-low", "Mesma data baixa", "2026-08-20", "baixa"),
            ("s-high", "Mesma data alta", "2026-08-20", "alta"),
        )
        manifest["sessions"] = []
        topic["sessions"] = []
        for index, (session_id, title, review, priority) in enumerate(cases, 1):
            relative = Path(
                "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes"
            ) / f"{index:03d}-{session_id}.md"
            manifest["sessions"].append({
                "id": session_id,
                "title": title,
                "date": f"2026-08-{index:02d}",
                "status": "completed",
                "module_id": "constitucional",
                "topic_ids": ["controle"],
                "file": relative.as_posix(),
            })
            topic["sessions"].append(session_id)
            text = valid_session(title).replace(
                "- Prioridade: consolidar competência.", f"- Prioridade: {priority}"
            ).replace(
                "## Próxima revisão\n\nEm sete dias.", f"## Próxima revisão\n\n{review}"
            )
            target = self.trail / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        for relative in ("painel/agenda-de-revisoes.md", "revisoes/agenda.md"):
            agenda = (self.trail / relative).read_text(encoding="utf-8")
            self.assertIn("Prioridades: alta, média, baixa; valores desconhecidos depois.", agenda)
            positions = [
                agenda.index(title)
                for title in ("Mesma data alta", "Mesma data baixa", "Data posterior", "Data inválida")
            ]
            self.assertEqual(positions, sorted(positions))

    def assert_every_local_link_resolves(self):
        for source in self.trail.rglob("*.md"):
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source.read_text(encoding="utf-8")):
                if target.startswith("#") or ":" in target:
                    continue
                resolved = (source.parent / target).resolve()
                self.assertTrue(
                    resolved.exists(),
                    f"{source.relative_to(self.trail)} links to missing {target}",
                )


if __name__ == "__main__":
    unittest.main()
