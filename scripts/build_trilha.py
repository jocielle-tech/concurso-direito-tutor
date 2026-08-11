#!/usr/bin/env python3
"""Validate a trail manifest and deterministically render its study handout."""

import argparse
import html
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse


SOURCES = {"provisional", "edital"}
STATUSES = {"not_started", "in_progress", "completed"}
MAP_CATEGORIES = {
    "conceito": ("Conceito", "#2563EB"),
    "regra": ("Regra", "#16A34A"),
    "excecao": ("Exceção", "#D97706"),
    "pegadinha": ("Pegadinha", "#DC2626"),
    "jurisprudencia": ("Jurisprudência", "#7C3AED"),
}
REQUIRED_SECTIONS = (
    "Conteúdo principal", "Resumo estratégico", "Mapa mental",
    "Questões e feedback", "Fontes", "Próxima revisão",
)
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MAP_ITEM = re.compile(r"^(\s*)[-*]\s+\[([^]]+)\]\s+.+$")


class ValidationError(ValueError):
    pass


def require_mapping(value, label):
    if not isinstance(value, dict):
        raise ValidationError(f"{label} deve ser um objeto")
    return value


def require_keys(value, keys, label):
    for key in keys:
        if key not in value:
            raise ValidationError(f"{label}: seção obrigatória ausente: {key}")


def unique_ids(items, label):
    ids = []
    for item in items:
        require_mapping(item, label)
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise ValidationError(f"{label}: id inválido")
        ids.append(item_id)
    if len(ids) != len(set(ids)):
        raise ValidationError(f"{label}: IDs duplicados")
    return set(ids)


def session_sections(text, session_title):
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    sections = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections[heading.group(1)] = text[heading.end():end].strip()
    expected_heading = f"# {session_title}"
    if not text.startswith(expected_heading + "\n"):
        raise ValidationError(f"sessão '{session_title}': título deve ser '{expected_heading}'")
    return sections


def validate_completed_session(text, session):
    sections = session_sections(text, session["title"])
    missing = [section for section in REQUIRED_SECTIONS if section not in sections]
    if missing:
        raise ValidationError(
            f"sessão '{session['id']}': seção obrigatória ausente: {', '.join(missing)}"
        )
    summary_items = re.findall(r"^\s*[-*]\s+.+$", sections["Resumo estratégico"], re.MULTILINE)
    if not 5 <= len(summary_items) <= 8:
        raise ValidationError(f"sessão '{session['id']}': resumo deve ter 5–8 itens")
    map_lines = [line for line in sections["Mapa mental"].splitlines() if line.strip()]
    if not map_lines:
        raise ValidationError(f"sessão '{session['id']}': mapa mental vazio")
    for line in map_lines:
        match = MAP_ITEM.match(line)
        if not match:
            raise ValidationError(f"sessão '{session['id']}': item de mapa inválido")
        if len(match.group(1).expandtabs(2)) // 2 >= 3:
            raise ValidationError(f"sessão '{session['id']}': mapa tem mais de três níveis")
        if match.group(2) not in MAP_CATEGORIES:
            raise ValidationError(f"sessão '{session['id']}': categoria de mapa inválida")


def inside_trail(trail, relative_path):
    if not isinstance(relative_path, str) or not relative_path:
        raise ValidationError("caminho da sessão inválido")
    candidate = (trail / relative_path).resolve()
    try:
        candidate.relative_to(trail.resolve())
    except ValueError as exc:
        raise ValidationError("caminho da sessão deve estar contido na trilha") from exc
    if not candidate.is_file():
        raise ValidationError(f"arquivo da sessão não encontrado: {relative_path}")
    return candidate


