import json
import re
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from importlib.util import find_spec
from pathlib import Path

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
