#!/usr/bin/env python3
"""Validate a trail manifest and deterministically render its study handout."""

import argparse
import html
import json
import re
import sys
import tempfile
from datetime import datetime
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote, urlparse

try:
    from scripts.trilha_outputs import build_output_bundle, canonical_session_relative_path, publish_bundle
    from scripts.trilha_migration import is_legacy_trail, migrate_legacy_trail
except ModuleNotFoundError:  # Direct ``python scripts/build_trilha.py`` execution.
    from trilha_outputs import build_output_bundle, canonical_session_relative_path, publish_bundle
    from trilha_migration import is_legacy_trail, migrate_legacy_trail


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
QUESTION_FIELDS = (
    "Resposta", "Resultado", "Fundamento", "Alternativas úteis", "Tipo de erro",
    "Prevenção", "Fonte", "Revisão",
)
TARGETED_QUESTION_FIELDS = QUESTION_FIELDS + ("Tópico",)
DIAGNOSIS_FIELDS = ("Acertos", "Padrões de erro", "Prioridade", "Próxima revisão")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MAP_ITEM = re.compile(r"^(\s*)[-*]\s+\[([^]]+)\]\s+.+$")
MIGRATION_REQUIRED_EXIT = 3
URL_COMPONENT_SAFE = "-._~!~*'()"


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class QuestionFeedback:
    number: int
    topic_id: str | None
    block: str


def reject_nonfinite_json(_value):
    raise ValidationError("peso deve ser finito")


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
        sections[heading.group(1)] = text[heading.end():end].strip("\n")
    expected_heading = f"# {session_title}"
    if not text.startswith(expected_heading + "\n"):
        raise ValidationError(f"sessão '{session_title}': título deve ser '{expected_heading}'")
    return sections


def missing_feedback_fields(block, fields):
    return [
        field for field in fields
        if not re.search(rf"^\s*[-*]\s+{re.escape(field)}:\s*\S", block, re.MULTILINE)
    ]


def field_value(block, field):
    match = re.search(rf"^\s*[-*]\s+{re.escape(field)}:\s*(\S.*?)\s*$", block, re.MULTILINE)
    return match.group(1) if match else None


def parse_question_feedback(text):
    headings = list(re.finditer(r"^###\s+(.+?)\s*$", text, re.MULTILINE))
    questions, diagnosis = [], ""
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.end():end]
        question = re.fullmatch(r"Questão\s+(\d+)", heading.group(1))
        if question:
            try:
                number = int(question.group(1))
            except ValueError as exc:
                raise ValidationError("número de questão inválido") from exc
            questions.append(QuestionFeedback(number, field_value(block, "Tópico"), block))
        elif heading.group(1) == "Diagnóstico agregado":
            diagnosis = block
    return questions, diagnosis


def validate_question_feedback(text, session_id):
    headings = list(re.finditer(r"^###\s+(.+?)\s*$", text, re.MULTILINE))
    questions = [
        (index, heading) for index, heading in enumerate(headings)
        if re.fullmatch(r"Questão\s+\d+", heading.group(1))
    ]
    diagnoses = [
        (index, heading) for index, heading in enumerate(headings)
        if heading.group(1) == "Diagnóstico agregado"
    ]
    if not questions:
        raise ValidationError(f"sessão '{session_id}': questão com feedback obrigatória ausente")
    if not diagnoses or diagnoses[0][1].start() < questions[-1][1].start():
        raise ValidationError(f"sessão '{session_id}': diagnóstico agregado obrigatório ausente")
    for index, heading in questions:
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        missing = missing_feedback_fields(text[heading.end():end], QUESTION_FIELDS)
        if missing:
            raise ValidationError(
                f"sessão '{session_id}': questão sem campos obrigatórios: {', '.join(missing)}"
            )
    diagnosis_index, diagnosis = diagnoses[0]
    end = headings[diagnosis_index + 1].start() if diagnosis_index + 1 < len(headings) else len(text)
    missing = missing_feedback_fields(text[diagnosis.end():end], DIAGNOSIS_FIELDS)
    if missing:
        raise ValidationError(
            f"sessão '{session_id}': diagnóstico sem campos obrigatórios: {', '.join(missing)}"
        )