def load_and_validate(trail):
    manifest_file = trail / "trilha.json"
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError("trilha.json não encontrado") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"JSON inválido: {exc.msg}") from exc
    require_mapping(manifest, "manifesto")
    require_keys(manifest, (
        "schema_version", "title", "slug", "source", "exam", "banca", "recalibrated",
        "modules", "sessions",
    ), "manifesto")
    if manifest["schema_version"] != 1:
        raise ValidationError("schema_version deve ser 1")
    if not isinstance(manifest["title"], str) or not isinstance(manifest["slug"], str):
        raise ValidationError("title e slug devem ser texto")
    if manifest["source"] not in SOURCES:
        raise ValidationError("source inválido")
    if not isinstance(manifest["recalibrated"], bool):
        raise ValidationError("recalibrated deve ser booleano")
    if not isinstance(manifest["modules"], list) or not isinstance(manifest["sessions"], list):
        raise ValidationError("modules e sessions devem ser listas")

    module_ids = unique_ids(manifest["modules"], "módulos")
    topic_ids, topic_modules, topic_sessions = set(), {}, {}
    for module in manifest["modules"]:
        require_keys(module, ("id", "title", "topics"), "módulo")
        if not isinstance(module["title"], str) or not isinstance(module["topics"], list):
            raise ValidationError("módulo inválido")
        for topic in module["topics"]:
            require_mapping(topic, "tópico")
            require_keys(topic, ("id", "title", "weight", "status", "sessions"), "tópico")
            topic_id = topic["id"]
            if not isinstance(topic_id, str) or not topic_id or topic_id in topic_ids:
                raise ValidationError("tópicos: IDs duplicados ou inválidos")
            if (not isinstance(topic["weight"], (int, float)) or isinstance(topic["weight"], bool)
                    or topic["weight"] <= 0):
                raise ValidationError("peso deve ser numérico positivo")
            if topic["status"] not in STATUSES or not isinstance(topic["sessions"], list):
                raise ValidationError("tópico inválido")
            topic_ids.add(topic_id)
            topic_modules[topic_id] = module["id"]
            topic_sessions[topic_id] = topic["sessions"]

    session_ids = unique_ids(manifest["sessions"], "sessões")
    session_files = {}
    for session in manifest["sessions"]:
        require_keys(session, ("id", "title", "date", "status", "module_id", "topic_ids", "file"), "sessão")
        if (not isinstance(session["title"], str) or not isinstance(session["date"], str)
                or session["status"] not in STATUSES or session["module_id"] not in module_ids
                or not isinstance(session["topic_ids"], list)):
            raise ValidationError("sessão inválida")
        if not session["topic_ids"] or len(session["topic_ids"]) != len(set(session["topic_ids"])):
            raise ValidationError("referências de tópicos inválidas")
        for topic_id in session["topic_ids"]:
            if topic_id not in topic_ids or topic_modules[topic_id] != session["module_id"]:
                raise ValidationError("referência de tópico inexistente ou fora do módulo")
            if session["id"] not in topic_sessions[topic_id]:
                raise ValidationError("referência de sessão ausente no tópico")
        path = inside_trail(trail, session["file"])
        text = path.read_text(encoding="utf-8")
        if session["status"] == "completed":
            validate_completed_session(text, session)
        session_files[session["id"]] = text
    for topic_id, ids in topic_sessions.items():
        if len(ids) != len(set(ids)) or any(item not in session_ids for item in ids):
            raise ValidationError("referência de sessão inexistente")
    return manifest, session_files


def progress(topics):
    total = sum(topic["weight"] for topic in topics)
    completed = sum(topic["weight"] for topic in topics if topic["status"] == "completed")
    return round(completed * 100 / total) if total else 0


def all_topics(manifest):
    return [topic for module in manifest["modules"] for topic in module["topics"]]


def markdown_document(manifest, session_files):
    overall = progress(all_topics(manifest))
    lines = [f"# {manifest['title']}", "", f"Progresso global: {overall}%", f"Régua de progresso: {overall}% {'█' * (overall // 10)}{'░' * (10 - overall // 10)}", ""]
    if manifest["recalibrated"] and manifest["source"] == "edital":
        lines.extend(["**Trilha recalibrada**", ""])
    lines.extend(["## Índice", ""])
    for module in manifest["modules"]:
        lines.append(f"- {module['title']}")
        for session in [s for s in manifest["sessions"] if s["module_id"] == module["id"]]:
            lines.append(f"  - {session['title']} ({session['date']})")
    lines.extend(["", "## Progresso por módulo", ""])
    for module in manifest["modules"]:
        lines.append(f"- {module['title']}: {progress(module['topics'])}%")
    lines.extend(["", "## Legenda do mapa mental", ""])
    for _, (label, color) in MAP_CATEGORIES.items():
        lines.append(f"- {label} ({color})")
    for session in manifest["sessions"]:
        lines.extend(["", "---", "", session_files[session["id"]].rstrip(), ""])
    return "\n".join(lines).rstrip() + "\n"


