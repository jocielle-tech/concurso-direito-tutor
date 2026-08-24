"""Self-contained, accessible HTML rendering for a study trail."""

from __future__ import annotations

import base64
import html
import re
from urllib.parse import quote, urlparse


PALETTE = {
    "ink": "#101828", "muted": "#475467", "surface": "#FFFFFF",
    "canvas": "#F4F7FB", "violet": "#635BFF", "blue": "#0284C7",
    "success": "#15803D", "warning": "#B45309", "danger": "#B42318",
}
HERO_COLORS = {"violet": "#3730A3", "blue": "#075985"}
FOCUS_COLORS = {"surface": "#344054", "hero": "#FFFFFF"}
MAP_CATEGORIES = {
    "conceito": ("Conceito", "#2563EB"),
    "regra": ("Regra", "#16A34A"),
    "excecao": ("Exceção", "#D97706"),
    "pegadinha": ("Pegadinha", "#DC2626"),
    "jurisprudencia": ("Jurisprudência", "#7C3AED"),
}
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
MAP_ITEM = re.compile(r"^(\s*)[-*]\s+\[([^]]+)\]\s+.+$")
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
URL_COMPONENT_SAFE = "-._~!~*'()"


def progress(topics):
    total = sum(topic["weight"] for topic in topics)
    completed = sum(topic["weight"] for topic in topics if topic["status"] == "completed")
    return round(completed * 100 / total) if total else 0


def all_topics(manifest):
    return [topic for module in manifest["modules"] for topic in module["topics"]]


def anchor_id(kind, item_id):
    return f"{kind}-{quote(item_id, safe=URL_COMPONENT_SAFE)}"


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


def safe_inline(text, local_fragments=()):
    parts, position = [], 0
    for match in LINK.finditer(text):
        parts.append(html.escape(text[position:match.start()], quote=True))
        label, url = match.group(1), match.group(2).strip()
        scheme = urlparse(url).scheme.lower()
        if ((scheme and scheme not in {"http", "https", "mailto"})
                or (url.startswith("#") and url[1:] not in local_fragments)):
            parts.append(html.escape(label, quote=True))
        else:
            parts.append(
                f'<a href="{html.escape(url, quote=True)}">{html.escape(label, quote=True)}</a>'
            )
        position = match.end()
    parts.append(html.escape(text[position:], quote=True))
    return "".join(parts)


def html_map(lines, local_fragments=()):
    blocks, current_level = ['<ul class="mind-map">'], 0
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
            f"<strong>{label}:</strong> {safe_inline(content, local_fragments)}"
        )
    while current_level > 1:
        blocks.append("</li></ul>")
        current_level -= 1
    if current_level:
        blocks.append("</li>")
    blocks.append("</ul>")
    return "\n".join(blocks)


def _algorithm_label(line):
    raw = line.strip()
    markdown = MAP_ITEM.match(raw)
    if markdown:
        raw = raw[markdown.end(2) + 2:].strip()
    match = re.match(r"^(ENTRADA|SE(?:\s+SIM|\s+NÃO)?|ENTÃO|SENÃO|RESULTADO|ALERTA)\s*:\s*(.*)$", raw, re.I)
    if match:
        return match.group(1).upper(), match.group(2)
    return "ETAPA", raw


def _algorithm_fallback(topic, lines):
    target_id = html.escape(anchor_id("algorithm", topic["id"]), quote=True)
    topic_id = html.escape(topic["id"], quote=True)
    nodes = []
    for line in lines:
        label, content = _algorithm_label(line)
        kind = "algorithm-decision" if label.startswith("SE") or label == "SENÃO" else "algorithm-step"
        if label == "ALERTA":
            kind += " algorithm-alert"
        nodes.append(
            f'<li class="algorithm-node {kind}"><strong>{html.escape(label)}:</strong> '
            f'{html.escape(content)}</li>'
        )
    if not nodes:
        nodes.append('<li class="algorithm-node algorithm-step">Mapa algorítmico indisponível.</li>')
    return (
        f'<div id="{target_id}" class="algorithm-flow" data-algorithm-fallback="{topic_id}">'
        f'<p class="algorithm-caption">Fluxo textual verificável</p><ol>{"".join(nodes)}</ol></div>'
    )


