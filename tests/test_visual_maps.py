import copy
import json
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts.trilha_visual_maps import build_visual_map_specs, load_visual_map_assets
from tests.test_build_trilha import valid_session
from tests.trilha_support import png_bytes


ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts" / "prepare_visual_map.py"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def snapshot_tree(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*") if path.is_file()
    }


def algorithm_session(title, algorithm_lines):
    session = valid_session(title)
    start = session.index("## Mapa mental\n\n") + len("## Mapa mental\n\n")
    end = session.index("\n## Questões e feedback", start)
    return session[:start] + "\n".join(algorithm_lines) + session[end:]


def png_chunk(kind, payload):
    return (
        struct.pack(">I", len(payload)) + kind + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def png_with_chunks(*chunks):
    return PNG_SIGNATURE + b"".join(chunks)


class VisualMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trail = Path(self.tmp.name) / "trilha"
        self.trail.mkdir()
        self.manifest = {
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
                "file": "modulos/01/sessoes/001.md",
            }],
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
        }
        self.write_trail()

    def tearDown(self):
        self.tmp.cleanup()

    def write_trail(self):
        (self.trail / "trilha.json").write_text(
            json.dumps(self.manifest, ensure_ascii=False), encoding="utf-8"
        )
        for session in self.manifest["sessions"]:
            path = self.trail / session["file"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.session_files[session["id"]], encoding="utf-8")

    def test_completed_topic_spec_aggregates_sessions_in_manifest_order(self):
        second = copy.deepcopy(self.manifest["sessions"][0])
        second.update(id="s002", title="Controle difuso — continuação", file="modulos/01/sessoes/002.md")
        self.manifest["sessions"].append(second)
        self.manifest["modules"][0]["topics"][0]["sessions"].append("s002")
        self.session_files["s002"] = algorithm_session("Controle difuso — continuação", (
            "ENTRADA: confirmar a legitimidade.",
            "RESULTADO: prosseguir com a decisão.",
        ))

        specs = build_visual_map_specs(self.manifest, self.session_files)

        spec = specs["controle"]
        self.assertEqual(spec.topic_id, "controle")
        self.assertEqual(spec.algorithm_lines[0], "ENTRADA: existe caso concreto?")
        self.assertEqual(spec.algorithm_lines[-1], "RESULTADO: prosseguir com a decisão.")
        self.assertIn("Use case: infographic-diagram", spec.prompt)
        self.assertIn("Text (verbatim):", spec.prompt)
        self.assertRegex(
            spec.expected_path.as_posix(),
            r"^assets/mapas/controle-[0-9a-f]{8}/[0-9a-f]{64}\.png$",
        )

    def test_incomplete_topic_has_no_visual_map_spec(self):
        self.manifest["modules"][0]["topics"][0]["status"] = "in_progress"

        self.assertEqual(build_visual_map_specs(self.manifest, self.session_files), {})

    def test_hash_changes_only_when_visual_source_or_template_changes(self):
        first = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        renamed = copy.deepcopy(self.manifest)
        renamed["modules"][0]["title"] = "Título novo"
        renamed["modules"][0]["topics"][0]["title"] = "Tópico novo"

        same = build_visual_map_specs(renamed, self.session_files)["controle"]
        changed_files = dict(self.session_files)
        changed_files["s001"] = changed_files["s001"].replace("SE SIM", "SE PRESENTE")
        changed = build_visual_map_specs(self.manifest, changed_files)["controle"]

        self.assertEqual(first.source_hash, same.source_hash)
        self.assertNotEqual(first.source_hash, changed.source_hash)

    def test_asset_loader_reports_ready_missing_and_invalid(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]

        self.assertEqual(load_visual_map_assets(self.trail, {"controle": spec})["controle"].status, "missing")
        target = self.trail / spec.expected_path
        target.parent.mkdir(parents=True)
        target.write_bytes(png_bytes())
        self.assertEqual(load_visual_map_assets(self.trail, {"controle": spec})["controle"].status, "ready")
        target.write_bytes(png_bytes(1024, 1024))

        invalid = load_visual_map_assets(self.trail, {"controle": spec})["controle"]
        self.assertEqual(invalid.status, "invalid")
        self.assertIn("proporção", invalid.error)

    def test_loader_rejects_invalid_png_signature_truncated_header_and_portrait(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        target = self.trail / spec.expected_path
        target.parent.mkdir(parents=True)
        cases = {
            "assinatura": b"not-a-png",
            "truncado": b"\x89PNG\r\n\x1a\n" + b"\x00\x00",
            "retrato": png_bytes(1024, 1536),
        }
        for label, content in cases.items():
            with self.subTest(label=label):
                target.write_bytes(content)
                asset = load_visual_map_assets(self.trail, {"controle": spec})["controle"]
                self.assertEqual(asset.status, "invalid")
                self.assertIsNotNone(asset.error)

    def test_loader_rejects_png_without_required_end_chunk(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        target = self.trail / spec.expected_path
        target.parent.mkdir(parents=True)
        target.write_bytes(png_bytes()[:-12])

        asset = load_visual_map_assets(self.trail, {"controle": spec})["controle"]

        self.assertEqual(asset.status, "invalid")
        self.assertIn("IEND", asset.error)

    def test_loader_rejects_invalid_png_chunk_order_and_empty_image_data(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        target = self.trail / spec.expected_path
        target.parent.mkdir(parents=True)
        header = struct.pack(">IIBBBBB", 1536, 1024, 8, 2, 0, 0, 0)
        cases = {
            "ihdr_duplicado": png_with_chunks(
                png_chunk(b"IHDR", header), png_chunk(b"IHDR", header),
                png_chunk(b"IDAT", b"x"), png_chunk(b"IEND", b""),
            ),
            "idat_vazio": png_with_chunks(
                png_chunk(b"IHDR", header), png_chunk(b"IDAT", b""), png_chunk(b"IEND", b""),
            ),
            "idat_interrompido": png_with_chunks(
                png_chunk(b"IHDR", header), png_chunk(b"IDAT", b"x"),
                png_chunk(b"tEXt", b"note\x00value"), png_chunk(b"IDAT", b"y"),
                png_chunk(b"IEND", b""),
            ),
        }
        for label, content in cases.items():
            with self.subTest(label=label):
                target.write_bytes(content)
                asset = load_visual_map_assets(self.trail, {"controle": spec})["controle"]
                self.assertEqual(asset.status, "invalid")
                self.assertIsNotNone(asset.error)

    def test_loader_accepts_valid_ancillary_chunk_after_image_data(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        target = self.trail / spec.expected_path
        target.parent.mkdir(parents=True)
        valid_png = png_bytes()
        target.write_bytes(valid_png[:-12] + png_chunk(b"tEXt", b"author\x00Tutor") + valid_png[-12:])

        asset = load_visual_map_assets(self.trail, {"controle": spec})["controle"]

        self.assertEqual(asset.status, "ready")
        self.assertIsNotNone(asset.png_bytes)

    def test_loader_rejects_path_outside_trail(self):
        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]
        escaped = type(spec)(
            topic_id=spec.topic_id,
            source_hash=spec.source_hash,
            expected_path=Path("../escape.png"),
            prompt=spec.prompt,
            alt_text=spec.alt_text,
            algorithm_lines=spec.algorithm_lines,
        )

        asset = load_visual_map_assets(self.trail, {"controle": escaped})["controle"]

        self.assertEqual(asset.status, "invalid")
        self.assertIn("contido", asset.error)

    def test_legacy_hierarchical_map_is_accepted_as_algorithm_source(self):
        self.session_files["s001"] = valid_session("Controle difuso")

        spec = build_visual_map_specs(self.manifest, self.session_files)["controle"]

        self.assertIn("- [conceito] Base", spec.algorithm_lines)
        self.assertIn("- [regra] Aplicação", spec.algorithm_lines)

    def test_cli_emits_machine_readable_native_image_request_without_writes(self):
        self.session_files["s001"] = valid_session("Controle difuso")
        self.write_trail()
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

    def test_cli_rejects_unknown_or_incomplete_topic(self):
        self.session_files["s001"] = valid_session("Controle difuso")
        self.write_trail()
        for topic in ("inexistente", "controle"):
            if topic == "controle":
                self.manifest["modules"][0]["topics"][0]["status"] = "in_progress"
                self.write_trail()
            with self.subTest(topic=topic):
                result = subprocess.run(
                    ["python3", str(PREPARE), str(self.trail), "--topic", topic],
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("tópico não concluído ou sem mapa mental", result.stderr)


if __name__ == "__main__":
    unittest.main()
