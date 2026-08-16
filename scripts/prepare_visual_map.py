#!/usr/bin/env python3
"""Emit a read-only native-image request for one completed visual map."""

import argparse
import json
from pathlib import Path

try:
    from scripts.build_trilha import ValidationError, load_and_validate
    from scripts.trilha_visual_maps import build_visual_map_specs, load_visual_map_assets
except ModuleNotFoundError:
    from build_trilha import ValidationError, load_and_validate
    from trilha_visual_maps import build_visual_map_specs, load_visual_map_assets


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("trail", type=Path)
    parser.add_argument("--topic", required=True)
    args = parser.parse_args(argv)
    try:
        trail = args.trail.resolve()
        manifest, session_files = load_and_validate(trail)
        specs = build_visual_map_specs(manifest, session_files)
        if args.topic not in specs:
            raise ValidationError("tópico não concluído ou sem mapa mental")
        spec = specs[args.topic]
        asset = load_visual_map_assets(trail, {args.topic: spec})[args.topic]
        print(json.dumps({
            "generator": "imagegen-built-in",
            "topic_id": spec.topic_id,
            "source_hash": spec.source_hash,
            "expected_path": spec.expected_path.as_posix(),
            "prompt": spec.prompt,
            "alt_text": spec.alt_text,
            "status": asset.status,
            "error": asset.error,
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
