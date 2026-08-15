import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import scripts.build_trilha as build_trilha
from tests.trilha_support import feedback_section


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_trilha.py"


class BuildTrilhaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trail = Path(self.tmp.name) / "trilha"
        self.trail.mkdir()

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
        paths = {
            "001.md": "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md",
            "002.md": "modulos/01-direito-constitucional/topicos/02-direitos-fundamentais/sessoes/002-direitos-fundamentais.md",
        }
        path = self.trail / paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

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
                 "file": "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md"},
                {"id": "s002", "title": "Direitos fundamentais", "date": "2026-08-11",
                 "status": "not_started", "module_id": "constitucional", "topic_ids": ["direitos"],
                 "file": "modulos/01-direito-constitucional/topicos/02-direitos-fundamentais/sessoes/002-direitos-fundamentais.md"},
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

    def test_targeted_completed_session_requires_exactly_twenty_questions(self):
        self.write_valid_trail()
        manifest = self.valid_manifest()
        manifest["sessions"][0]["question_target"] = 20
        self.write_manifest(manifest)
        self.write_session("001.md", valid_session("Controle difuso", question_count=19))
        result = self.run_build("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exatamente 20 questões", result.stderr)

    def test_targeted_questions_cover_every_session_topic(self):
        self.write_valid_trail()
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
        self.write_session("001.md", valid_session("Controle difuso", question_count=19))
        result = self.run_build("--check")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_question_feedback_parser_returns_questions_and_diagnosis(self):
        questions, diagnosis = build_trilha.parse_question_feedback(feedback_section(2, ("controle", "direitos")))
        self.assertEqual([(question.number, question.topic_id) for question in questions], [
            (1, "controle"), (2, "direitos"),
        ])
        self.assertIn("Acertos: 20/20", diagnosis)

    def test_invalid_targeted_question_inputs_preserve_outputs_without_traceback(self):
        cases = {
            "duplicate_question": lambda manifest, text: text.replace("### Questão 8", "### Questão 7"),
            "skipped_question": lambda manifest, text: text.replace("### Questão 11", "### Questão 12"),
            "invalid_topic": lambda manifest, text: text.replace("- Tópico: controle", "- Tópico: inexistente", 1),
            "non_integer_target": lambda manifest, text: manifest["sessions"][0].update(question_target="20"),
            "wrong_target": lambda manifest, text: manifest["sessions"][0].update(question_target=19),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name):
                self.write_valid_trail()
                manifest = self.valid_manifest()
                manifest["sessions"][0]["question_target"] = 20
                text = valid_session("Controle difuso")
                mutation = mutate(manifest, text)
                if isinstance(mutation, str):
                    text = mutation
                self.write_manifest(manifest)
                self.write_session("001.md", text)
                before_md = b"previous markdown"
                before_html = b"previous html"
                (self.trail / "apostila.md").write_bytes(before_md)
                (self.trail / "apostila.html").write_bytes(before_html)

                result = self.run_build()

                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual((self.trail / "apostila.md").read_bytes(), before_md)
                self.assertEqual((self.trail / "apostila.html").read_bytes(), before_html)

    def test_oversized_question_number_reports_validation_error_without_traceback(self):
        self.write_valid_trail()
        manifest = self.valid_manifest()
        manifest["sessions"][0]["question_target"] = 20
        self.write_manifest(manifest)
        oversized_number = "9" * 5_000
        self.write_session(
            "001.md",
            valid_session("Controle difuso").replace("### Questão 1", f"### Questão {oversized_number}"),
        )

        result = self.run_build("--check")

        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("número de questão inválido", result.stderr)

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
            "map_starts_below_first_level": None,
            "map_skips_a_level": None,
            "missing_question_feedback": None,
            "incomplete_question_feedback": None,
            "missing_aggregate_diagnosis": None,
            "source_wrong_type": lambda m: set_value(m, ["source"], []),
            "topic_status_wrong_type": lambda m: set_value(m, ["modules", 0, "topics", 0, "status"], {}),
            "session_status_wrong_type": lambda m: set_value(m, ["sessions", 0, "status"], []),
            "session_topic_id_wrong_type": lambda m: set_value(m, ["sessions", 0, "topic_ids"], [{}]),
            "topic_session_id_wrong_type": lambda m: set_value(
                m, ["modules", 0, "topics", 0, "sessions"], ["s001", {}]
            ),
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
                elif name == "map_starts_below_first_level":
                    self.write_session("001.md", valid_session("Controle difuso").replace(
                        "- [conceito] Base", "  - [conceito] Base"
                    ))
                elif name == "map_skips_a_level":
                    self.write_session("001.md", valid_session("Controle difuso").replace(
                        "  - [regra] Aplicação\n    - [excecao] Limite", "    - [excecao] Limite"
                    ))
                elif name == "missing_question_feedback":
                    self.write_session("001.md", valid_session("Controle difuso", question_count=0))
                elif name == "incomplete_question_feedback":
                    self.write_session("001.md", valid_session("Controle difuso").replace(
                        "- Prevenção: manter a revisão.\n", ""
                    ))
                elif name == "missing_aggregate_diagnosis":
                    self.write_session("001.md", valid_session("Controle difuso").replace(
                        "### Diagnóstico agregado\n- Acertos: 20/20 (100%).\n- Padrões de erro: nenhum.\n"
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
            "# Direitos fundamentais\n\n## Mapa mental\n\n- [conceito] Conteúdo em elaboração.\n"
            "    - [excecao] Rascunho com salto de nível.\n"
            "\n### Próxima etapa\n\nConcluir o mapa após a revisão.\n",
        )

        result = self.run_build()

        self.assertEqual(result.returncode, 0, result.stderr)
        html = (self.trail / "apostila.html").read_text(encoding="utf-8")
        in_progress_html = html[html.index('id="sessao-s002"'):]
        self.assertIn("Conteúdo em elaboração.", html)
        self.assertIn("Rascunho com salto de nível.", html)
        self.assertNotIn('<ul class="mind-map">', in_progress_html)
        self.assertIn("<h5>Próxima etapa</h5>", html)
        self.assertNotIn("### Próxima etapa", html)


def set_value(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


def valid_session(title, question_count=20, topic_ids=("controle",)):
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

{feedback_section(question_count, topic_ids)}

## Fontes

- Constituição Federal.

## Próxima revisão

Em sete dias.
"""


if __name__ == "__main__":
    unittest.main()