def safe_inline(text):
    escaped = html.escape(text, quote=True)
    def link(match):
        label, url = match.group(1), match.group(2).strip()
        scheme = urlparse(url).scheme.lower()
        if scheme and scheme not in {"http", "https", "mailto"}:
            return label
        return f'<a href="{html.escape(url, quote=True)}">{label}</a>'
    return LINK.sub(link, escaped)


def html_session(text):
    blocks = []
    for line in text.splitlines():
        if line.startswith("# "):
            blocks.append(f"<h2>{safe_inline(line[2:])}</h2>")
        elif line.startswith("## "):
            blocks.append(f"<h3>{safe_inline(line[3:])}</h3>")
        elif line.strip().startswith(("- ", "* ")):
            item = line.strip()[2:]
            category = re.match(r"\[([^]]+)\]\s*(.*)", item)
            if category and category.group(1) in MAP_CATEGORIES:
                label, color = MAP_CATEGORIES[category.group(1)]
                blocks.append(f'<p class="map-item" style="border-color:{color}"><strong>{label}:</strong> {safe_inline(category.group(2))}</p>')
            else:
                blocks.append(f"<p>• {safe_inline(item)}</p>")
        elif line.strip():
            blocks.append(f"<p>{safe_inline(line.strip())}</p>")
    return "\n".join(blocks)


def html_document(manifest, session_files):
    overall = progress(all_topics(manifest))
    index = "".join(
        f"<li>{html.escape(module['title'])}<ul>" + "".join(
            f"<li>{html.escape(session['title'])} ({html.escape(session['date'])})</li>"
            for session in manifest["sessions"] if session["module_id"] == module["id"]
        ) + "</ul></li>"
        for module in manifest["modules"]
    )
    module_progress = "".join(
        f"<li>{html.escape(module['title'])}: {progress(module['topics'])}%</li>"
        for module in manifest["modules"]
    )
    legend = "".join(
        f'<li><span style="color:{color}">{label} ({color})</span></li>'
        for label, color in MAP_CATEGORIES.values()
    )
    sessions = "\n".join(html_session(session_files[s["id"]]) for s in manifest["sessions"])
    recalibrated = "<p><strong>Trilha recalibrada</strong></p>" if manifest["recalibrated"] and manifest["source"] == "edital" else ""
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>{html.escape(manifest['title'])}</title>
<style>
body {{ font-family: system-ui, sans-serif; color: #111827; max-width: 900px; margin: auto; line-height: 1.5; }}
.progress {{ height: 1rem; background: #e5e7eb; }} .progress > span {{ display: block; height: 100%; background: #2563EB; }}
.map-item {{ border-left: .35rem solid; padding-left: .6rem; }}
@media print {{ body {{ max-width: none; }} a {{ color: #000; text-decoration: none; }} }}
</style></head><body>
<h1>{html.escape(manifest['title'])}</h1>{recalibrated}
<p>Progresso global: {overall}%</p><div class="progress" role="progressbar" aria-label="Progresso global" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{overall}"><span style="width:{overall}%"></span></div>
<h2>Índice</h2><ul>{index}</ul><h2>Progresso por módulo</h2><ul>{module_progress}</ul>
<h2>Legenda do mapa mental</h2><ul>{legend}</ul>{sessions}
</body></html>\n'''


def atomic_write(path, content):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="somente validar")
    parser.add_argument("trail_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        trail = args.trail_dir.resolve()
        manifest, session_files = load_and_validate(trail)
        if not args.check:
            markdown = markdown_document(manifest, session_files)
            document = html_document(manifest, session_files)
            atomic_write(trail / "apostila.md", markdown)
            atomic_write(trail / "apostila.html", document)
    except (ValidationError, OSError, UnicodeDecodeError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
