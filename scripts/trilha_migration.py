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
    if backup.exists():
        raise OSError(f"backup de migração já existe: {backup.name}")
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


def _skip_whitespace(document, index):
    while index < len(document) and document[index] in " \t\r\n":
        index += 1
    return index


def _scan_string(document, index):
    if index >= len(document) or document[index] != '"':
        raise OSError("JSON de migração inválido")
    try:
        return json.decoder.scanstring(document, index + 1, True)
    except ValueError as exc:
        raise OSError("JSON de migração inválido") from exc


def _skip_json_value(document, index):
    index = _skip_whitespace(document, index)
    if index >= len(document):
        raise OSError("JSON de migração inválido")
    token = document[index]
    if token == '"':
        _value, index = _scan_string(document, index)
        return index
    if token == "{":
        index = _skip_whitespace(document, index + 1)
        if index < len(document) and document[index] == "}":
            return index + 1
        while True:
            _key, index = _scan_string(document, index)
            index = _skip_whitespace(document, index)
            if index >= len(document) or document[index] != ":":
                raise OSError("JSON de migração inválido")
            index = _skip_json_value(document, index + 1)
            index = _skip_whitespace(document, index)
            if index >= len(document) or document[index] not in ",}":
                raise OSError("JSON de migração inválido")
            if document[index] == "}":
                return index + 1
            index = _skip_whitespace(document, index + 1)
    if token == "[":
        index = _skip_whitespace(document, index + 1)
        if index < len(document) and document[index] == "]":
            return index + 1
        while True:
            index = _skip_json_value(document, index)
            index = _skip_whitespace(document, index)
            if index >= len(document) or document[index] not in ",]":
                raise OSError("JSON de migração inválido")
            if document[index] == "]":
                return index + 1
            index = _skip_whitespace(document, index + 1)
    end = index
    while end < len(document) and document[end] not in " \t\r\n,]}":
        end += 1
    if end == index:
        raise OSError("JSON de migração inválido")
    return end


def _session_file_spans(document, index):
    index = _skip_whitespace(document, index)
    if index >= len(document) or document[index] != "[":
        raise OSError("sessions de migração inválidas")
    spans = []
    index = _skip_whitespace(document, index + 1)
    while index < len(document) and document[index] != "]":
        if document[index] != "{":
            raise OSError("sessions de migração inválidas")
        index = _skip_whitespace(document, index + 1)
        found_file = False
        while index < len(document) and document[index] != "}":
            key, index = _scan_string(document, index)
            index = _skip_whitespace(document, index)
            if index >= len(document) or document[index] != ":":
                raise OSError("JSON de migração inválido")
            value_start = _skip_whitespace(document, index + 1)
            value_end = _skip_json_value(document, value_start)
            if key == "file":
                if found_file or value_start >= len(document) or document[value_start] != '"':
                    raise OSError("arquivo da sessão inválido na migração")
                spans.append((value_start, value_end))
                found_file = True
            index = _skip_whitespace(document, value_end)
            if index >= len(document) or document[index] not in ",}":
                raise OSError("JSON de migração inválido")
            if document[index] == ",":
                index = _skip_whitespace(document, index + 1)
        if not found_file or index >= len(document):
            raise OSError("arquivo da sessão inválido na migração")
        index = _skip_whitespace(document, index + 1)
        if index >= len(document) or document[index] not in ",]":
            raise OSError("sessions de migração inválidas")
        if document[index] == ",":
            index = _skip_whitespace(document, index + 1)
    if index >= len(document):
        raise OSError("sessions de migração inválidas")
    return spans


def _rewrite_session_files(document, files):
    """Replace only top-level ``sessions[*].file`` JSON string tokens."""
    index = _skip_whitespace(document, 0)
    if index >= len(document) or document[index] != "{":
        raise OSError("JSON de migração inválido")
    index = _skip_whitespace(document, index + 1)
    spans = None
    while index < len(document) and document[index] != "}":
        key, index = _scan_string(document, index)
        index = _skip_whitespace(document, index)
        if index >= len(document) or document[index] != ":":
            raise OSError("JSON de migração inválido")
        value_start = _skip_whitespace(document, index + 1)
        if key == "sessions":
            if spans is not None:
                raise OSError("sessions de migração duplicadas")
            spans = _session_file_spans(document, value_start)
            value_end = _skip_json_value(document, value_start)
        else:
            value_end = _skip_json_value(document, value_start)
        index = _skip_whitespace(document, value_end)
        if index >= len(document) or document[index] not in ",}":
            raise OSError("JSON de migração inválido")
        if document[index] == ",":
            index = _skip_whitespace(document, index + 1)
    if spans is None or len(spans) != len(files):
        raise OSError("sessions de migração inválidas")
    for (start, end), value in reversed(list(zip(spans, files))):
        document = document[:start] + json.dumps(value, ensure_ascii=False) + document[end:]
    return document


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
    backup_name = f"migracao-{now:%Y%m%d-%H%M%S}.zip"
    if (trail / "backups" / backup_name).exists():
        raise OSError(f"backup de migração já existe: {backup_name}")

    stage = Path(tempfile.mkdtemp(prefix=f".{trail.name}.migration-stage-", dir=trail.parent))
    stage.rmdir()
    original_moved = False
    promoted = False
    try:
        shutil.copytree(trail, stage)
        manifest_path = stage / "trilha.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        backup = stage / "backups" / backup_name
        _archive_original(trail, backup)

        legacy_paths, canonical_files = [], []
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
            canonical_files.append(session["file"])
            if old_relative.parts[:1] == ("sessoes",):
                legacy_paths.append(old_relative)
        manifest_path.write_text(_rewrite_session_files(manifest_text, canonical_files), encoding="utf-8")
        _remove_legacy_sources(stage, legacy_paths)
        for legacy_output in ("apostila.md", "apostila.html"):
            (stage / legacy_output).unlink(missing_ok=True)
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