def validate_targeted_question_feedback(text, session):
    session_id = session["id"]
    questions, diagnosis = parse_question_feedback(text)
    if len(questions) != 20:
        raise ValidationError(f"sessão '{session_id}': exige exatamente 20 questões")
    numbers = [question.number for question in questions]
    if numbers != list(range(1, 21)):
        raise ValidationError(
            f"sessão '{session_id}': questões devem ser numeradas de 1 a 20, sem duplicidades ou lacunas"
        )
    for question in questions:
        missing = missing_feedback_fields(question.block, TARGETED_QUESTION_FIELDS)
        if missing:
            raise ValidationError(
                f"sessão '{session_id}': questão sem campos obrigatórios: {', '.join(missing)}"
            )
        if question.topic_id not in session["topic_ids"]:
            raise ValidationError(f"sessão '{session_id}': tópico inválido: {question.topic_id}")
    covered_topics = {question.topic_id for question in questions}
    for topic_id in session["topic_ids"]:
        if topic_id not in covered_topics:
            raise ValidationError(f"sessão '{session_id}': tópico sem questão: {topic_id}")
    if not diagnosis:
        raise ValidationError(f"sessão '{session_id}': diagnóstico agregado obrigatório ausente")


def map_validation_error(map_lines):
    previous_level = None
    for line in map_lines:
        match = MAP_ITEM.match(line)
        if not match:
            return "item de mapa inválido"
        level = len(match.group(1).expandtabs(2)) // 2 + 1
        if level > 3:
            return "mapa tem mais de três níveis"
        if previous_level is None and level != 1:
            return "mapa deve iniciar no primeiro nível"
        if previous_level is not None and level > previous_level + 1:
            return "mapa não pode saltar níveis"
        if match.group(2) not in MAP_CATEGORIES:
            return "categoria de mapa inválida"
        previous_level = level
    return None


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
    map_error = map_validation_error(map_lines)
    if map_error:
        raise ValidationError(f"sessão '{session['id']}': {map_error}")
    validate_question_feedback(sections["Questões e feedback"], session["id"])
    if session.get("question_target") is not None:
        validate_targeted_question_feedback(sections["Questões e feedback"], session)


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
        manifest = json.loads(
            manifest_file.read_text(encoding="utf-8"),
            parse_float=Decimal,
            parse_constant=reject_nonfinite_json,
        )
    except FileNotFoundError as exc:
        raise ValidationError("trilha.json não encontrado") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"JSON inválido: {exc.msg}") from exc
    require_mapping(manifest, "manifesto")
    require_keys(manifest, (
        "schema_version", "title", "slug", "source", "exam", "banca", "recalibrated",
        "modules", "sessions",
    ), "manifesto")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValidationError("schema_version deve ser o inteiro 1")
    if not isinstance(manifest["title"], str) or not isinstance(manifest["slug"], str):
        raise ValidationError("title e slug devem ser texto")
    if not isinstance(manifest["source"], str) or manifest["source"] not in SOURCES:
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
            weight = topic["weight"]
            valid_weight = (
                isinstance(weight, (int, Decimal))
                and not isinstance(weight, bool)
                and (not isinstance(weight, Decimal) or weight.is_finite())
                and weight > 0
            )
            if not valid_weight:
                raise ValidationError("peso deve ser numérico positivo")
            if (not isinstance(topic["status"], str) or topic["status"] not in STATUSES
                    or not isinstance(topic["sessions"], list)):
                raise ValidationError("tópico inválido")
            if any(not isinstance(item, str) or not item for item in topic["sessions"]):
                raise ValidationError("referências de sessões inválidas")
            topic_ids.add(topic_id)
            topic_modules[topic_id] = module["id"]
            topic_sessions[topic_id] = topic["sessions"]

    session_ids = unique_ids(manifest["sessions"], "sessões")
    session_files = {}
    for session in manifest["sessions"]:
        require_keys(session, ("id", "title", "date", "status", "module_id", "topic_ids", "file"), "sessão")
        if (not isinstance(session["title"], str) or not isinstance(session["date"], str)
                or not isinstance(session["status"], str) or session["status"] not in STATUSES
                or not isinstance(session["module_id"], str) or session["module_id"] not in module_ids
                or not isinstance(session["topic_ids"], list)):
            raise ValidationError("sessão inválida")
        target = session.get("question_target")
        if target is not None and (type(target) is not int or target != 20):
            raise ValidationError(f"sessão '{session['id']}': question_target deve ser o inteiro 20")
        if (not session["topic_ids"]
                or any(not isinstance(item, str) or not item for item in session["topic_ids"])
                or len(session["topic_ids"]) != len(set(session["topic_ids"]))):
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


