import io
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

from scripts.trilha_pdf import render_pdf
from scripts.trilha_visual_maps import VisualMapAsset, build_visual_map_specs
from tests.test_build_trilha import detailed_session, valid_session
from tests.test_visual_maps import algorithm_session, truncated_idat_png
from tests.trilha_support import png_bytes


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_trilha.py"


class PdfOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trail = Path(self.tmp.name) / "trilha"
        self.trail.mkdir()
        self._write_trail()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_trail(self):
        from tests.test_hybrid_outputs import HybridOutputTests

        fixture = HybridOutputTests(methodName="runTest")
        fixture.trail = self.trail
        fixture.write_trail()

    def run_build(self):
        return subprocess.run(
            ["python3", str(SCRIPT), str(self.trail)], text=True, capture_output=True
        )

    def ready_visual_fixture(self):
        manifest = {
            "title": "Trilha de Direito Constitucional",
            "recalibrated": False,
            "modules": [{
                "id": "constitucional", "title": "Direito Constitucional", "topics": [{
                    "id": "controle", "title": "Controle difuso", "weight": 1,
                    "status": "completed", "sessions": ["s001"],
                }],
            }],
            "sessions": [{
                "id": "s001", "title": "Controle difuso", "date": "2026-08-10",
                "status": "completed", "module_id": "constitucional", "topic_ids": ["controle"],
            }],
        }
        session_files = {
            "s001": algorithm_session("Controle difuso", (
                "ENTRADA: existe caso concreto?",
                "SE SIM: identificar a controvérsia constitucional.",
                "ENTÃO: aplicar o controle difuso.",
                "SENÃO: encerrar a análise.",
                "RESULTADO: decisão fundamentada.",
                "ALERTA: observar a reserva de plenário.",
            )),
        }
        spec = build_visual_map_specs(manifest, session_files)["controle"]
        return manifest, session_files, {
            "controle": VisualMapAsset(spec, "ready", png_bytes(), None),
        }

    def missing_visual_fixture(self):
        manifest, session_files, assets = self.ready_visual_fixture()
        spec = assets["controle"].spec
        return manifest, session_files, {
            "controle": VisualMapAsset(spec, "missing", None, None),
        }

    @staticmethod
    def pdf_text(pdf):
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)

    def test_pdf_embeds_ready_visual_map_and_keeps_textual_algorithm(self):
        manifest, session_files, assets = self.ready_visual_fixture()

        pdf = render_pdf(manifest, session_files, assets)
        reader = PdfReader(io.BytesIO(pdf))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        images = [
            object_ref.get_object()
            for page in reader.pages
            for object_ref in (page.get("/Resources", {}).get("/XObject", {}) or {}).values()
            if object_ref.get_object().get("/Subtype") == "/Image"
        ]

        self.assertTrue(images)
        self.assertIn("ENTRADA: existe caso concreto?", text)
        self.assertIn("Progresso global", text)
        self.assertEqual(reader.metadata.title, manifest["title"])
        self.assertIn("Página 1", text)
        self.assertTrue(any("/Annots" in page for page in reader.pages))
        self.assertTrue(reader.outline)
        self.assertTrue(any(
            re.search(r"Questão 1\s+Tópico: controle\s+Resposta: alternativa A", page.extract_text() or "")
            for page in reader.pages
        ))

    def test_pdf_unavailable_or_absent_visual_map_uses_searchable_fallback(self):
        manifest, session_files, assets = self.missing_visual_fixture()
        spec = assets["controle"].spec

        for visual_maps in (
            assets,
            {"controle": VisualMapAsset(spec, "invalid", None, "imagem inválida")},
            None,
        ):
            with self.subTest(visual_maps=visual_maps is None and "absent" or visual_maps["controle"].status):
                text = self.pdf_text(render_pdf(manifest, session_files, visual_maps))

                self.assertIn("Mapa algorítmico", text)
                self.assertIn("SE SIM", text)

    def test_visual_pdf_is_byte_identical_across_two_builds(self):
        manifest, session_files, assets = self.ready_visual_fixture()

        self.assertEqual(
            render_pdf(manifest, session_files, assets),
            render_pdf(manifest, session_files, assets),
        )

    def test_multi_topic_session_is_detailed_only_under_its_canonical_topic(self):
        manifest, session_files, _assets = self.ready_visual_fixture()
        session = manifest["sessions"][0]
        session["title"] = "Sessão integrada"
        session["topic_ids"] = ["controle", "direitos"]
        manifest["modules"][0]["topics"].append({
            "id": "direitos", "title": "Direitos fundamentais", "weight": 1,
            "status": "completed", "sessions": ["s001"],
        })

        text = self.pdf_text(render_pdf(manifest, session_files))

        self.assertEqual(text.count("Sessão integrada"), 1)
        self.assertEqual(len(re.findall(r"(?m)^Questão 1$", text)), 1)
        self.assertIn("Direitos fundamentais", text)

    def test_long_index_has_its_own_paginated_readable_section(self):
        topics = [
            {"id": f"topico-{number}", "title": f"Tópico {number:02}", "weight": 1,
             "status": "not_started", "sessions": []}
            for number in range(1, 81)
        ]
        manifest = {
            "title": "Trilha de índice longo", "recalibrated": False,
            "modules": [{"id": "longo", "title": "Módulo longo", "topics": topics}],
            "sessions": [],
        }

        reader = PdfReader(io.BytesIO(render_pdf(manifest, {})))
        index_text = "\n".join(page.extract_text() or "" for page in reader.pages[1:4])

        self.assertGreaterEqual(len(reader.pages), 4)
        self.assertIn("Índice da trilha", index_text)
        self.assertIn("Tópico 80", index_text)
        self.assertTrue(any("/Annots" in page for page in reader.pages[1:4]))

    def test_undecodable_ready_image_degrades_to_textual_fallback(self):
        manifest, session_files, assets = self.ready_visual_fixture()
        spec = assets["controle"].spec

        text = self.pdf_text(render_pdf(manifest, session_files, {
            "controle": VisualMapAsset(spec, "ready", b"not-a-png", None),
        }))

        self.assertIn("Mapa algorítmico", text)
        self.assertIn("ENTRADA: existe caso concreto?", text)

    def test_crc_valid_but_corrupt_ready_image_degrades_to_textual_fallback(self):
        manifest, session_files, assets = self.ready_visual_fixture()
        spec = assets["controle"].spec

        text = self.pdf_text(render_pdf(manifest, session_files, {
            "controle": VisualMapAsset(spec, "ready", truncated_idat_png(), None),
        }))

        self.assertIn("Mapa algorítmico", text)
        self.assertIn("ENTRADA: existe caso concreto?", text)

    def test_build_generates_a_linked_pdf_study_booklet(self):
        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        pdf = (self.trail / "apostila/apostila.pdf").read_bytes()
        reader = PdfReader(io.BytesIO(pdf))
        self.assertGreaterEqual(len(reader.pages), 2)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Trilha de Direito Constitucional", text)
        self.assertIn("Questão 20", text)
        self.assertTrue(any("/Annots" in page for page in reader.pages))

    def test_pdf_renders_theory_subheadings_before_questions_without_markers(self):
        manifest, session_files, _assets = self.ready_visual_fixture()
        manifest["sessions"][0]["theory_briefing_version"] = 1
        session_files["s001"] = detailed_session("Controle difuso")

        text = self.pdf_text(render_pdf(manifest, session_files))

        self.assertIn("Objetivos de aprendizagem", text)
        self.assertNotIn("### Objetivos de aprendizagem", text)
        self.assertLess(text.index("Objetivos de aprendizagem"), text.index("Questão 1"))

    def test_pdf_renders_complete_question_before_answer_and_feedback(self):
        manifest, session_files, _assets = self.ready_visual_fixture()
        session_files["s001"] = valid_session(
            "Controle difuso", include_question_content=True
        )

        text = self.pdf_text(render_pdf(manifest, session_files))

        question = text.index("Pergunta")
        alternatives = text.index("Alternativas", question)
        feedback = text.index("Resposta e feedback", alternatives)
        result = text.index("Resultado:", feedback)
        self.assertLess(question, alternatives)
        self.assertLess(alternatives, feedback)
        self.assertLess(feedback, result)
        self.assertIn("Qual regra jurídica se aplica à situação 1?", text)
        self.assertIn("E) Não existe revisão possível.", text)
        self.assertNotIn("#### Pergunta", text)
        self.assertNotIn("#### Alternativas", text)
        self.assertNotIn("#### Resposta e feedback", text)

    def test_build_generates_identical_pdf_bytes_twice(self):
        first = self.run_build()
        first_pdf = (self.trail / "apostila/apostila.pdf").read_bytes()

        second = self.run_build()

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((self.trail / "apostila/apostila.pdf").read_bytes(), first_pdf)

    def test_pdf_keeps_official_source_urls_clickable(self):
        self.assertEqual(self.run_build().returncode, 0)
        reader = PdfReader(io.BytesIO((self.trail / "apostila/apostila.pdf").read_bytes()))

        destinations = []
        for page in reader.pages:
            for annotation in page.get("/Annots", []):
                action = annotation.get_object().get("/A")
                if action and action.get("/URI"):
                    destinations.append(str(action["/URI"]))
        self.assertIn("https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm", destinations)

    def test_pdf_renders_the_aggregate_diagnosis_once(self):
        self.assertEqual(self.run_build().returncode, 0)
        reader = PdfReader(io.BytesIO((self.trail / "apostila/apostila.pdf").read_bytes()))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)

        self.assertEqual(text.count("Diagnóstico agregado"), 1)

    def test_missing_pdf_dependency_preserves_every_prior_output(self):
        from scripts.build_trilha import build_trail
        from scripts.trilha_pdf import PdfDependencyError

        self.assertEqual(self.run_build().returncode, 0)
        before = {
            path.relative_to(self.trail): path.read_bytes()
            for path in self.trail.rglob("*") if path.is_file()
        }
        with patch("scripts.trilha_pdf.load_reportlab", side_effect=ModuleNotFoundError("reportlab")):
            with self.assertRaisesRegex(PdfDependencyError, "python3 -m pip install -r requirements.txt"):
                build_trail(self.trail)

        after = {
            path.relative_to(self.trail): path.read_bytes()
            for path in self.trail.rglob("*") if path.is_file()
        }
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
