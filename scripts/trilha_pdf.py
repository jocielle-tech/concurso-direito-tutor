"""Deterministic ReportLab renderer for a trail study booklet."""

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


class PdfDependencyError(RuntimeError):
    """Raised only when PDF output was requested without ReportLab."""


def load_reportlab():
    """Import ReportLab only when a PDF is actually being rendered."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer
    except ModuleNotFoundError as exc:
        raise PdfDependencyError(
            "dependência PDF ausente; execute: python3 -m pip install -r requirements.txt"
        ) from exc
    return colors, A4, getSampleStyleSheet, ParagraphStyle, mm, SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether


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
    headings = list(re.finditer(r"^##\s+(.+?)\s*$", text, re.MULTILINE))
    sections = {}
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections[heading.group(1)] = text[heading.end():end].strip()
    return sections


def _question_groups(text):
    headings = list(re.finditer(r"^###\s+(.+?)\s*$", text, re.MULTILINE))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        question = re.fullmatch(r"Questão\s+\d+", heading.group(1))
        if not question:
            continue
        lines = [line.strip() for line in text[heading.end():end].splitlines() if line.strip()]
        yield question.group(0), lines


def render_pdf(manifest, session_files):
    """Return a stable PDF byte string for already-validated trail content."""
    try:
        (
            colors, A4, get_sample_styles, ParagraphStyle, mm,
            SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether,
        ) = load_reportlab()
    except ModuleNotFoundError as exc:
        raise PdfDependencyError(
            "dependência PDF ausente; execute: python3 -m pip install -r requirements.txt"
        ) from exc

    styles = get_sample_styles()
    styles.add(ParagraphStyle(
        name="TrailTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=26, leading=32, textColor=colors.HexColor("#111827"), spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name="TrailHeading", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=17, leading=22, textColor=colors.HexColor("#1D4ED8"), spaceBefore=8, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="TrailSubheading", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=colors.HexColor("#111827"), spaceBefore=8, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="TrailBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5,
        leading=13, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="TrailQuestion", parent=styles["Heading3"], fontName="Helvetica-Bold",
        fontSize=11, leading=14, textColor=colors.HexColor("#7C3AED"), spaceBefore=7, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="TrailMap", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5,
        leading=13, leftIndent=7, borderPadding=6, spaceAfter=5,
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

    def on_page(canvas, document):
        canvas.saveState()
        width, height = A4
        canvas.setStrokeColor(colors.HexColor("#D1D5DB"))
        canvas.line(document.leftMargin, height - 13 * mm, width - document.rightMargin, height - 13 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#4B5563"))
        canvas.drawString(document.leftMargin, height - 10 * mm, manifest["title"])
        canvas.drawRightString(width - document.rightMargin, 10 * mm, f"Página {canvas.getPageNumber()}")
        canvas.restoreState()

    stream = io.BytesIO()
    document = StableBooklet(
        stream, pagesize=A4, title=manifest["title"], author="Tutor de Concursos de Direito",
        leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
    )
    story = [
        Spacer(1, 42 * mm),
        Paragraph(_paragraph_markup(manifest["title"]), styles["TrailTitle"]),
        Paragraph("Apostila de estudo - material gerado automaticamente", styles["TrailBody"]),
        Spacer(1, 10 * mm),
        Paragraph("Índice", styles["TrailHeading"]),
    ]
    for module in manifest["modules"]:
        story.append(Paragraph(
            f'<link href="#module-{escape_markup(module["id"], quote=True)}">{_paragraph_markup(module["title"])}</link>',
            styles["TrailBody"],
        ))
        for topic in module["topics"]:
            story.append(Paragraph(
                f'&nbsp;&nbsp;&nbsp;<link href="#topic-{escape_markup(topic["id"], quote=True)}">{_paragraph_markup(topic["title"])}</link>',
                styles["TrailBody"],
            ))
    story.append(PageBreak())

    for module_index, module in enumerate(manifest["modules"]):
        if module_index:
            story.append(PageBreak())
        story.append(heading(module["title"], "TrailHeading", f"module-{module['id']}", 0))
        for topic in module["topics"]:
            story.append(heading(topic["title"], "TrailSubheading", f"topic-{topic['id']}", 1))
            for session in (
                item for item in manifest["sessions"]
                if item["module_id"] == module["id"] and item["topic_ids"][0] == topic["id"]
            ):
                session_anchor = f"session-{session['id']}"
                story.append(heading(session["title"], "TrailSubheading", session_anchor, 2))
                sections = _session_sections(session_files[session["id"]])
                for section_name in ("Conteúdo principal", "Resumo estratégico"):
                    section = sections.get(section_name)
                    if section:
                        story.append(Paragraph(_paragraph_markup(section_name), styles["TrailQuestion"]))
                        for line in section.splitlines():
                            if line.strip():
                                story.append(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]))
                mind_map = sections.get("Mapa mental")
                if mind_map:
                    story.append(Paragraph("Mapa mental", styles["TrailQuestion"]))
                    for line in mind_map.splitlines():
                        match = re.match(r"\s*[-*]\s+\[([^]]+)\]\s+(.+)", line)
                        if not match:
                            continue
                        category, content = match.groups()
                        map_style = ParagraphStyle(
                            name=f"TrailMap{len(story)}", parent=styles["TrailMap"],
                            borderColor=colors.HexColor(MAP_COLOURS.get(category, "#6B7280")), borderWidth=1,
                        )
                        story.append(Paragraph(_paragraph_markup(content), map_style))
                questions = sections.get("Questões e feedback", "")
                if questions:
                    story.append(Paragraph("Questões e feedback", styles["TrailQuestion"]))
                    for question, lines in _question_groups(questions):
                        first_lines, remaining = lines[:2], lines[2:]
                        block = [Paragraph(_paragraph_markup(question), styles["TrailQuestion"])]
                        block.extend(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]) for line in first_lines)
                        story.append(KeepTogether(block))
                        story.extend(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]) for line in remaining)
                    diagnosis = re.search(r"^###\s+Diagnóstico agregado\s*$([\s\S]*)", questions, re.MULTILINE)
                    if diagnosis:
                        story.append(Paragraph("Diagnóstico agregado", styles["TrailQuestion"]))
                        for line in diagnosis.group(1).splitlines():
                            if line.strip():
                                story.append(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]))
                sources = sections.get("Fontes")
                if sources:
                    story.append(Paragraph("Fontes", styles["TrailQuestion"]))
                    for line in sources.splitlines():
                        if line.strip():
                            story.append(Paragraph(_paragraph_markup(line.lstrip("-* ").strip()), styles["TrailBody"]))

    def stable_canvas(filename, **kwargs):
        from reportlab.pdfgen.canvas import Canvas
        kwargs["invariant"] = 1
        kwargs["pageCompression"] = 1
        return Canvas(filename, **kwargs)

    document.build(story, onFirstPage=on_page, onLaterPages=on_page, canvasmaker=stable_canvas)
    return stream.getvalue()