def _data_uri(png_bytes):
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _visual_map_html(topic, asset):
    topic_id = html.escape(topic["id"], quote=True)
    algorithm_target = html.escape(anchor_id("algorithm", topic["id"]), quote=True)
    lines = asset.spec.algorithm_lines if asset else ()
    fallback = _algorithm_fallback(topic, lines)
    if asset and asset.status == "ready" and asset.png_bytes:
        source = _data_uri(asset.png_bytes)
        alt = html.escape(asset.spec.alt_text, quote=True)
        return (
            f'<figure class="visual-map-card" data-visual-map="{topic_id}">'
            f'<button type="button" class="map-open" data-map-open="{topic_id}" '
            f'aria-haspopup="dialog"><img src="{source}" alt="{alt}" loading="lazy"></button>'
            '<figcaption>Mapa algorítmico — clique para ampliar. '
            f'<a class="no-js-map-link" href="#{algorithm_target}">Ler fluxo textual</a></figcaption>'
            f'{fallback}</figure>'
        )
    if asset:
        return f'<div class="visual-map-card" data-visual-map="{topic_id}">{fallback}</div>'
    if topic["status"] == "completed":
        return f'<div class="visual-map-card" data-visual-map="{topic_id}">{fallback}</div>'
    return ""


def _question_fields(lines, local_fragments):
    fields = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            label, separator, value = stripped[2:].partition(":")
            if separator:
                class_name = "question-chip" if label in {"Tópico", "Resultado"} else "question-field"
                fields.append(
                    f'<p class="{class_name}"><strong>{safe_inline(label, local_fragments)}:</strong> '
                    f'{safe_inline(value.strip(), local_fragments)}</p>'
                )
            else:
                fields.append(f'<p>{safe_inline(stripped[2:], local_fragments)}</p>')
        elif stripped:
            fields.append(f'<p>{safe_inline(stripped, local_fragments)}</p>')
    return "".join(fields)


def _question_parts(lines):
    headings = [
        (index, line.strip()[5:].strip())
        for index, line in enumerate(lines)
        if line.strip().startswith("#### ")
    ]
    if [name for _index, name in headings] != [
        "Pergunta", "Alternativas", "Resposta e feedback"
    ]:
        return None
    parts = {}
    for position, (index, name) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        parts[name] = lines[index + 1:end]
    return lines[:headings[0][0]], parts


def _question_prose(lines, local_fragments):
    return "".join(
        f'<p>{safe_inline(line.strip(), local_fragments)}</p>'
        for line in lines if line.strip()
    )


def _question_options(lines, local_fragments):
    items = []
    option = re.compile(r"^[-*]\s+((?:[A-Z]|Certo|Errado)[).:])\s+(\S.*)$", re.IGNORECASE)
    for line in lines:
        match = option.match(line.strip())
        if match:
            items.append(
                f'<li><strong>{safe_inline(match.group(1), local_fragments)}</strong> '
                f'{safe_inline(match.group(2), local_fragments)}</li>'
            )
        elif line.strip():
            items.append(f'<li>{safe_inline(line.strip(), local_fragments)}</li>')
    return f'<ul>{"".join(items)}</ul>'


def _question_card(title, lines, local_fragments):
    structured = _question_parts(lines)
    if structured is None:
        body = _question_fields(lines, local_fragments)
    else:
        metadata, parts = structured
        body = (
            f'{_question_fields(metadata, local_fragments)}'
            '<div class="question-prompt"><h6>Pergunta</h6>'
            f'{_question_prose(parts["Pergunta"], local_fragments)}</div>'
            '<div class="question-options"><h6>Alternativas</h6>'
            f'{_question_options(parts["Alternativas"], local_fragments)}</div>'
            '<div class="question-feedback"><h6>Resposta e feedback</h6>'
            f'{_question_fields(parts["Resposta e feedback"], local_fragments)}</div>'
        )
    return f'<section class="question-card"><h5>{safe_inline(title, local_fragments)}</h5>{body}</section>'


