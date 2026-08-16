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


VISUAL_TEMPLATE_VERSION = "dashboard-modern-v1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SECTION = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


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


def _visual_prompt(topic_title, lines):
    verbatim = "\n".join(lines)
    return (
        "Use case: infographic-diagram\n"
        "Create one polished Portuguese algorithmic mind-map infographic for a law-study handout.\n"
        f"Topic: {topic_title}\n"
        "Target: landscape 3:2, approximately 1536×1024, modern academic dashboard style.\n"
        "Use clear directional flow, concise readable labels, and accessible color contrast. "
        "Do not invent legal content or alter the supplied wording.\n"
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
            lines = tuple(line.strip() for line in normalized.splitlines() if line.strip())
            specs[topic["id"]] = VisualMapSpec(
                topic_id=topic["id"],
                source_hash=source_hash,
                expected_path=expected,
                prompt=_visual_prompt(topic["title"], lines),
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


def _png_dimensions(content):
    if not content.startswith(PNG_SIGNATURE):
        raise ValueError("assinatura PNG inválida")
    position = len(PNG_SIGNATURE)
    width = height = None
    image_data_state = "before_idat"
    found_iend = found_palette = False
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
            width, height = struct.unpack(">II", payload[:8])
        elif kind == b"IHDR":
            raise ValueError("chunk IHDR PNG duplicado")
        elif kind == b"IDAT":
            if length == 0:
                raise ValueError("chunk IDAT PNG vazio")
            if image_data_state == "after_idat":
                raise ValueError("chunks IDAT PNG devem ser consecutivos")
            image_data_state = "in_idat"
        elif kind == b"PLTE":
            if image_data_state != "before_idat" or found_palette:
                raise ValueError("chunk PLTE PNG fora de ordem")
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