def anchor_id(kind, item_id):
    """Return a stable fragment identifier while keeping arbitrary IDs safe in URLs."""
    # Keep the encoded fragments aligned with JavaScript's encodeURIComponent().
    return f"{kind}-{quote(item_id, safe=URL_COMPONENT_SAFE)}"


def markdown_document(manifest, session_files):
    overall = progress(all_topics(manifest))
    lines = [f"# {manifest['title']}", "", f"Progresso global: {overall}%", f"Régua de progresso: {overall}% {'█' * (overall // 10)}{'░' * (10 - overall // 10)}", ""]
    if manifest["recalibrated"] and manifest["source"] == "edital":
        lines.extend(["**Trilha recalibrada**", ""])
    lines.extend(["## Índice", ""])
    for module in manifest["modules"]:
        module_anchor = anchor_id("modulo", module["id"])
        lines.append(f"- [{module['title']}](#{module_anchor})")
        for session in [s for s in manifest["sessions"] if s["module_id"] == module["id"]]:
            session_anchor = anchor_id("sessao", session["id"])
            lines.append(f"  - [{session['title']}](#{session_anchor}) ({session['date']})")
    lines.extend(["", "## Progresso por módulo", ""])
    for module in manifest["modules"]:
        lines.append(f"- {module['title']}: {progress(module['topics'])}%")
    lines.extend(["", "## Legenda do mapa mental", ""])
    for _, (label, color) in MAP_CATEGORIES.items():
        lines.append(f"- {label} ({color})")
    for module in manifest["modules"]:
        lines.extend(["", "---", "", f'<a id="{anchor_id("modulo", module["id"])}"></a>', "", f"## {module['title']}", ""])
        for session in [s for s in manifest["sessions"] if s["module_id"] == module["id"]]:
            lines.extend([
                "---", "", f'<a id="{anchor_id("sessao", session["id"])}"></a>', "",
                session_files[session["id"]].rstrip(), "",
            ])
    return "\n".join(lines).rstrip() + "\n"


def safe_inline(text):
    parts = []
    position = 0
    for match in LINK.finditer(text):
        parts.append(html.escape(text[position:match.start()], quote=True))
        label, url = match.group(1), match.group(2).strip()
        scheme = urlparse(url).scheme.lower()
        if scheme and scheme not in {"http", "https", "mailto"}:
            parts.append(html.escape(label, quote=True))
        else:
            parts.append(
                f'<a href="{html.escape(url, quote=True)}">'
                f"{html.escape(label, quote=True)}</a>"
            )
        position = match.end()
    parts.append(html.escape(text[position:], quote=True))
    return "".join(parts)


def html_map(lines):
    blocks = ['<ul class="mind-map">']
    current_level = 0
    for line in lines:
        match = MAP_ITEM.match(line)
        if not match:
            continue
        level = len(match.group(1).expandtabs(2)) // 2 + 1
        category, content = match.group(2), line[match.end(2) + 2:].strip()
        label, color = MAP_CATEGORIES[category]
        if current_level == 0:
            current_level = level
        elif level > current_level:
            while current_level < level:
                current_level += 1
                blocks.append(f'<ul class="map-level-{current_level}">')
        elif level == current_level:
            blocks.append("</li>")
        else:
            while current_level > level:
                blocks.append("</li></ul>")
                current_level -= 1
            blocks.append("</li>")
        blocks.append(
            f'<li class="map-item map-level-{level}" style="border-color:{color}">'
            f"<strong>{label}:</strong> {safe_inline(content)}"
        )
    while current_level > 1:
        blocks.append("</li></ul>")
        current_level -= 1
    if current_level:
        blocks.append("</li>")
    blocks.append("</ul>")
    return "\n".join(blocks)