def html_session(text, session_anchor, local_fragments):
    blocks, lines, index = [], text.splitlines(), 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("# "):
            blocks.append(
                f'<h3 id="{html.escape(session_anchor, quote=True)}" class="session-title">'
                f'{safe_inline(line[2:], local_fragments)}</h3>'
            )
        elif line.startswith("## "):
            heading = line[3:]
            index += 1
            section_lines = []
            while index < len(lines) and not lines[index].startswith(("# ", "## ")):
                section_lines.append(lines[index])
                index += 1
            if heading == "Mapa mental":
                map_end = next(
                    (position for position, item in enumerate(section_lines) if item.startswith("### ")),
                    len(section_lines),
                )
                map_lines = [item for item in section_lines[:map_end] if item.strip()]
                if map_lines and map_validation_error(map_lines) is None:
                    body = html_map(map_lines, local_fragments)
                else:
                    body = "".join(
                        f'<p>{safe_inline(item.strip(), local_fragments)}</p>'
                        for item in map_lines if item.strip()
                    )
                trailing = []
                for item in section_lines[map_end:]:
                    if item.startswith("### "):
                        trailing.append(f'<h5>{safe_inline(item[4:], local_fragments)}</h5>')
                    elif item.strip():
                        trailing.append(f'<p>{safe_inline(item.strip(), local_fragments)}</p>')
                blocks.append(
                    f'<section class="study-card"><h4>{safe_inline(heading, local_fragments)}</h4>'
                    f'{body}{"".join(trailing)}</section>'
                )
                continue
            section_parts, subindex = [], 0
            while subindex < len(section_lines):
                item = section_lines[subindex]
                if item.startswith("### Questão "):
                    title = item[4:]
                    subindex += 1
                    question_lines = []
                    while subindex < len(section_lines) and not section_lines[subindex].startswith("### "):
                        question_lines.append(section_lines[subindex])
                        subindex += 1
                    section_parts.append(_question_card(title, question_lines, local_fragments))
                    continue
                if item.startswith("### "):
                    heading_class = ' class="theory-section-title"' if heading == "Conteúdo principal" else ""
                    section_parts.append(
                        f'<h5{heading_class}>{safe_inline(item[4:], local_fragments)}</h5>'
                    )
                elif item.strip().startswith(("- ", "* ")):
                    section_parts.append(f'<p>• {safe_inline(item.strip()[2:], local_fragments)}</p>')
                elif item.strip():
                    section_parts.append(f'<p>{safe_inline(item.strip(), local_fragments)}</p>')
                subindex += 1
            card_class = "study-card theory-briefing" if heading == "Conteúdo principal" else "study-card"
            blocks.append(
                f'<section class="{card_class}"><h4>{safe_inline(heading, local_fragments)}</h4>'
                f'{"".join(section_parts)}</section>'
            )
            continue
        index += 1
    return "\n".join(blocks)


def _next_review(manifest, session_files):
    for session in manifest["sessions"]:
        if session["status"] != "completed":
            continue
        headings = list(SECTION.finditer(session_files[session["id"]]))
        for index, heading in enumerate(headings):
            if heading.group(1) != "Próxima revisão":
                continue
            end = headings[index + 1].start() if index + 1 < len(headings) else len(session_files[session["id"]])
            review = " ".join(session_files[session["id"]][heading.end():end].split())
            if review:
                return review
    return "Sem revisão agendada"


def _metrics(manifest, session_files):
    topics = all_topics(manifest)
    return (
        ("global-progress", "Progresso global", f"{progress(topics)}%"),
        ("completed-sessions", "Sessões concluídas", str(sum(s["status"] == "completed" for s in manifest["sessions"]))),
        ("completed-topics", "Tópicos concluídos", str(sum(t["status"] == "completed" for t in topics))),
        ("next-review", "Próxima revisão", _next_review(manifest, session_files)),
    )


def _progress_indicator(scope, marker, label, value):
    """Return a visible, screen-reader friendly progress meter with a stable selector."""
    safe_marker = html.escape(marker, quote=True)
    safe_label = html.escape(label, quote=True)
    return (
        f'<div class="progress progress-{scope}" data-progress-{scope}="{safe_marker}" '
        f'role="progressbar" aria-label="{safe_label}" aria-valuemin="0" '
        f'aria-valuemax="100" aria-valuenow="{value}" aria-valuetext="{value}% concluído">'
        f'<span style="width:{value}%"></span></div>'
        f'<p class="progress-caption">{html.escape(label)}: <strong>{value}%</strong></p>'
    )


