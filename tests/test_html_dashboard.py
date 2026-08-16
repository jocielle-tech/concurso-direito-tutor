import unittest
from html.parser import HTMLParser

from scripts.trilha_html import PALETTE, render_html
from scripts.trilha_visual_maps import VisualMapAsset, build_visual_map_specs
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