def html_session(text, session_anchor):
    blocks = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("# "):
            blocks.append(f'<h3 id="{html.escape(session_anchor, quote=True)}">{safe_inline(line[2:])}</h3>')
        elif line.startswith("## "):
            blocks.append(f"<h4>{safe_inline(line[3:])}</h4>")
            if line[3:] == "Mapa mental":
                index += 1
                map_lines = []
                while index < len(lines) and not lines[index].startswith(("# ", "## ", "### ")):
                    if lines[index].strip():
                        map_lines.append(lines[index])
                    index += 1
                if map_lines and map_validation_error(map_lines) is None:
                    blocks.append(html_map(map_lines))
                else:
                    blocks.extend(f"<p>{safe_inline(map_line.strip())}</p>" for map_line in map_lines)
                continue
        elif line.startswith("### "):
            blocks.append(f"<h5>{safe_inline(line[4:])}</h5>")
        elif line.strip().startswith(("- ", "* ")):
            item = line.strip()[2:]
            blocks.append(f"<p>• {safe_inline(item)}</p>")
        elif line.strip():
            blocks.append(f"<p>{safe_inline(line.strip())}</p>")
        index += 1
    return "\n".join(blocks)


def html_document(manifest, session_files):
    overall = progress(all_topics(manifest))
    navigation_html = "".join(
        f'<li><a class="module-label" href="#{html.escape(anchor_id("modulo", module["id"]), quote=True)}">{html.escape(module["title"])}</a><ul>' + "".join(
            f'<li><a href="#{html.escape(anchor_id("topico", topic["id"]), quote=True)}" '
            f'data-topic-link="{html.escape(topic["id"], quote=True)}">{html.escape(topic["title"])}</a></li>'
            for topic in module["topics"]
        ) + "</ul><ul>" + "".join(
            f'<li><a href="#{html.escape(anchor_id("sessao", session["id"]), quote=True)}">{html.escape(session["title"])}</a> ({html.escape(session["date"])})</li>'
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
    content_html = "\n".join(
        f'<section aria-labelledby="{html.escape(anchor_id("modulo", module["id"]), quote=True)}">'
        f'<h2 id="{html.escape(anchor_id("modulo", module["id"]), quote=True)}">{html.escape(module["title"])}</h2>'
        + "\n".join(
            f'<section id="{html.escape(anchor_id("topico", topic["id"]), quote=True)}" '
            f'data-topic-section="{html.escape(topic["id"], quote=True)}" '
            f'aria-label="{html.escape(topic["title"], quote=True)}">'
            f'<h3>{html.escape(topic["title"])}</h3>'
            + "\n".join(
                html_session(
                    session_files[session["id"]],
                    anchor_id("sessao", session["id"]),
                )
                for session in manifest["sessions"]
                if session["module_id"] == module["id"] and session["topic_ids"][0] == topic["id"]
            )
            + "</section>"
            for topic in module["topics"]
        )
        + "</section>"
        for module in manifest["modules"]
    )
    recalibrated = "<p><strong>Trilha recalibrada</strong></p>" if manifest["recalibrated"] and manifest["source"] == "edital" else ""
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>{html.escape(manifest['title'])}</title>
<style>
body {{ font-family: system-ui, sans-serif; color: #111827; margin: 0; line-height: 1.5; }}
#trail-layout {{ display: grid; grid-template-columns: minmax(13rem, 18rem) minmax(0, 1fr); gap: 2rem; max-width: 1200px; margin: 0 auto; padding: 1.5rem; }}
#trail-sidebar {{ position: sticky; top: 1rem; align-self: start; max-height: calc(100vh - 2rem); overflow: auto; padding: 1rem; border: 1px solid #d1d5db; border-radius: .5rem; background: #fff; }}
#trail-sidebar ul {{ padding-left: 1rem; }} #trail-sidebar a {{ color: #1d4ed8; }}
.module-label {{ display: block; font-weight: 700; margin-top: .5rem; }}
[data-topic-link].is-active {{ color: #111827; font-weight: 700; }} [data-topic-link].is-active::after {{ content: " — tópico atual"; }}
#sidebar-toggle {{ display: none; }}
#trail-content {{ min-width: 0; }} [data-topic-section] {{ scroll-margin-top: 1rem; }}
a:focus-visible, button:focus-visible {{ outline: 3px solid #f59e0b; outline-offset: 3px; }}
.progress {{ height: 1rem; background: #e5e7eb; }} .progress > span {{ display: block; height: 100%; background: #2563EB; }}
.map-item {{ border-left: .35rem solid; padding-left: .6rem; }}
@media (max-width: 800px) {{
  #trail-layout {{ display: block; padding: 1rem; }} #sidebar-toggle {{ display: block; margin: 1rem; }}
  #trail-sidebar {{ position: fixed; z-index: 1; inset: 0 auto 0 0; width: min(18rem, 85vw); max-height: none; border-radius: 0; transform: translateX(-105%); transition: transform .2s ease; }}
  #trail-sidebar.is-open {{ transform: translateX(0); }}
}}
@media print {{ #trail-sidebar, #sidebar-toggle {{ display: none !important; }} #trail-layout {{ display: block; max-width: none; padding: 0; }} a {{ color: #000; text-decoration: none; }} }}
</style></head><body>
<button id="sidebar-toggle" type="button" aria-controls="trail-sidebar" aria-expanded="false">Índice</button>
<div id="trail-layout"><aside id="trail-sidebar" aria-label="Índice da apostila"><nav><h2>Índice</h2><ul>{navigation_html}</ul></nav></aside>
<main id="trail-content"><h1>{html.escape(manifest['title'])}</h1>{recalibrated}
<p>Progresso global: {overall}%</p><div class="progress" role="progressbar" aria-label="Progresso global" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{overall}"><span style="width:{overall}%"></span></div>
<h2>Progresso por módulo</h2><ul>{module_progress}</ul>
<h2>Legenda do mapa mental</h2><ul>{legend}</ul>{content_html}</main></div>
<script>
const toggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('trail-sidebar');
toggle.addEventListener('click', () => {{
  const open = sidebar.classList.toggle('is-open');
  toggle.setAttribute('aria-expanded', String(open));
}});
const links = new Map([...document.querySelectorAll('[data-topic-link]')]
  .map(link => [link.dataset.topicLink, link]));
const sections = [...document.querySelectorAll('[data-topic-section]')];
const activate = id => {{
  links.forEach((link, key) => {{
    const active = key === id;
    link.classList.toggle('is-active', active);
    if (active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  }});
  if (id) history.replaceState(null, '', `#topico-${{encodeURIComponent(id)}}`);
}};
const observer = new IntersectionObserver(entries => {{
  const visible = entries.filter(entry => entry.isIntersecting)
    .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
  if (visible) activate(visible.target.dataset.topicSection);
}}, {{rootMargin: '-20% 0px -65% 0px', threshold: [0, 0.1, 0.5]}});
sections.forEach(section => observer.observe(section));
</script>
</body></html>\n'''


def atomic_write(path, content):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def build_trail(trail):
    """Validate and publish every normal derived artifact for one trail."""
    manifest, session_files = load_and_validate(trail)
    markdown = markdown_document(manifest, session_files)
    document = html_document(manifest, session_files)
    outputs = build_output_bundle(trail, manifest, session_files, markdown, document)
    # Keep the original two entry points during the staged layout transition.
    outputs[Path("apostila.md")] = markdown.encode("utf-8")
    outputs[Path("apostila.html")] = document.encode("utf-8")
    publish_bundle(trail, outputs)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    migration_mode = parser.add_mutually_exclusive_group()
    migration_mode.add_argument("--check", action="store_true", help="somente validar")
    migration_mode.add_argument("--migrate", action="store_true", help="migrar uma trilha legada")
    parser.add_argument("trail_dir", type=Path)
    args = parser.parse_args(argv)
    try:
        trail = args.trail_dir.resolve()
        manifest, session_files = load_and_validate(trail)
        if is_legacy_trail(trail, manifest):
            if not args.migrate:
                print("MIGRATION_REQUIRED", file=sys.stderr)
                return MIGRATION_REQUIRED_EXIT
            migrate_legacy_trail(trail, build_trail, canonical_session_relative_path, datetime.now())
        elif not args.check:
            build_trail(trail)
    except (ValidationError, OSError, UnicodeDecodeError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
