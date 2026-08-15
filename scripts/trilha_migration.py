"""Safely migrate legacy session paths into the canonical hybrid layout."""

import json
import shutil
import tempfile
import zipfile
from pathlib import Path


def is_legacy_trail(trail, manifest):
    """Return whether any session still uses the legacy ``sessoes/`` root."""
    del trail
    return any(Path(session["file"]).parts[:1] == ("sessoes",) for session in manifest["sessions"])


def swap_path_for(trail, now):
    """Return the recovery sibling reserved for one migration promotion."""
    trail = Path(trail)
    return trail.with_name(f".{trail.name}.migration-original-{now:%Y%m%d-%H%M%S}")


def _contained_file(root, relative):
    relative = Path(relative)
    if relative.is_absolute():
        raise OSError("caminho de migração deve ser relativo")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise OSError("caminho de migração deve estar contido na trilha") from exc
    if not candidate.is_file():
        raise OSError(f"arquivo da sessão não encontrado: {relative.as_posix()}")
    return candidate


def _contained_destination(root, relative):
    relative = Path(relative)
    if relative.is_absolute():
        raise OSError("caminho canônico deve ser relativo")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise OSError("caminho canônico deve estar contido na trilha") from exc
    return candidate


def _archive_original(original, backup):
    backup.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(path for path in original.rglob("*") if path.is_file()):
            archive.write(source, source.relative_to(original).as_posix())
    with zipfile.ZipFile(backup) as archive:
        bad_member = archive.testzip()
    if bad_member is not None:
        raise OSError(f"backup de migração corrompido: {bad_member}")


def _remove_legacy_sources(stage, legacy_paths):
    for relative in legacy_paths:
        source = _contained_file(stage, relative)
        source.unlink()
        parent = source.parent
        legacy_root = (stage / "sessoes").resolve()
        while parent != legacy_root.parent and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent


def migrate_legacy_trail(trail, build_staged, canonical_path, now):
    """Migrate in a sibling copy, validate it, then promote it with recovery.

    ``build_staged`` must validate and build a complete staged trail.  The
    original trail remains untouched until the two directory renames below.
    """
    trail = Path(trail).resolve()
    if callable(now):
        now = now()
    swap_path = swap_path_for(trail, now)
    if swap_path.exists():
        raise OSError(f"caminho de troca já existe: {swap_path.name}")

    stage = Path(tempfile.mkdtemp(prefix=f".{trail.name}.migration-stage-", dir=trail.parent))
    stage.rmdir()
    original_moved = False
    promoted = False
    try:
        shutil.copytree(trail, stage)
        manifest_path = stage / "trilha.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        backup = stage / "backups" / f"migracao-{now:%Y%m%d-%H%M%S}.zip"
        _archive_original(trail, backup)

        legacy_paths = []
        for session in manifest["sessions"]:
            old_relative = Path(session["file"])
            source = _contained_file(stage, old_relative)
            new_relative = Path(canonical_path(manifest, session))
            destination = _contained_destination(stage, new_relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source != destination:
                shutil.copyfile(source, destination)
                if source.read_bytes() != destination.read_bytes():
                    raise OSError(f"não foi possível copiar sessão: {old_relative.as_posix()}")
            session["file"] = new_relative.as_posix()
            if old_relative.parts[:1] == ("sessoes",):
                legacy_paths.append(old_relative)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _remove_legacy_sources(stage, legacy_paths)
        build_staged(stage)

        trail.replace(swap_path)
        original_moved = True
        try:
            stage.replace(trail)
            promoted = True
        except Exception:
            swap_path.replace(trail)
            original_moved = False
            raise
        shutil.rmtree(swap_path)
    finally:
        if stage.exists() and not promoted:
            shutil.rmtree(stage, ignore_errors=True)
        if original_moved and not trail.exists() and swap_path.exists():
            swap_path.replace(trail)
