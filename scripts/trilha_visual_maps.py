"""Deterministic specifications and cache validation for visual topic maps."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import unicodedata
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


VISUAL_TEMPLATE_VERSION = "dashboard-modern-v2"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
MAX_PNG_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_PNG_DECOMPRESSED_BYTES = 64 * 1024 * 1024
VALID_PNG_FORMATS = {
    0: {1, 2, 4, 8, 16},
    2: {8, 16},
    3: {1, 2, 4, 8},
    4: {8, 16},
    6: {8, 16},
}


@dataclass(frozen=True)
class VisualMapSpec:
    topic_id: str
    source_hash: str
    expected_path: Path
    prompt: str
    alt_text: str
    algorithm_lines: tuple[str, ...]


@dataclass(frozen=True)
class VisualMapAsset:
    spec: VisualMapSpec
    status: Literal["ready", "missing", "invalid"]
    png_bytes: bytes | None
    error: str | None


def _sections(text):
    headings = list(SECTION.finditer(text))
    return {
        heading.group(1): text[
            heading.end(): headings[index + 1].start() if index + 1 < len(headings) else len(text)
        ].strip()
        for index, heading in enumerate(headings)
    }


def _safe_segment(value):
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-") or "topico"
    return f"{slug}-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]}"


def _algorithm_source(manifest, session_files, topic_id):
    blocks = []
    for session in manifest["sessions"]:
        if session["status"] != "completed" or topic_id not in session["topic_ids"]:
            continue
        mind_map = _sections(session_files[session["id"]]).get("Mapa mental", "").strip()
        if mind_map:
            blocks.append(mind_map)
    return "\n\n".join(blocks)


def _visual_prompt(lines):
    verbatim = "\n".join(lines)
    return (
        "Use case: infographic-diagram\n"
        "Asset type: complementary algorithmic study diagram for a Portuguese law handout.\n"
        "Primary request: render exactly one hierarchical decision flow from the supplied Markdown.\n"
        "Composition/framing: horizontal 3:2, designed for 1536×1024, generous safe margins, "
        "clear parent-child connectors only according to Markdown indentation. siblings have no arrows, "
        "especially RESULTADO and ALERTA siblings.\n"
        "Style/medium: Dashboard Moderno infographic-diagram, polished flat vector-like cards, no radial map.\n"
        "Color palette: semantic violet/blue dashboard base; ENTRADA blue, SE/ENTÃO green, "
        "SENÃO amber, RESULTADO violet, ALERTA red; high contrast on a clean light background.\n"
        "Constraints: preserve every supplied label verbatim, including indentation topology; short readable "
        "Portuguese text; no topic title or headline inside the image.\n"
        "Avoid: logos, watermark, brand marks, articles, precedents, citations, extra legal text, invented text, "
        "decorative arrows between siblings, or any content not supplied below.\n"
        "Text (verbatim):\n"
        f"{verbatim}"
    )


def build_visual_map_specs(manifest, session_files):
    """Build content-addressed specifications for completed topics with a textual map."""
    specs = {}
    for module in manifest["modules"]:
        for topic in module["topics"]:
            if topic["status"] != "completed":
                continue
            source = _algorithm_source(manifest, session_files, topic["id"])
            if not source:
                continue
            normalized = "\n".join(line.rstrip() for line in source.splitlines()).strip()
            digest_input = json.dumps(
                {
                    "topic_id": topic["id"],
                    "template": VISUAL_TEMPLATE_VERSION,
                    "ratio": "3:2",
                    "source": normalized,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            source_hash = hashlib.sha256(digest_input).hexdigest()
            expected = Path("assets/mapas") / _safe_segment(topic["id"]) / f"{source_hash}.png"
            prompt_lines = tuple(line for line in normalized.splitlines() if line.strip())
            lines = tuple(line.strip() for line in prompt_lines)
            specs[topic["id"]] = VisualMapSpec(
                topic_id=topic["id"],
                source_hash=source_hash,
                expected_path=expected,
                prompt=_visual_prompt(prompt_lines),
                alt_text=f"Fluxograma algorítmico do tópico {topic['title']}. " + " ".join(lines),
                algorithm_lines=lines,
            )
    return specs


def _contained_path(trail, expected_path):
    trail_root = Path(trail).resolve()
    expected = Path(expected_path)
    if expected.is_absolute():
        raise ValueError("caminho do mapa deve ser relativo e contido na trilha")
    candidate = (trail_root / expected).resolve()
    try:
        candidate.relative_to(trail_root)
    except ValueError as exc:
        raise ValueError("caminho do mapa deve estar contido na trilha") from exc
    return candidate


def _scanline_layout(width, height, bits_per_pixel, interlace):
    if interlace == 0:
        passes = ((0, 0, 1, 1),)
    else:
        passes = (
            (0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4),
            (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2),
        )
    for x_start, y_start, x_step, y_step in passes:
        pass_width = 0 if width <= x_start else (width - x_start + x_step - 1) // x_step
        pass_height = 0 if height <= y_start else (height - y_start + y_step - 1) // y_step
        if pass_width and pass_height:
            yield pass_height, (pass_width * bits_per_pixel + 7) // 8


def _validate_png_scanlines(idat, width, height, bit_depth, color_type, interlace):
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    expected = sum(rows * (row_bytes + 1) for rows, row_bytes in _scanline_layout(
        width, height, channels * bit_depth, interlace
    ))
    if expected > MAX_PNG_DECOMPRESSED_BYTES:
        raise ValueError("dados de imagem PNG excedem o limite seguro")
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(idat, expected + 1)
        raw += decoder.flush()
    except zlib.error as exc:
        raise ValueError("dados de imagem PNG comprimidos inválidos") from exc
    if len(raw) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("dados de imagem PNG truncados ou excedentes")
    offset = 0
    for rows, row_bytes in _scanline_layout(width, height, channels * bit_depth, interlace):
        for _ in range(rows):
            if raw[offset] > 4:
                raise ValueError("filtro de scanline PNG inválido")
            offset += row_bytes + 1


def _png_dimensions(content):
    if not content.startswith(PNG_SIGNATURE):
        raise ValueError("assinatura PNG inválida")
    position = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    image_data_state = "before_idat"
    found_iend = found_palette = False
    idat = bytearray()
    while position < len(content):
        if position + 12 > len(content):
            raise ValueError("chunk PNG truncado")
        length = struct.unpack(">I", content[position:position + 4])[0]
        chunk_end = position + 12 + length
        if chunk_end > len(content):
            raise ValueError("chunk PNG truncado")
        kind = content[position + 4:position + 8]
        payload = content[position + 8:position + 8 + length]
        stored_crc = struct.unpack(">I", content[position + 8 + length:chunk_end])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != stored_crc:
            raise ValueError("CRC PNG inválido")
        if position == len(PNG_SIGNATURE):
            if kind != b"IHDR" or length != 13:
                raise ValueError("cabeçalho IHDR PNG inválido")
            width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if (color_type not in VALID_PNG_FORMATS or bit_depth not in VALID_PNG_FORMATS[color_type]):
                raise ValueError("combinação de bit-depth e color-type PNG inválida")
            if compression != 0 or filter_method != 0 or interlace not in {0, 1}:
                raise ValueError("método PNG não suportado")
        elif kind == b"IHDR":
            raise ValueError("chunk IHDR PNG duplicado")
        elif kind == b"IDAT":
            if length == 0:
                raise ValueError("chunk IDAT PNG vazio")
            if image_data_state == "after_idat":
                raise ValueError("chunks IDAT PNG devem ser consecutivos")
            if len(idat) + length > MAX_PNG_COMPRESSED_BYTES:
                raise ValueError("dados de imagem PNG excedem o limite seguro")
            idat.extend(payload)
            image_data_state = "in_idat"
        elif kind == b"PLTE":
            if image_data_state != "before_idat" or found_palette:
                raise ValueError("chunk PLTE PNG fora de ordem")
            if color_type in {0, 4} or length == 0 or length % 3 or length > 768:
                raise ValueError("palette PNG inválida")
            if color_type == 3 and length // 3 > 2 ** bit_depth:
                raise ValueError("palette PNG excede o bit-depth")
            found_palette = True
        elif kind == b"IEND":
            if (
                length != 0
                or chunk_end != len(content)
                or image_data_state not in {"in_idat", "after_idat"}
            ):
                raise ValueError("chunk IEND PNG inválido")
            found_iend = True
            break
        else:
            if not kind[0] & 0x20:
                raise ValueError("chunk PNG crítico desconhecido")
            if image_data_state == "in_idat":
                image_data_state = "after_idat"
        position = chunk_end
    if width is None or height is None:
        raise ValueError("cabeçalho IHDR PNG inválido")
    if width == 0 or height == 0:
        raise ValueError("dimensões PNG inválidas")
    if image_data_state == "before_idat":
        raise ValueError("chunk IDAT PNG ausente")
    if not found_iend:
        raise ValueError("chunk IEND PNG ausente")
    if color_type == 3 and not found_palette:
        raise ValueError("palette PNG obrigatória para color-type indexado")
    _validate_png_scanlines(bytes(idat), width, height, bit_depth, color_type, interlace)
    return width, height


def load_visual_map_assets(trail, specs):
    """Load only cache entries that are safe, readable landscape PNG files."""
    assets = {}
    for topic_id, spec in specs.items():
        try:
            target = _contained_path(trail, spec.expected_path)
        except ValueError as exc:
            assets[topic_id] = VisualMapAsset(spec, "invalid", None, str(exc))
            continue
        if not target.is_file():
            assets[topic_id] = VisualMapAsset(spec, "missing", None, None)
            continue
        try:
            content = target.read_bytes()
            width, height = _png_dimensions(content)
            if width < 640 or height < 640:
                raise ValueError("imagem PNG deve ter pelo menos 640 px em cada dimensão")
            ratio = width / height
            if not 1.4 <= ratio <= 1.6:
                raise ValueError("proporção PNG deve ficar entre 1,4 e 1,6")
            if width <= height:
                raise ValueError("imagem PNG deve estar em orientação paisagem")
        except (OSError, ValueError) as exc:
            assets[topic_id] = VisualMapAsset(spec, "invalid", None, str(exc))
        else:
            assets[topic_id] = VisualMapAsset(spec, "ready", content, None)
    return assets
