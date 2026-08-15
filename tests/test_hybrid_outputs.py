import json
import subprocess
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from tests.test_build_trilha import valid_session


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_trilha.py"
GENERATED_NOTICE = "<!-- GERADO AUTOMATICAMENTE. NÃO EDITE. -->\n\n"


class HybridOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trail = Path(self.tmp.name) / "trilha"
        (self.trail / "sessoes").mkdir(parents=True)
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
                "file": "sessoes/001.md",
            }],
        }
        (self.trail / "trilha.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        (self.trail / "sessoes/001.md").write_text(
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
        (self.trail / "sessoes/001.md").write_text(
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


if __name__ == "__main__":
    unittest.main()
