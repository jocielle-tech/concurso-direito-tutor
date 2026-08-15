"""Build and publish the generated study-material tree."""

import os
import re
import tempfile
import unicodedata
from pathlib import Path


GENERATED_NOTICE = "<!-- GERADO AUTOMATICAMENTE. NÃO EDITE. -->\n\n"
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
QUESTION = re.compile(r"^###\s+Questão\s+\d+\s*$", re.MULTILINE)
HEADING_THREE = re.compile(r"^###\s+.+$", re.MULTILINE)
TOPIC = re.compile(r"^\s*[-*]\s+Tópico:\s*(\S.*?)\s*$", re.MULTILINE)


def slugify(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "item"


def ordered_segment(index, title):
    return f"{index:02d}-{slugify(title)}"


def canonical_session_relative_path(manifest, session):
    module_index = next(
        index for index, item in enumerate(manifest["modules"], 1) if item["id"] == session["module_id"]
    )
    module = manifest["modules"][module_index - 1]
    topic_id = session["topic_ids"][0]
    topic_index = next(index for index, item in enumerate(module["topics"], 1) if item["id"] == topic_id)
    topic = module["topics"][topic_index - 1]
    session_index = next(
        index for index, item in enumerate(manifest["sessions"], 1) if item["id"] == session["id"]
    )
    return (
        Path("modulos") / ordered_segment(module_index, module["title"]) / "topicos"
        / ordered_segment(topic_index, topic["title"]) / "sessoes"
        / f"{session_index:03d}-{slugify(session['title'])}.md"
    )


def _sections(text):
    headings = list(SECTION.finditer(text))
    return {
        heading.group(1): text[heading.end(): headings[index + 1].start() if index + 1 < len(headings) else len(text)].strip()
        for index, heading in enumerate(headings)
    }


def _question_blocks(text, topic_id):
    headings = list(HEADING_THREE.finditer(text))
    blocks = []
    for index, heading in enumerate(headings):
        if not QUESTION.fullmatch(heading.group(0)):
            continue
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        block = text[heading.start():end].strip()
        match = TOPIC.search(block)
        if match and match.group(1) == topic_id:
            blocks.append(block)
    return blocks


def _generated(title, parts):
    body = "\n\n".join(part.strip() for part in parts if part and part.strip())
    return f"{GENERATED_NOTICE}# {title}\n" + (f"\n{body}\n" if body else "\n")


def _topic_relative_path(module_index, module, topic_index, topic):
    return (
        Path("modulos") / ordered_segment(module_index, module["title"])
        / "topicos" / ordered_segment(topic_index, topic["title"])
    )


def _canonical_links_section(links, output_path):
    lines = []
    for title, canonical_path in links:
        relative = Path(os.path.relpath(canonical_path, start=output_path.parent)).as_posix()
        lines.append(f"- {title}: [Abrir sessão canônica]({relative})")
    return "## Sessões canônicas relacionadas\n\n" + "\n".join(lines)


def _progress(topics):
    total = sum(topic["weight"] for topic in topics)
    completed = sum(topic["weight"] for topic in topics if topic["status"] == "completed")
    return round(completed * 100 / total) if total else 0


def _review_details(session, text):
    if session["status"] != "completed":
        return "não definida", session["status"]
    sections = _sections(text)
    review = " ".join(sections.get("Próxima revisão", "").split()) or "não definida"
    match = re.search(r"^\s*[-*]\s+Prioridade:\s*(\S.*?)\s*$", text, re.MULTILINE)
    return review, match.group(1) if match else "não definida"


def build_output_bundle(trail, manifest, session_files, apostila_md, apostila_html, apostila_pdf=None):
    """Return all generated artifacts without writing any of them to disk."""
    del trail  # The interface accepts the trail for callers; all returned paths are relative.
    outputs = {
        Path("apostila/apostila.md"): (GENERATED_NOTICE + apostila_md).encode("utf-8"),
        Path("apostila/apostila.html"): apostila_html.encode("utf-8"),
    }
    if apostila_pdf is not None:
        outputs[Path("apostila/apostila.pdf")] = apostila_pdf

    panel_index, panel_progress = [], []
    all_summaries, all_maps, all_questions = [], [], []
    for module_index, module in enumerate(manifest["modules"], 1):
        module_root = Path("modulos") / ordered_segment(module_index, module["title"])
        panel_index.extend([
            f"## [{module['title']}](../{module_root.as_posix()}/)",
            "",
        ])
        for topic_index, topic in enumerate(module["topics"], 1):
            topic_root = _topic_relative_path(module_index, module, topic_index, topic)
            panel_index.append(f"- [{topic['title']}](../{(topic_root / 'resumo.md').as_posix()})")
            linked_sessions = [
                session for session in manifest["sessions"]
                if session["module_id"] == module["id"] and topic["id"] in session["topic_ids"]
            ]
            canonical_links, summaries, maps, questions = [], [], [], []
            for session in linked_sessions:
                canonical = canonical_session_relative_path(manifest, session)
                panel_index.append(f"- {module['title']} / {topic['title']}: [{session['title']}](../{canonical})")
                if session["topic_ids"][0] != topic["id"]:
                    canonical_links.append((session["title"], canonical))
                else:
                    outputs[canonical] = session_files[session["id"]].encode("utf-8")
                sections = _sections(session_files[session["id"]])
                summaries.append(f"## {session['title']}\n\n{sections.get('Resumo estratégico', 'Sem resumo registrado.')}")
                maps.append(f"## {session['title']}\n\n{sections.get('Mapa mental', 'Sem mapa mental registrado.')}")
                blocks = _question_blocks(sections.get("Questões e feedback", ""), topic["id"])
                if blocks:
                    questions.append(f"## {session['title']}\n\n" + "\n\n".join(blocks))
            material_summaries = list(summaries)
            material_maps = list(maps)
            material_questions = list(questions)
            if canonical_links:
                summaries.append(_canonical_links_section(canonical_links, topic_root / "resumo.md"))
                maps.append(_canonical_links_section(canonical_links, topic_root / "mapa-mental.md"))
                questions.append(_canonical_links_section(canonical_links, topic_root / "questoes.md"))
            outputs[topic_root / "resumo.md"] = _generated(f"Resumo — {topic['title']}", summaries).encode("utf-8")
            outputs[topic_root / "mapa-mental.md"] = _generated(f"Mapa mental — {topic['title']}", maps).encode("utf-8")
            outputs[topic_root / "questoes.md"] = _generated(f"Questões — {topic['title']}", questions).encode("utf-8")
            all_summaries.extend(material_summaries)
            all_maps.extend(material_maps)
            all_questions.extend(material_questions)
            if canonical_links:
                all_summaries.append(_canonical_links_section(canonical_links, Path("materiais/resumos.md")))
                all_maps.append(_canonical_links_section(canonical_links, Path("materiais/mapas-mentais.md")))
                all_questions.append(_canonical_links_section(canonical_links, Path("materiais/caderno-de-questoes.md")))

    panel_index.extend([
        "", "## Materiais consolidados", "",
        "- [Resumos](../materiais/resumos.md)",
        "- [Mapas mentais](../materiais/mapas-mentais.md)",
        "- [Caderno de questões](../materiais/caderno-de-questoes.md)",
    ])
    topics = [topic for module in manifest["modules"] for topic in module["topics"]]
    panel_progress.extend([f"Progresso global: {_progress(topics)}%", "", "## Por módulo", ""])
    panel_progress.extend(f"- {module['title']}: {_progress(module['topics'])}%" for module in manifest["modules"])
    panel_progress.extend(["", "## Por tópico", ""])
    panel_progress.extend(
        f"- {module['title']} / {topic['title']}: {_progress([topic])}%"
        for module in manifest["modules"] for topic in module["topics"]
    )
    review_agenda = []
    for session in manifest["sessions"]:
        review, priority = _review_details(session, session_files[session["id"]])
        review_agenda.append(
            f"- {session['title']} — Próxima revisão: {review}; Prioridade: {priority}."
        )

    outputs.update({
        Path("painel/indice.md"): _generated("Índice da trilha", panel_index).encode("utf-8"),
        Path("painel/progresso.md"): _generated("Progresso", panel_progress).encode("utf-8"),
        Path("painel/agenda-de-revisoes.md"): _generated("Agenda de revisões", review_agenda).encode("utf-8"),
        Path("revisoes/agenda.md"): _generated("Agenda de revisões", review_agenda).encode("utf-8"),
        Path("materiais/resumos.md"): _generated("Resumos", all_summaries).encode("utf-8"),
        Path("materiais/mapas-mentais.md"): _generated("Mapas mentais", all_maps).encode("utf-8"),
        Path("materiais/caderno-de-questoes.md"): _generated("Caderno de questões", all_questions).encode("utf-8"),
    })
    return outputs


def _target_path(trail, relative):
    relative = Path(relative)
    if relative.is_absolute():
        raise ValueError("caminho de saída deve ser relativo")
    target = (trail / relative).resolve()
    try:
        target.relative_to(trail.resolve())
    except ValueError as exc:
        raise ValueError("caminho de saída deve estar contido na trilha") from exc
    return target


def publish_bundle(trail, outputs, replace_file=lambda source, target: source.replace(target)):
    """Atomically replace a group of files, restoring all prior bytes on failure."""
    prepared, previous = {}, {}
    trail = Path(trail)
    try:
        for relative, content in outputs.items():
            target = _target_path(trail, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            previous[target] = target.read_bytes() if target.exists() else None
            handle = tempfile.NamedTemporaryFile(dir=target.parent, delete=False)
            with handle:
                handle.write(content)
            prepared[target] = Path(handle.name)
        for target, source in prepared.items():
            replace_file(source, target)
    except Exception:
        for target, content in previous.items():
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(content)
        raise
    finally:
        for source in prepared.values():
            source.unlink(missing_ok=True)
