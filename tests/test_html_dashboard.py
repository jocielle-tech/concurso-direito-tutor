import unittest
from html.parser import HTMLParser

from scripts.trilha_html import FOCUS_COLORS, HERO_COLORS, PALETTE, anchor_id, render_html
from scripts.trilha_visual_maps import VisualMapAsset, build_visual_map_specs
from tests.test_build_trilha import detailed_session
from tests.test_visual_maps import algorithm_session
from tests.trilha_support import png_bytes


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.fragment_links = []
        self.controls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if values.get("href", "").startswith("#"):
            self.fragment_links.append(values["href"][1:])
        for attribute in ("aria-controls", "aria-labelledby"):
            if attribute in values:
                self.controls.extend(values[attribute].split())


def contrast_ratio(first, second):
    def luminance(value):
        channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
        linear = [channel / 12.92 if channel <= .04045 else ((channel + .055) / 1.055) ** 2.4
                  for channel in channels]
        return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]

    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


class HtmlDashboardTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "title": "Trilha de Direito Constitucional",
            "recalibrated": False,
            "modules": [{
                "id": "constitucional", "title": "Direito Constitucional", "topics": [
                    {"id": "controle", "title": "Controle difuso", "weight": 1,
                     "status": "completed", "sessions": ["s001"]},
                    {"id": "direitos", "title": "Direitos fundamentais", "weight": 3,
                     "status": "not_started", "sessions": ["s002"]},
                ],
            }],
            "sessions": [
                {"id": "s001", "title": "Controle difuso", "date": "2026-08-10",
                 "status": "completed", "module_id": "constitucional", "topic_ids": ["controle"]},
                {"id": "s002", "title": "Direitos fundamentais", "date": "2026-08-11",
                 "status": "not_started", "module_id": "constitucional", "topic_ids": ["direitos"]},
            ],
        }
        self.session_files = {
            "s001": algorithm_session("Controle difuso", (
                "ENTRADA: existe caso concreto?",
                "SE SIM: identificar a controvérsia constitucional.",
                "ENTÃO: aplicar o controle difuso.",
                "SENÃO: encerrar a análise.",
                "RESULTADO: decisão fundamentada.",
                "ALERTA: observar a reserva de plenário.",
            )),
            "s002": "# Direitos fundamentais\n\n## Conteúdo principal\n\nConteúdo pendente.\n",
        }

    def ready_visual_fixture(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        return self.manifest, self.session_files, {
            "controle": VisualMapAsset(spec, "ready", png_bytes(), None),
        }

    def unavailable_visual_fixture(self, status):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        return self.manifest, self.session_files, {
            "controle": VisualMapAsset(spec, status, None, "imagem indisponível"),
        }

    def build_html(self):
        manifest, session_files, assets = self.ready_visual_fixture()
        return render_html(manifest, session_files, assets)

    def test_ready_visual_map_is_embedded_in_self_contained_dashboard(self):
        html = self.build_html()

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

    def test_theory_briefing_has_visual_hierarchy_and_precedes_questions(self):
        self.session_files["s001"] = detailed_session("Controle difuso")

        html = render_html(self.manifest, self.session_files, {})

        self.assertIn('class="study-card theory-briefing"', html)
        self.assertIn(
            '<h5 class="theory-section-title">Objetivos de aprendizagem</h5>', html
        )
        self.assertLess(
            html.index('class="study-card theory-briefing"'),
            html.index('class="question-card"'),
        )

    def test_missing_or_invalid_image_uses_algorithmic_html_fallback(self):
        for status in ("missing", "invalid"):
            with self.subTest(status=status):
                manifest, session_files, assets = self.unavailable_visual_fixture(status)
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

    def test_every_local_control_has_a_unique_target_and_palette_is_aa(self):
        html = self.build_html()
        parser = DocumentParser()
        parser.feed(html)

        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        targets = set(parser.ids)
        self.assertTrue(set(parser.fragment_links) <= targets)
        self.assertTrue(set(parser.controls) <= targets)
        for foreground, background in ((PALETTE["ink"], PALETTE["surface"]),
                                       (PALETTE["muted"], PALETTE["surface"])):
            self.assertGreaterEqual(contrast_ratio(foreground, background), 4.5)

    def test_missing_asset_entry_uses_encoded_algorithm_fallback_target(self):
        unusual_id = "controle especial/ação"
        topic = self.manifest["modules"][0]["topics"][0]
        topic["id"] = unusual_id
        self.manifest["sessions"][0]["topic_ids"] = [unusual_id]

        html = render_html(self.manifest, self.session_files, {})
        target = anchor_id("algorithm", unusual_id)
        parser = DocumentParser()
        parser.feed(html)

        self.assertIn(f'id="{target}"', html)
        self.assertIn('class="algorithm-flow"', html)
        self.assertIn("ENTRADA: existe caso concreto?", html)
        self.assertEqual(parser.ids.count(target), 1)
        self.assertNotIn(f'id="algorithm-{unusual_id}"', html)

    def test_hero_and_focus_palette_meet_required_contrast(self):
        html = self.build_html()
        for background in HERO_COLORS.values():
            self.assertGreaterEqual(contrast_ratio("#FFFFFF", background), 4.5)
            self.assertGreaterEqual(contrast_ratio(FOCUS_COLORS["hero"], background), 3)
        for background in (PALETTE["surface"], PALETTE["canvas"]):
            self.assertGreaterEqual(contrast_ratio(FOCUS_COLORS["surface"], background), 3)
        self.assertIn(
            f"background:linear-gradient(122deg,{HERO_COLORS['violet']},{HERO_COLORS['blue']})",
            html,
        )
        self.assertIn(f"outline:3px solid {FOCUS_COLORS['surface']}", html)
        self.assertIn(f"outline-color:{FOCUS_COLORS['hero']}", html)

    def test_global_module_and_topic_progress_are_accessible_and_stable(self):
        second_module = {
            "id": "administrativo", "title": "Direito Administrativo", "topics": [{
                "id": "atos", "title": "Atos administrativos", "weight": 2,
                "status": "in_progress", "sessions": [],
            }],
        }
        self.manifest["modules"].append(second_module)

        html = render_html(self.manifest, self.session_files, {})

        expected = (
            ('global', '17'),
            ('constitucional', '25'),
            ('administrativo', '0'),
            ('controle', '100'),
            ('direitos', '0'),
            ('atos', '0'),
        )
        for marker, value in expected:
            with self.subTest(marker=marker):
                self.assertRegex(
                    html,
                    rf'data-progress-(?:global|module|topic)="{marker}"[^>]*role="progressbar"'
                    rf'[^>]*aria-valuemin="0"[^>]*aria-valuemax="100"[^>]*aria-valuenow="{value}"',
                )
        self.assertIn("Progresso do módulo", html)
        self.assertIn("Progresso do tópico", html)

    def test_module_and_topic_progress_labels_include_distinct_escaped_titles(self):
        self.manifest["modules"][0]["title"] = 'Módulo <A> & "um"'
        self.manifest["modules"][0]["topics"][0]["title"] = 'Tópico <A> & "um"'
        self.manifest["modules"][0]["topics"][1]["title"] = "Tópico B & especial"
        self.manifest["modules"].append({
            "id": "penal", "title": "Módulo B > dois", "topics": [{
                "id": "crimes", "title": 'Tópico C: "três"', "weight": 1,
                "status": "not_started", "sessions": [],
            }],
        })

        html = render_html(self.manifest, self.session_files, {})

        self.assertIn(
            'aria-label="Progresso do módulo Módulo &lt;A&gt; &amp; &quot;um&quot;"', html
        )
        self.assertIn(
            'aria-label="Progresso do tópico Tópico &lt;A&gt; &amp; &quot;um&quot;"', html
        )
        self.assertIn('aria-label="Progresso do tópico Tópico B &amp; especial"', html)
        self.assertIn('aria-label="Progresso do módulo Módulo B &gt; dois"', html)
        self.assertIn('aria-label="Progresso do tópico Tópico C: &quot;três&quot;"', html)
