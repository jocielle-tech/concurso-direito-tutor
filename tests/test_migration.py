import json
import subprocess
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path

from scripts.trilha_outputs import canonical_session_relative_path
from tests.test_build_trilha import valid_session


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_trilha.py"


def snapshot_tree(root):
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class MigrationTests(unittest.TestCase):
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

    def legacy_manifest(self):
        return {
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
                    "id": "controle", "title": "Controle difuso", "weight": 1,
                    "status": "completed", "sessions": ["s001"],
                }, {
                    "id": "direitos", "title": "Direitos fundamentais", "weight": 1,
                    "status": "not_started", "sessions": ["s002"],
                }],
            }],
            "sessions": [{
                "id": "s001", "title": "Controle difuso", "date": "2026-08-10",
                "status": "completed", "module_id": "constitucional", "topic_ids": ["controle"],
                "file": "sessoes/001.md",
            }, {
                "id": "s002", "title": "Direitos fundamentais", "date": "2026-08-11",
                "status": "not_started", "module_id": "constitucional", "topic_ids": ["direitos"],
                "file": "sessoes/002.md",
            }],
        }

    def write_legacy_trail(self):
        (self.trail / "trilha.json").write_text(
            json.dumps(self.legacy_manifest(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.trail / "sessoes/001.md").write_text(valid_session("Controle difuso"), encoding="utf-8")
        planned = "# Direitos fundamentais\n\nConteúdo pendente.\n"
        (self.trail / "sessoes/002.md").write_text(planned, encoding="utf-8")
        (self.trail / "apostila.md").write_text("apostila legada", encoding="utf-8")
        (self.trail / "apostila.html").write_text("<p>apostila legada</p>", encoding="utf-8")

    def test_check_reports_migration_required_without_writes(self):
        self.write_legacy_trail()
        before = snapshot_tree(self.trail)

        result = self.run_build("--check")

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stderr.strip(), "MIGRATION_REQUIRED")
        self.assertEqual(snapshot_tree(self.trail), before)

    def test_migrate_preserves_sessions_and_creates_single_verified_backup(self):
        self.write_legacy_trail()
        before = snapshot_tree(self.trail)
        original_manifest = self.legacy_manifest()

        result = self.run_build("--migrate")

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.trail / "trilha.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [{key: session[key] for key in session if key != "file"} for session in manifest["sessions"]],
            [{key: session[key] for key in session if key != "file"} for session in original_manifest["sessions"]],
        )
        original_files = {session["id"]: session["file"] for session in original_manifest["sessions"]}
        for session in manifest["sessions"]:
            self.assertTrue(session["file"].startswith("modulos/"))
            self.assertEqual(
                (self.trail / session["file"]).read_bytes(), before[original_files[session["id"]]]
            )
        self.assertFalse((self.trail / "sessoes").exists())
        self.assertTrue((self.trail / "apostila/apostila.md").is_file())
        self.assertTrue((self.trail / "apostila/apostila.html").is_file())
        self.assertFalse((self.trail / "apostila.md").exists())
        self.assertFalse((self.trail / "apostila.html").exists())

        backups = list((self.trail / "backups").glob("migracao-*.zip"))
        self.assertEqual(len(backups), 1)
        with zipfile.ZipFile(backups[0]) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.read("trilha.json"), before["trilha.json"])
            self.assertEqual(archive.read("sessoes/001.md"), before["sessoes/001.md"])
            self.assertEqual(archive.read("sessoes/002.md"), before["sessoes/002.md"])
            self.assertEqual(archive.read("apostila.md"), before["apostila.md"])
            self.assertEqual(archive.read("apostila.html"), before["apostila.html"])

    def test_migration_preserves_numeric_literals_except_for_session_paths(self):
        self.write_legacy_trail()
        manifest_path = self.trail / "trilha.json"
        original = manifest_path.read_text(encoding="utf-8")
        original = original.replace('"weight": 1', '"weight": 0.12345678901234567890123456789', 1)
        original = original.replace('"weight": 1', '"weight": 1e309', 1)
        manifest_path.write_text(original, encoding="utf-8")

        result = self.run_build("--migrate")

        self.assertEqual(result.returncode, 0, result.stderr)
        expected = original.replace(
            '"file": "sessoes/001.md"',
            '"file": "modulos/01-direito-constitucional/topicos/01-controle-difuso/sessoes/001-controle-difuso.md"',
        ).replace(
            '"file": "sessoes/002.md"',
            '"file": "modulos/01-direito-constitucional/topicos/02-direitos-fundamentais/sessoes/002-direitos-fundamentais.md"',
        )
        self.assertEqual(manifest_path.read_text(encoding="utf-8"), expected)
        self.assertEqual(self.run_build("--check").returncode, 0)

    def test_build_failure_rolls_back_without_writing_the_original_tree(self):
        from scripts.trilha_migration import migrate_legacy_trail

        self.write_legacy_trail()
        before = snapshot_tree(self.trail)
        manifest = self.legacy_manifest()

        def build_failure(_stage):
            raise OSError("staged build failed")

        with self.assertRaisesRegex(OSError, "staged build failed"):
            migrate_legacy_trail(
                self.trail,
                build_failure,
                canonical_session_relative_path,
                datetime(2026, 8, 15, 12, 30, 45),
            )

        self.assertEqual(snapshot_tree(self.trail), before)
        self.assertFalse(list(self.trail.parent.glob(".trilha.migration-*")))
        self.assertEqual(manifest, self.legacy_manifest())

    def test_second_migration_is_idempotent_and_does_not_create_another_backup(self):
        self.write_legacy_trail()
        first = self.run_build("--migrate")
        self.assertEqual(first.returncode, 0, first.stderr)
        before = snapshot_tree(self.trail)

        second = self.run_build("--migrate")

        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(snapshot_tree(self.trail), before)
        self.assertEqual(len(list((self.trail / "backups").glob("migracao-*.zip"))), 1)

    def test_preexisting_swap_path_is_rejected_without_overwriting_it(self):
        from scripts.trilha_migration import migrate_legacy_trail, swap_path_for

        self.write_legacy_trail()
        before = snapshot_tree(self.trail)
        now = datetime(2026, 8, 15, 12, 30, 45)
        swap = swap_path_for(self.trail, now)
        swap.mkdir()
        marker = swap / "do-not-overwrite"
        marker.write_text("keep", encoding="utf-8")

        with self.assertRaisesRegex(OSError, "caminho de troca já existe"):
            migrate_legacy_trail(self.trail, lambda _stage: None, canonical_session_relative_path, now)

        self.assertEqual(snapshot_tree(self.trail), before)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_preexisting_backup_timestamp_is_rejected_without_overwriting_it(self):
        from scripts.trilha_migration import migrate_legacy_trail

        self.write_legacy_trail()
        now = datetime(2026, 8, 15, 12, 30, 45)
        backup = self.trail / "backups/migracao-20260815-123045.zip"
        backup.parent.mkdir()
        backup.write_bytes(b"previous backup bytes")
        before = snapshot_tree(self.trail)

        with self.assertRaisesRegex(OSError, "backup de migração já existe"):
            migrate_legacy_trail(self.trail, lambda _stage: None, canonical_session_relative_path, now)

        self.assertEqual(snapshot_tree(self.trail), before)
        self.assertEqual(backup.read_bytes(), b"previous backup bytes")


if __name__ == "__main__":
    unittest.main()