def render_html(manifest, session_files, visual_maps):
    """Render a deterministic portable dashboard.  The caller owns asset discovery."""
    visual_maps = visual_maps or {}
    topics = all_topics(manifest)
    overall = progress(topics)
    local_fragments = {
        *(anchor_id("modulo", module["id"]) for module in manifest["modules"]),
        *(anchor_id("topico", topic["id"]) for topic in topics),
        *(anchor_id("sessao", session["id"]) for session in manifest["sessions"]),
        *(anchor_id("algorithm", topic["id"]) for topic in topics if topic["status"] == "completed"),
    }
    navigation_html = "".join(
        f'<li><a class="module-label" href="#{html.escape(anchor_id("modulo", module["id"]), quote=True)}">{html.escape(module["title"])}</a><ul>'
        + "".join(
            f'<li><a href="#{html.escape(anchor_id("topico", topic["id"]), quote=True)}" '
            f'data-topic-link="{html.escape(topic["id"], quote=True)}">{html.escape(topic["title"])}</a></li>'
            for topic in module["topics"]
        ) + "</ul><ul>" + "".join(
            f'<li><a href="#{html.escape(anchor_id("sessao", session["id"]), quote=True)}">{html.escape(session["title"])}</a> ({html.escape(session["date"])})</li>'
            for session in manifest["sessions"] if session["module_id"] == module["id"]
        ) + "</ul></li>"
        for module in manifest["modules"]
    )
    metric_html = "".join(
        f'<article class="metric-card" data-metric="{key}"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></article>'
        for key, label, value in _metrics(manifest, session_files)
    )
    content_html = "\n".join(
        f'<section class="module-section" aria-labelledby="{html.escape(anchor_id("modulo", module["id"]), quote=True)}">'
        f'<h2 id="{html.escape(anchor_id("modulo", module["id"]), quote=True)}">{html.escape(module["title"])}</h2>'
        f'{_progress_indicator("module", module["id"], "Progresso do módulo " + module["title"], progress(module["topics"]))}'
        + "\n".join(
            f'<section id="{html.escape(anchor_id("topico", topic["id"]), quote=True)}" '
            f'data-topic-section="{html.escape(topic["id"], quote=True)}" '
            f'aria-label="{html.escape(topic["title"], quote=True)}">'
            f'<div class="topic-heading"><h3>{html.escape(topic["title"])}</h3><span class="status-chip status-{html.escape(topic["status"], quote=True)}">{html.escape(topic["status"].replace("_", " "))}</span></div>'
            f'{_progress_indicator("topic", topic["id"], "Progresso do tópico " + topic["title"], 100 if topic["status"] == "completed" else 0)}'
            f'{_visual_map_html(topic, visual_maps.get(topic["id"]))}'
            + "\n".join(
                html_session(session_files[session["id"]], anchor_id("sessao", session["id"]), local_fragments)
                for session in manifest["sessions"]
                if session["module_id"] == module["id"] and session["topic_ids"][0] == topic["id"]
            ) + "\n".join(
                f'<p class="shared-session">Sessão compartilhada: <a href="#{html.escape(anchor_id("sessao", session["id"]), quote=True)}">{html.escape(session["title"])}</a></p>'
                for session in manifest["sessions"]
                if session["module_id"] == module["id"] and topic["id"] in session["topic_ids"] and session["topic_ids"][0] != topic["id"]
            ) + "</section>"
            for topic in module["topics"]
        ) + "</section>"
        for module in manifest["modules"]
    )
    legend = "".join(
        f'<li><span style="color:{color}">{label} ({color})</span></li>'
        for label, color in MAP_CATEGORIES.values()
    )
    recalibrated = '<p class="recalibrated"><strong>Trilha recalibrada</strong></p>' if manifest["recalibrated"] and manifest["source"] == "edital" else ""
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(manifest['title'])}</title>
<style>
:root {{ --ink:{PALETTE['ink']}; --muted:{PALETTE['muted']}; --surface:{PALETTE['surface']}; --canvas:{PALETTE['canvas']}; --violet:{PALETTE['violet']}; --blue:{PALETTE['blue']}; --success:{PALETTE['success']}; --warning:{PALETTE['warning']}; --danger:{PALETTE['danger']}; --border:#D0D5DD; --shadow:0 10px 30px rgba(16,24,40,.08); }}
* {{ box-sizing:border-box; }} html {{ scroll-behavior: smooth; }} body {{ margin:0; background:var(--canvas); color:var(--ink); font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.55; }}
a {{ color:#175CD3; }} a:focus-visible, button:focus-visible {{ outline:3px solid {FOCUS_COLORS['surface']}; outline-offset:3px; }} #dashboard-hero a:focus-visible, #dashboard-hero button:focus-visible {{ outline-color:{FOCUS_COLORS['hero']}; }} button {{ font:inherit; }}
#dashboard-hero {{ max-width:1200px; margin:0 auto; padding:2.2rem 1.5rem 1.5rem; color:#fff; background:linear-gradient(122deg,{HERO_COLORS['violet']},{HERO_COLORS['blue']}); border-radius:0 0 1.5rem 1.5rem; }} #dashboard-hero h1 {{ margin:0; font-size:clamp(1.75rem,4vw,2.7rem); line-height:1.12; }} #dashboard-hero p {{ margin:.65rem 0 0; max-width:56rem; }}
.metric-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.8rem; margin-top:1.4rem; }} .metric-card {{ min-width:0; padding:1rem; border:1px solid rgba(255,255,255,.3); border-radius:.85rem; background:rgba(255,255,255,.14); }} .metric-card span {{ display:block; font-size:.82rem; }} .metric-card strong {{ display:block; margin-top:.2rem; font-size:1.1rem; overflow-wrap:anywhere; }}
#trail-layout {{ display:grid; grid-template-columns:minmax(13rem,18rem) minmax(0,1fr); gap:2rem; max-width:1200px; margin:0 auto; padding:1.5rem; }} #trail-sidebar {{ position:sticky; top:1rem; align-self:start; max-height:calc(100vh - 2rem); overflow:auto; padding:1rem; border:1px solid var(--border); border-radius:.85rem; background:var(--surface); box-shadow:var(--shadow); }} #trail-sidebar ul {{ padding-left:1rem; }} #trail-sidebar a {{ color:#175CD3; }} .module-label {{ display:block; margin-top:.5rem; font-weight:700; color:var(--ink) !important; }} [data-topic-link].is-active {{ color:var(--ink); font-weight:700; }} [data-topic-link].is-active::after {{ content:" — tópico atual"; }} #sidebar-toggle {{ display:none; }}
#trail-content {{ min-width:0; }} [data-topic-section] {{ scroll-margin-top:1rem; margin-bottom:2.6rem; }} .module-section > h2 {{ margin:0 0 1rem; font-size:1.65rem; }} .topic-heading {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; }} .topic-heading h3,.session-title {{ margin:1.4rem 0 .7rem; }} .status-chip,.question-chip {{ display:inline-block; padding:.2rem .55rem; border-radius:999px; background:#E0EAFF; color:#00359E; font-size:.82rem; font-weight:700; text-transform:capitalize; }} .status-completed {{ background:#DCFCE7; color:#14532D; }} .status-in_progress {{ background:#FEF3C7; color:#78350F; }}
.study-card,.visual-map-card {{ margin:1rem 0; padding:1.15rem; border:1px solid var(--border); border-radius:1rem; background:var(--surface); box-shadow:var(--shadow); }} .study-card h4 {{ margin:0 0 .75rem; }} .study-card p,.question-card p {{ margin:.5rem 0; }} .theory-briefing {{ border-top:4px solid var(--blue); background:linear-gradient(180deg,#F0F9FF 0,#FFFFFF 8rem); }} .theory-section-title {{ margin:1.2rem 0 .45rem; padding-left:.7rem; border-left:3px solid var(--violet); color:#312E81; font-size:1rem; }} .question-card {{ margin:.85rem 0; padding:1rem; border-left:4px solid var(--violet); border-radius:.7rem; background:#F9FAFF; }} .question-card h5 {{ margin:0 0 .6rem; font-size:1rem; }} .question-card h6 {{ margin:.2rem 0 .55rem; color:#312E81; font-size:.94rem; }} .question-prompt,.question-options,.question-feedback {{ margin:.75rem 0; padding:.85rem 1rem; border-radius:.65rem; }} .question-prompt {{ background:#EEF2FF; border-left:4px solid #4F46E5; }} .question-options {{ background:#F8FAFC; border:1px solid #E2E8F0; }} .question-options ul {{ margin:.25rem 0 0; padding:0; list-style:none; }} .question-options li {{ margin:.45rem 0; }} .question-feedback {{ background:#FAF5FF; border-left:4px solid #8B5CF6; }} .question-field {{ color:var(--muted); }}
.progress {{ height:.75rem; overflow:hidden; border-radius:999px; background:#DDE3EE; }} .progress > span {{ display:block; height:100%; background:linear-gradient(90deg,var(--violet),var(--blue)); }} .progress-caption {{ margin:.35rem 0 .85rem; color:var(--muted); font-size:.88rem; }} .progress-module {{ max-width:34rem; }} .progress-topic {{ max-width:24rem; }} .mind-map {{ padding-left:1.2rem; }} .map-item {{ margin:.35rem 0; border-left:.35rem solid; padding-left:.6rem; }}
.visual-map-card {{ overflow:hidden; }} .map-open {{ display:block; width:100%; padding:0; border:0; border-radius:.75rem; background:transparent; cursor:zoom-in; }} .map-open img {{ display:block; width:100%; height:auto; border-radius:.75rem; }} .visual-map-card figcaption {{ margin-top:.75rem; color:var(--muted); font-size:.9rem; }} .algorithm-flow {{ margin-top:1rem; }} .algorithm-caption {{ margin:0 0 .45rem; font-weight:700; color:var(--muted); }} .algorithm-flow ol {{ display:grid; gap:.55rem; margin:0; padding:0; list-style:none; }} .algorithm-node {{ padding:.7rem .8rem; border:1px solid var(--border); border-radius:.65rem; background:#fff; }} .algorithm-decision {{ border-color:#7C3AED; background:#F5F3FF; }} .algorithm-alert {{ border-color:#B42318; background:#FEF3F2; }}
dialog {{ width:min(92vw,1100px); max-height:92vh; padding:0; border:0; border-radius:1rem; color:var(--ink); box-shadow:0 24px 70px rgba(16,24,40,.35); }} dialog::backdrop {{ background:rgba(16,24,40,.65); }} .dialog-toolbar {{ display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:1rem 1.25rem; }} .dialog-toolbar h2 {{ margin:0; font-size:1.15rem; }} [data-map-close] {{ width:2.4rem; height:2.4rem; border:1px solid var(--border); border-radius:50%; background:#fff; color:var(--ink); font-size:1.4rem; cursor:pointer; }} #map-dialog-image {{ display:block; max-width:100%; max-height:calc(92vh - 5rem); margin:0 auto 1rem; }}
@media (max-width: 800px) {{
  #dashboard-hero {{ margin:0; border-radius:0; padding:1.6rem 1rem; }}
  .metric-grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
  #trail-layout {{ display:block; padding:1rem; }}
  #trail-sidebar {{ position: static; max-height:none; overflow:visible; }}
  .js #sidebar-toggle {{ display: block; margin: 1rem; position: relative; z-index: 2; }}
  .js #trail-sidebar {{ position:fixed; z-index:1; inset:0 auto 0 0; width:min(18rem,85vw); overflow:auto; border-radius:0; transform: translateX(-105%); transition:transform .2s ease; }}
  .js #trail-sidebar.is-open {{ transform:translateX(0); }}
}}
@media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}
@media (prefers-reduced-motion: reduce) {{ *,*::before,*::after {{ animation-duration:.01ms !important; transition-duration:.01ms !important; }} }}
@media print {{ body {{ background:#fff; }} #dashboard-hero {{ max-width:none; padding:0; color:#000; background:none; }} #trail-sidebar,#sidebar-toggle {{ display:none !important; }} #trail-layout {{ display:block; max-width:none; padding:0; }} .metric-grid {{ grid-template-columns:repeat(4,1fr); }} .metric-card,.study-card,.visual-map-card {{ box-shadow:none; }} .question-card h5,.question-card h6 {{ break-after:avoid-page; }} .question-options li {{ break-inside:avoid; }} .map-open {{ cursor:default; }} .no-js-map-link {{ display:none; }} a {{ color:#000; text-decoration:none; }} }}
</style></head><body>
<header id="dashboard-hero"><h1>{html.escape(manifest['title'])}</h1>{recalibrated}<p>Roteiro de estudo, revisões e questões com feedback em uma apostila navegável.</p>{_progress_indicator("global", "global", "Progresso global", overall)}<div class="metric-grid">{metric_html}</div></header>
<button id="sidebar-toggle" type="button" aria-controls="trail-sidebar" aria-expanded="false">Índice</button>
<div id="trail-layout"><aside id="trail-sidebar" aria-label="Índice da apostila"><nav><h2>Índice</h2><ul>{navigation_html}</ul></nav></aside><main id="trail-content"><h2>Conteúdo da apostila</h2><h3>Legenda do mapa mental</h3><ul>{legend}</ul>{content_html}</main></div>
<dialog id="map-dialog" aria-modal="true" aria-labelledby="map-dialog-title"><div class="dialog-toolbar"><h2 id="map-dialog-title">Mapa algorítmico</h2><button type="button" data-map-close aria-label="Fechar mapa">×</button></div><img id="map-dialog-image" alt=""></dialog>
<script>
const toggle = document.getElementById('sidebar-toggle');
const sidebar = document.getElementById('trail-sidebar');
const mobileQuery = window.matchMedia('(max-width: 800px)');
const setSidebarState = open => {{
  const mobile = mobileQuery.matches;
  sidebar.hidden = mobile && !open;
  sidebar.inert = mobile && !open;
  sidebar.classList.toggle('is-open', mobile && open);
  toggle.setAttribute('aria-expanded', String(mobile && open));
}};
toggle.addEventListener('click', () => setSidebarState(sidebar.hidden));
mobileQuery.addEventListener('change', () => setSidebarState(false));
setSidebarState(false);
document.documentElement.classList.add('js');
const links = new Map([...document.querySelectorAll('[data-topic-link]')].map(link => [link.dataset.topicLink, link]));
const sections = [...document.querySelectorAll('[data-topic-section]')];
let navigationTarget = null;
const activate = id => {{links.forEach((link, key) => {{const active = key === id; link.classList.toggle('is-active', active); if (active) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current');}}); if (id) history.replaceState(null, '', `#topico-${{encodeURIComponent(id)}}`);}};
links.forEach((link, key) => link.addEventListener('click', () => {{navigationTarget = key; activate(key); window.setTimeout(() => {{navigationTarget = null;}}, 500);}}));
const observer = new IntersectionObserver(entries => {{if (navigationTarget) return; const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]; if (visible) activate(visible.target.dataset.topicSection);}}, {{rootMargin: '-20% 0px -65% 0px', threshold: [0, .1, .5]}}); sections.forEach(section => observer.observe(section));
const dialog=document.getElementById('map-dialog'); const dialogImage=document.getElementById('map-dialog-image'); let mapOpener=null;
document.querySelectorAll('[data-map-open]').forEach(button=>button.addEventListener('click',()=>{{const image=button.querySelector('img'); if(!image) return; mapOpener=button; dialogImage.src=image.src; dialogImage.alt=image.alt; dialog.showModal();}}));
const closeMap=()=>{{if(dialog.open) dialog.close();}}; document.querySelector('[data-map-close]').addEventListener('click',closeMap); dialog.addEventListener('click',event=>{{if(event.target===dialog) closeMap();}}); dialog.addEventListener('keydown',event=>{{if(event.key === 'Escape') closeMap();}}); dialog.addEventListener('close',()=>{{if(mapOpener) mapOpener.focus(); mapOpener=null; dialogImage.removeAttribute('src'); dialogImage.alt='';}});
</script></body></html>\n'''


def html_document(manifest, session_files, visual_maps=None):
    """Compatibility wrapper kept for existing callers."""
    return render_html(manifest, session_files, visual_maps or {})
