import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_trilha.py"


class BuildTrilhaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trail = Path(self.tmp.name) / "trilha"
        (self.trail / "sessoes").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def run_build(self, *args):
        return subprocess.run(
            ["python3", str(SCRIPT), *args, str(self.trail)],
            text=True,
            capture_output=True,
        )

    def write_manifest(self, manifest=None):
        manifest = manifest or self.valid_manifest()
        (self.trail / "trilha.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return manifest

    def write_session(self, name, content=None):
        content = content or valid_session("Controle difuso")
        (self.trail / "sessoes" / name).write_text(content, encoding="utf-8")

    def valid_manifest(self):
        return {
            "schema_version": 1,
            "title": "Trilha de Direito Constitucional",
            "slug": "direito-constitucional",
            "source": "provisional",
            "exam": None,
            "banca": None,
            "recalibrated": False,
            "modules": [
                {
                    "id": "constitucional",
                    "title": "Direito Constitucional",
                    "topics": [
                        {"id": "controle", "title": "Controle difuso", "weight": 1,
                         "status": "completed", "sessions": ["s001"]},
                        {"id": "direitos", "title": "Direitos fundamentais", "weight": 3,
                         "status": "not_started", "sessions": ["s002"]},
                    ],
                }
            ],
            "sessions": [
                {"id": "s001", "title": "Controle difuso", "date": "2026-08-10",
                 "status": "completed", "module_id": "constitucional", "topic_ids": ["controle"],
                 "file": "sessoes/001.md"},
                {"id": "s002", "title": "Direitos fundamentais", "date": "2026-08-11",
                 "status": "not_started", "module_id": "constitucional", "topic_ids": ["direitos"],
                 "file": "sessoes/002.md"},
            ],
        }

    def write_valid_trail(self):
        self.write_manifest()
        self.write_session("001.md")
        self.write_session("002.md", "# Direitos fundamentais\n\nConteúdo pendente.\n")

    def test_provisional_manifest_calculates_weighted_progress(self):
        self.write_valid_trail()

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        markdown = (self.trail / "apostila.md").read_text(encoding="utf-8")
        self.assertIn("Progresso global: 25%", markdown)

    def test_boolean_schema_version_is_rejected(self):
        self.write_valid_trail()
        manifest = self.valid_manifest()
        manifest["schema_version"] = True
        self.write_manifest(manifest)

        result = self.run_build()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema_version deve ser o inteiro 1", result.stderr)

    def test_decimal_schema_version_is_rejected(self):
        self.write_valid_trail()
        manifest = self.valid_manifest()
        manifest["schema_version"] = 1.0
        self.write_manifest(manifest)

        result = self.run_build()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("schema_version deve ser o inteiro 1", result.stderr)

    def test_extreme_finite_weights_calculate_progress_without_overflow(self):
        self.write_valid_trail()
        manifest = self.valid_manifest()
        manifest["modules"][0]["topics"][0]["weight"] = 1e308
        manifest["modules"][0]["topics"][1]["weight"] = 1e308
        self.write_manifest(manifest)

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        markdown = (self.trail / "apostila.md").read_text(encoding="utf-8")
        self.assertIn("Progresso global: 50%", markdown)

    def test_nonfinite_json_weights_are_rejected_without_changing_outputs(self):
        self.write_valid_trail()
        valid_json = json.dumps(self.valid_manifest())
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                (self.trail / "apostila.md").write_bytes(b"valid markdown")
                (self.trail / "apostila.html").write_bytes(b"valid html")
                invalid_json = valid_json.replace('"weight": 1', f'"weight": {value}', 1)
                (self.trail / "trilha.json").write_text(invalid_json, encoding="utf-8")

                result = self.run_build()

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("peso deve ser finito", result.stderr)
                self.assertEqual((self.trail / "apostila.md").read_bytes(), b"valid markdown")
                self.assertEqual((self.trail / "apostila.html").read_bytes(), b"valid html")

    def test_check_validates_without_creating_or_changing_outputs(self):
        self.write_valid_trail()
        result = self.run_build("--check")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.trail / "apostila.md").exists())
        self.assertFalse((self.trail / "apostila.html").exists())
        before_md = b"previous markdown"
        before_html = b"previous html"
        (self.trail / "apostila.md").write_bytes(before_md)
        (self.trail / "apostila.html").write_bytes(before_html)

        result = self.run_build("--check")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.trail / "apostila.md").read_bytes(), before_md)
        self.assertEqual((self.trail / "apostila.html").read_bytes(), before_html)

    def test_build_creates_accessible_index_legend_and_printable_outputs(self):
        self.write_valid_trail()

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        markdown = (self.trail / "apostila.md").read_text(encoding="utf-8")
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        self.assertIn("## Índice", markdown)
        self.assertIn("Régua de progresso: 25%", markdown)
        self.assertIn('role="progressbar"', html)
        self.assertIn('aria-valuenow="25"', html)
        self.assertIn("@media print", html)
        for label, color in {
            "Conceito": "#2563EB", "Regra": "#16A34A", "Exceção": "#D97706",
            "Pegadinha": "#DC2626", "Jurisprudência": "#7C3AED",
        }.items():
            self.assertIn(label, html)
            self.assertIn(color, html)

    def test_index_links_to_deterministic_module_and_session_anchors(self):
        self.write_valid_trail()

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        markdown = (self.trail / "apostila.md").read_text(encoding="utf-8")
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        self.assertIn("[Direito Constitucional](#modulo-constitucional)", markdown)
        self.assertIn("[Controle difuso](#sessao-s001)", markdown)
        self.assertIn('<a id="modulo-constitucional"></a>', markdown)
        self.assertIn('<a id="sessao-s001"></a>', markdown)
        self.assertIn('href="#modulo-constitucional"', html)
        self.assertIn('href="#sessao-s001"', html)
        self.assertIn('id="modulo-constitucional"', html)
        self.assertIn('id="sessao-s001"', html)

    def test_same_input_produces_byte_identical_outputs(self):
        self.write_valid_trail()
        self.assertEqual(self.run_build().returncode, 0)
        first = tuple((self.trail / f).read_bytes() for f in ("apostila.md", "apostila.html"))

        self.assertEqual(self.run_build().returncode, 0)
        second = tuple((self.trail / f).read_bytes() for f in ("apostila.md", "apostila.html"))
        self.assertEqual(second, first)

    def test_invalid_manifests_leave_existing_outputs_untouched(self):
        invalid_cases = {
            "invalid_json": "{ no json",
            "non_positive_weight": lambda m: set_value(m, ["modules", 0, "topics", 0, "weight"], 0),
            "duplicate_ids": lambda m: set_value(m, ["sessions", 1, "id"], "s001"),
            "missing_reference": lambda m: set_value(m, ["sessions", 0, "module_id"], "missing"),
            "missing_required_section": None,
            "invalid_map_category": None,
            "missing_question_feedback": None,
            "incomplete_question_feedback": None,
            "missing_aggregate_diagnosis": None,
            "source_wrong_type": lambda m: set_value(m, ["source"], []),
            "topic_status_wrong_type": lambda m: set_value(m, ["modules", 0, "topics", 0, "status"], {}),
            "session_status_wrong_type": lambda m: set_value(m, ["sessions", 0, "status"], []),
        }
        for name, mutate in invalid_cases.items():
            with self.subTest(name=name):
                case_dir = self.trail.parent / name
                shutil.copytree(self.trail, case_dir)
                original_trail = self.trail
                self.trail = case_dir
                self.write_valid_trail()
                (self.trail / "apostila.md").write_bytes(b"valid markdown")
                (self.trail / "apostila.html").write_bytes(b"valid html")
                if name == "invalid_json":
                    (self.trail / "trilha.json").write_text(mutate, encoding="utf-8")
                elif name == "missing_required_section":
                    self.write_session("001.md", valid_session("Controle difuso").replace("## Fontes\n\n", ""))
                elif name == "invalid_map_category":
                    self.write_session("001.md", valid_session("Controle difuso").replace("[conceito]", "[inválido]"))
                elif name == "missing_question_feedback":
                    self.write_session("001.md", valid_session("Controle difuso").replace(
                        "### Questão 1\n- Resposta: alternativa A\n- Resultado: correta; gabarito A\n"
                        "- Fundamento: Constituição Federal.\n- Alternativas úteis: B ignora a competência.\n"
                        "- Tipo de erro: nenhum\n- Prevenção: manter a revisão.\n"
                        "- Fonte: Constituição Federal.\n- Revisão: em sete dias.\n\n", ""
                    ))
                elif name == "incomplete_question_feedback":
                    self.write_session("001.md", valid_session("Controle difuso").replace(
                        "- Prevenção: manter a revisão.\n", ""
                    ))
                elif name == "missing_aggregate_diagnosis":
                    self.write_session("001.md", valid_session("Controle difuso").replace(
                        "### Diagnóstico agregado\n- Acertos: 1/1 (100%).\n- Padrões de erro: nenhum.\n"
                        "- Prioridade: consolidar competência.\n- Próxima revisão: em sete dias.\n\n", ""
                    ))
                else:
                    manifest = self.valid_manifest()
                    mutate(manifest)
                    self.write_manifest(manifest)
                result = self.run_build()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual((self.trail / "apostila.md").read_bytes(), b"valid markdown")
                self.assertEqual((self.trail / "apostila.html").read_bytes(), b"valid html")
                self.trail = original_trail

    def test_escapes_raw_html_and_disables_javascript_links(self):
        self.write_valid_trail()
        self.write_session(
            "001.md",
            valid_session("Controle difuso").replace(
                "Texto de estudo.", "<script>alert('x')</script> [perigoso](javascript:alert(1))"
            ),
        )

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;", html)
        self.assertNotIn('href="javascript:', html.lower())

    def test_html_url_query_escapes_ampersand_once(self):
        self.write_valid_trail()
        self.write_session(
            "001.md",
            valid_session("Controle difuso").replace(
                "Texto de estudo.", "[fonte](https://exemplo/?a=1&b=2)"
            ),
        )

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        self.assertIn('href="https://exemplo/?a=1&amp;b=2"', html)
        self.assertNotIn("&amp;amp;", html)

    def test_recalibrated_edital_trail_is_identified(self):
        self.write_valid_trail()
        manifest = self.valid_manifest()
        manifest["source"] = "edital"
        manifest["recalibrated"] = True
        self.write_manifest(manifest)

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Trilha recalibrada", (self.trail / "apostila.md").read_text(encoding="utf-8"))

    def test_html_renders_level_three_session_headings_without_markdown_markers(self):
        self.write_valid_trail()

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        self.assertIn("<h5>Questão 1</h5>", html)
        self.assertIn("<h5>Diagnóstico agregado</h5>", html)
        self.assertNotIn("### Questão 1", html)
        self.assertNotIn("### Diagnóstico agregado", html)

    def test_html_preserves_three_level_mind_map_hierarchy_and_colors(self):
        self.write_valid_trail()

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        self.assertIn('<ul class="mind-map">', html)
        self.assertIn('class="map-item map-level-1"', html)
        self.assertIn('class="map-item map-level-2"', html)
        self.assertIn('class="map-item map-level-3"', html)
        self.assertIn("Base", html)
        self.assertIn("Aplicação", html)
        self.assertIn("Limite", html)
        self.assertIn("border-color:#2563EB", html)
        self.assertIn("border-color:#16A34A", html)
        self.assertIn("border-color:#D97706", html)

    def test_in_progress_session_with_unvalidated_map_content_still_builds(self):
        self.write_valid_trail()
        manifest = self.valid_manifest()
        manifest["sessions"][1]["status"] = "in_progress"
        manifest["modules"][0]["topics"][1]["status"] = "in_progress"
        self.write_manifest(manifest)
        self.write_session(
            "002.md",
            "# Direitos fundamentais\n\n## Mapa mental\n\n- [rascunho] Conteúdo em elaboração.\n",
        )

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        self.assertIn("Conteúdo em elaboração.", html)


def set_value(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


def valid_session(title):
    return f"""# {title}

## Conteúdo principal

Texto de estudo.

## Resumo estratégico

- Item 1
- Item 2
- Item 3
- Item 4
- Item 5

## Mapa mental

- [conceito] Base
  - [regra] Aplicação
    - [excecao] Limite
- [pegadinha] Atenção
- [jurisprudencia] Precedente

## Questões e feedback

### Questão 1
- Resposta: alternativa A
- Resultado: correta; gabarito A
- Fundamento: Constituição Federal.
- Alternativas úteis: B ignora a competência.
- Tipo de erro: nenhum
- Prevenção: manter a revisão.
- Fonte: Constituição Federal.
- Revisão: em sete dias.

### Diagnóstico agregado
- Acertos: 1/1 (100%).
- Padrões de erro: nenhum.
- Prioridade: consolidar competência.
- Próxima revisão: em sete dias.

## Fontes

- Constituição Federal.

## Próxima revisão

Em sete dias.
"""


if __name__ == "__main__":
    unittest.main()
