import io
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader


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
