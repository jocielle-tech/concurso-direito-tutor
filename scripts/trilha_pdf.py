"""Deterministic ReportLab renderer for a polished trail study booklet."""

from __future__ import annotations

import io
import re
from html import escape as escape_markup


MAP_COLOURS = {
    "conceito": "#2563EB",
    "regra": "#16A34A",
    "excecao": "#D97706",
    "pegadinha": "#DC2626",
    "jurisprudencia": "#7C3AED",
}
MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
URL = re.compile(r"https?://[^\s<>()]+")
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
MAP_ITEM = re.compile(r"\s*[-*]\s+\[([^]]+)\]\s+(.+)")


class PdfDependencyError(RuntimeError):
    """Raised only when PDF output was requested without ReportLab."""


def load_reportlab():
    """Import ReportLab only when a PDF is actually being rendered."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
            Image,
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ModuleNotFoundError as exc:
        raise PdfDependencyError(
            "dependência PDF ausente; execute: python3 -m pip install -r requirements.txt"
        ) from exc
    return (
        colors, A4, getSampleStyleSheet, ParagraphStyle, mm, SimpleDocTemplate,
        Paragraph, Spacer, PageBreak, KeepTogether, Image, Table, TableStyle, HRFlowable,
    )


def _paragraph_markup(value):
    """Escape ReportLab markup, then restore only supported Markdown links."""
    def escaped_text_with_urls(text):
        pieces = []
        offset = 0
        for url in URL.finditer(text):
            pieces.append(escape_markup(text[offset:url.start()]))
            target = url.group(0)
            pieces.append(
                f'<link href="{escape_markup(target, quote=True)}" color="#1D4ED8">'
                f"{escape_markup(target)}</link>"
            )
            offset = url.end()
        pieces.append(escape_markup(text[offset:]))
        return "".join(pieces)

    parts = []
    position = 0
    for match in MARKDOWN_LINK.finditer(value):
        parts.append(escaped_text_with_urls(value[position:match.start()]))
        label, target = match.group(1), match.group(2).strip()
        escaped_label = escape_markup(label)
        if target.startswith(("https://", "http://", "mailto:")):
            parts.append(f'<link href="{escape_markup(target, quote=True)}" color="#1D4ED8">{escaped_label}</link>')
        else:
            parts.append(escaped_label)
        position = match.end()
    parts.append(escaped_text_with_urls(value[position:]))
    return "".join(parts)


def _anchor(name, label):
    return f'<a name="{escape_markup(name, quote=True)}"/>{_paragraph_markup(label)}'


def _session_sections(text):
    headings = list(SECTION.finditer(text))
    return {
        heading.group(1): text[heading.end():headings[index + 1].start() if index + 1 < len(headings) else len(text)].strip()
        for index, heading in enumerate(headings)
    }


def _question_groups(text):
    headings = list(re.finditer(r"^###\s+(.+?)\s*$", text, re.MULTILINE))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        question = re.fullmatch(r"Questão\s+\d+", heading.group(1))
        if question:
            lines = [line.strip() for line in text[heading.end():end].splitlines() if line.strip()]
            yield question.group(0), lines


def _trail_progress(manifest):
    topics = [topic for module in manifest["modules"] for topic in module["topics"]]
    total = sum(topic["weight"] for topic in topics)
    complete = sum(topic["weight"] for topic in topics if topic["status"] == "completed")
    return round(complete * 100 / total) if total else 0


def _metric_table(metrics, Table, TableStyle, Paragraph, styles, colors, mm):
    """Return a fixed-width, deterministic dashboard metric row for A4."""
    cells = [
        Paragraph(
            f'<b>{_paragraph_markup(value)}</b><br/>{_paragraph_markup(label)}',
            styles["MetricLabel"],
        )
        for label, value in metrics
    ]
    table = Table([cells], colWidths=[42 * mm] * len(cells), hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0EFFF")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7C4FF")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9D7FF")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def _algorithm_lines_from_sessions(manifest, session_files, topic_id):
    """Return completed-session map lines in manifest order for a single topic."""
    lines = []
    for session in manifest["sessions"]:
        if session["status"] != "completed" or topic_id not in session["topic_ids"]:
            continue
        source = _session_sections(session_files[session["id"]]).get("Mapa mental", "")
        lines.extend(line.strip() for line in source.splitlines() if line.strip())
    return tuple(lines)


def _map_line_style(line, ParagraphStyle, styles, colors, sequence):
    match = MAP_ITEM.match(line)
    category = match.group(1) if match else None
    text = match.group(2) if match else line
    color = MAP_COLOURS.get(category, "#64748B")
    style = ParagraphStyle(
        name=f"AlgorithmLine{sequence}", parent=styles["AlgorithmText"],
        leftIndent=6, borderPadding=5, borderWidth=0.8, borderColor=colors.HexColor(color),
    )
    return text, style


def _algorithm_fallback_flowables(lines, Paragraph, ParagraphStyle, styles, colors, sequence_start=0):
    flowables = [Paragraph("Fluxo textual verificável", styles["FallbackCaption"])]
    for offset, line in enumerate(lines):
        text, style = _map_line_style(line, ParagraphStyle, styles, colors, sequence_start + offset)
        flowables.append(Paragraph(_paragraph_markup(text), style))
    if not lines:
        flowables.append(Paragraph("Mapa algorítmico indisponível.", styles["AlgorithmText"]))
    return flowables


def _map_flowables(topic, asset, lines, Image, Paragraph, ParagraphStyle, KeepTogether, styles, colors, max_width, max_height):
    """Render a proportional PNG followed by authoritative searchable algorithm text."""
    flowables = [Paragraph("Mapa algorítmico", styles["SectionLabel"])]
    has_ready_image = bool(asset and asset.status == "ready" and asset.png_bytes)
    if has_ready_image:
        try:
            # Eager decoding keeps malformed cache entries local to this map instead
            # of allowing ReportLab to fail later while building the whole document.
            image = Image(io.BytesIO(asset.png_bytes), lazy=0)
            image._img.getRGBData()
            image._restrictSize(max_width, max_height)
        except (OSError, TypeError, ValueError):
            has_ready_image = False
        else:
            flowables.append(KeepTogether([image]))
    if not has_ready_image:
        flowables.extend(_algorithm_fallback_flowables(lines, Paragraph, ParagraphStyle, styles, colors, len(flowables)))
    if has_ready_image:
        flowables.append(Paragraph("Fluxo textual verificável", styles["FallbackCaption"]))
        for offset, line in enumerate(lines):
            text, style = _map_line_style(line, ParagraphStyle, styles, colors, 1000 + offset)
            flowables.append(Paragraph(_paragraph_markup(text), style))
    return flowables


def render_pdf(manifest, session_files, visual_maps=None):
    """Return a stable A4 PDF byte string for already-validated trail content."""
    try:
        (
            colors, A4, get_sample_styles, ParagraphStyle, mm, SimpleDocTemplate,
            Paragraph, Spacer, PageBreak, KeepTogether, Image, Table, TableStyle, HRFlowable,
        ) = load_reportlab()
    except ModuleNotFoundError as exc:
        raise PdfDependencyError(
            "dependência PDF ausente; execute: python3 -m pip install -r requirements.txt"
        ) from exc
    visual_maps = visual_maps or {}

    styles = get_sample_styles()
    styles.add(ParagraphStyle(
        name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=27, leading=32, textColor=colors.white, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="CoverSubtitle", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=10.5, leading=15, textColor=colors.HexColor("#E0E7FF"), spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Eyebrow", parent=styles["BodyText"], fontName="Helvetica-Bold",
        fontSize=8, leading=10, textColor=colors.HexColor("#C7D2FE"), spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="MetricLabel", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7.6, leading=10, textColor=colors.HexColor("#475467"), alignment=1,
    ))
    styles.add(ParagraphStyle(
        name="TrailHeading", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=18, leading=23, textColor=colors.HexColor("#312E81"), spaceBefore=8, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="TopicHeading", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=14, leading=18, textColor=colors.HexColor("#0F172A"), spaceBefore=13, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="SessionHeading", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=11.2, leading=14, textColor=colors.HexColor("#3730A3"), spaceBefore=10, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="TrailBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2,
        leading=13, textColor=colors.HexColor("#1F2937"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="SectionLabel", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.4,
        leading=13, textColor=colors.HexColor("#1D4ED8"), spaceBefore=8, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="QuestionTitle", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10.5,
        leading=13, textColor=colors.HexColor("#6D28D9"), spaceBefore=8, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="FeedbackText", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.8,
        leading=12.2, textColor=colors.HexColor("#334155"), spaceAfter=0,
    ))
    styles.add(ParagraphStyle(
        name="AlgorithmText", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.8,
        leading=12, textColor=colors.HexColor("#1E293B"), spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="FallbackCaption", parent=styles["BodyText"], fontName="Helvetica-Oblique", fontSize=8,
        leading=10, textColor=colors.HexColor("#64748B"), spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="IndexHeading", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19,
        leading=24, textColor=colors.HexColor("#312E81"), spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="IndexModule", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10,
        leading=14, textColor=colors.HexColor("#1E293B"), spaceBefore=5, spaceAfter=2, keepWithNext=1,
    ))
    styles.add(ParagraphStyle(
        name="IndexTopic", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.3,
        leading=13, textColor=colors.HexColor("#1E3A8A"), leftIndent=8, spaceAfter=1,
    ))
    class StableBooklet(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            bookmark = getattr(flowable, "bookmark_name", None)
            if bookmark:
                self.canv.bookmarkPage(bookmark)
                self.canv.addOutlineEntry(flowable.outline_title, bookmark, flowable.outline_level, False)

    def heading(text, style_name, bookmark=None, level=0):
        item = Paragraph(_anchor(bookmark, text) if bookmark else _paragraph_markup(text), styles[style_name])
        if bookmark:
            item.bookmark_name = bookmark
            item.outline_title = text
            item.outline_level = level
        return item

    topic_count = sum(len(module["topics"]) for module in manifest["modules"])
    completed_topics = sum(
        topic["status"] == "completed" for module in manifest["modules"] for topic in module["topics"]
    )
    completed_sessions = sum(session["status"] == "completed" for session in manifest["sessions"])
    question_count = sum(
        sum(1 for _ in _question_groups(_session_sections(session_files[session["id"]]).get("Questões e feedback", "")))
        for session in manifest["sessions"] if session["status"] == "completed"
    )
    metrics = (
        ("Progresso global", f"{_trail_progress(manifest)}%"),
        ("Tópicos concluídos", f"{completed_topics}/{topic_count}"),
        ("Sessões concluídas", f"{completed_sessions}/{len(manifest['sessions'])}"),
        ("Questões corrigidas", str(question_count)),
    )

    def on_first_page(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setFillColor(colors.HexColor("#312E81"))
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#2563EB"))
        canvas.rect(0, height - 44 * mm, width, 44 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#7C3AED"))
        canvas.rect(0, 0, width, 18 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#E0E7FF"))
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(width - document.rightMargin, 10 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    def on_later_page(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(colors.HexColor("#C7D2FE"))
        canvas.setLineWidth(1)
        canvas.line(document.leftMargin, height - 13 * mm, width - document.rightMargin, height - 13 * mm)
        canvas.setStrokeColor(colors.HexColor("#38BDF8"))
        canvas.line(document.leftMargin, height - 14.5 * mm, document.leftMargin + 36 * mm, height - 14.5 * mm)
        canvas.setFont("Helvetica", 7.8)
        canvas.setFillColor(colors.HexColor("#475467"))
        canvas.drawString(document.leftMargin, height - 10 * mm, manifest["title"])
        canvas.setFillColor(colors.HexColor("#312E81"))
        canvas.roundRect(width - document.rightMargin - 25 * mm, 7 * mm, 25 * mm, 8 * mm, 4 * mm, fill=0, stroke=1)
        canvas.drawCentredString(width - document.rightMargin - 12.5 * mm, 10 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    stream = io.BytesIO()
    document = StableBooklet(
        stream, pagesize=A4, title=manifest["title"], author="Tutor de Concursos de Direito",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
    )
    story = [
        Spacer(1, 39 * mm),
        Paragraph("APOSTILA DE ESTUDO", styles["Eyebrow"]),
        Paragraph(_paragraph_markup(manifest["title"]), styles["CoverTitle"]),
        Paragraph("Trilha organizada, revisável e pronta para estudo dirigido.", styles["CoverSubtitle"]),
        Spacer(1, 15 * mm),
        _metric_table(metrics, Table, TableStyle, Paragraph, styles, colors, mm),
        PageBreak(),
        Paragraph("Índice da trilha", styles["IndexHeading"]),
    ]
    for module in manifest["modules"]:
        story.append(Paragraph(
            f'<link href="#module-{escape_markup(module["id"], quote=True)}">{_paragraph_markup(module["title"])}</link>',
            styles["IndexModule"],
        ))
        for topic in module["topics"]:
            story.append(Paragraph(
                f'&nbsp;&nbsp;&nbsp;<link href="#topic-{escape_markup(topic["id"], quote=True)}">{_paragraph_markup(topic["title"])}</link>',
                styles["IndexTopic"],
            ))
    story.append(PageBreak())

    for module_index, module in enumerate(manifest["modules"]):
        if module_index:
            story.append(PageBreak())
        story.append(heading(module["title"], "TrailHeading", f"module-{module['id']}", 0))
        story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#C7D2FE"), spaceAfter=5))
        for topic in module["topics"]:
            story.append(heading(topic["title"], "TopicHeading", f"topic-{topic['id']}", 1))
            asset = visual_maps.get(topic["id"])
            lines = tuple(asset.spec.algorithm_lines) if asset else _algorithm_lines_from_sessions(
                manifest, session_files, topic["id"]
            )
            if lines or asset or topic["status"] == "completed":
                story.extend(_map_flowables(
                    topic, asset, lines, Image, Paragraph, ParagraphStyle, KeepTogether, styles, colors,
                    document.width, 108 * mm,
                ))
            for session in (
                item for item in manifest["sessions"]
                if item["module_id"] == module["id"] and item["topic_ids"][0] == topic["id"]
            ):
                story.append(heading(session["title"], "SessionHeading", f"session-{session['id']}", 2))
                sections = _session_sections(session_files[session["id"]])
                for section_name in ("Conteúdo principal", "Resumo estratégico"):
                    section = sections.get(section_name)
                    if section:
                        story.append(Paragraph(_paragraph_markup(section_name), styles["SectionLabel"]))
                        for line in section.splitlines():
                            if line.strip():
                                story.append(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]))
                questions = sections.get("Questões e feedback", "")
                if questions:
                    story.append(Paragraph("Questões e feedback", styles["SectionLabel"]))
                    for question, lines in _question_groups(questions):
                        first_lines, remaining = lines[:2], lines[2:]
                        intro = [Paragraph(_paragraph_markup(question), styles["QuestionTitle"])]
                        intro.extend(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]) for line in first_lines)
                        story.append(KeepTogether(intro))
                        if remaining:
                            feedback = "<br/>".join(_paragraph_markup(line.lstrip("-* ").strip()) for line in remaining)
                            card = Table([[Paragraph(feedback, styles["FeedbackText"])]], colWidths=[document.width])
                            card.setStyle(TableStyle([
                                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#DDD6FE")),
                                ("LINEBEFORE", (0, 0), (0, -1), 2.5, colors.HexColor("#8B5CF6")),
                                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 6),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ]))
                            story.append(card)
                            story.append(Spacer(1, 2 * mm))
                    diagnosis = re.search(r"^###\s+Diagnóstico agregado\s*$([\s\S]*)", questions, re.MULTILINE)
                    if diagnosis:
                        story.append(Paragraph("Diagnóstico agregado", styles["SectionLabel"]))
                        for line in diagnosis.group(1).splitlines():
                            if line.strip():
                                story.append(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]))
                sources = sections.get("Fontes")
                if sources:
                    story.append(Paragraph("Fontes", styles["SectionLabel"]))
                    for line in sources.splitlines():
                        if line.strip():
                            story.append(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]))

    def stable_canvas(filename, **kwargs):
        from reportlab.pdfgen.canvas import Canvas
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 1
        return Canvas(filename, **kwargs)

    document.build(story, onFirstPage=on_first_page, onLaterPages=on_later_page, canvasmaker=stable_canvas)
    return stream.getvalue()
