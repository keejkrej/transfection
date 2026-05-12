"""Slide mapping command implementation."""

from __future__ import annotations

import sys
from pathlib import Path

from transfection.core import (
    SlideMapping,
    parse_slide_mapping_spec,
    write_slide_mapping,
)

NAME = "slide"
HELP = "Write slide.json from a compact slide mapping string."


def run_command(sample: str, output: Path, force: bool = False) -> None:
    output_path = output.expanduser().resolve()

    try:
        mapping = parse_slide_mapping_spec(sample)
    except ValueError as error:
        print(f"Invalid --sample mapping: {error}", file=sys.stderr)
        raise SystemExit(1) from None

    if output_path.exists() and not force:
        print(f"{output_path} already exists. Pass --force to overwrite.", file=sys.stderr)
        raise SystemExit(1)

    written_path = write_slide_mapping(mapping, output_path)
    print(f"Wrote slide mapping: {written_path}")
    _print_mapping(mapping)


def _print_mapping(mapping: SlideMapping) -> None:
    for slide_channel in sorted(mapping):
        entry = mapping[slide_channel]
        positions = ", ".join(str(pos) for pos in entry.positions)
        print(
            f"  slide_channel={slide_channel} sample_name={entry.sample_name!r} "
            f"image_channel={entry.image_channel} positions={positions}"
        )
