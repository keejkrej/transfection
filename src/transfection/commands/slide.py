"""Slide mapping command implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection.app import app
from transfection.core import (
    SlideMapping,
    parse_slide_mapping_spec,
    write_slide_mapping,
)

NAME = "slide"
HELP = "Write slide.json from a compact slide mapping string."


def _print_mapping(mapping: SlideMapping) -> None:
    for slide_channel in sorted(mapping):
        entry = mapping[slide_channel]
        positions = ", ".join(str(pos) for pos in entry.positions)
        typer.echo(
            f"  slide_channel={slide_channel} sample_name={entry.sample_name!r} "
            f"signal_channel={entry.signal_channel} mask_channel={entry.mask_channel} positions={positions}"
        )


@app.command(NAME, help=HELP)
def slide(
    sample: Annotated[
        str,
        typer.Option(
            "--sample",
            help=(
                'Pipe-separated segments "positions@signal_channel/mask_channel#sample_name" in entry order '
                "(slide_channel keys in slide.json are 0, 1, 2, ...). "
                "Use signal_channel for intensity and mask_channel for segmentation. "
                'Example: --sample "10,11@2/0#condA|20@1/0#condB". Positions use commas and slices; '
                "each segment requires #sample_name."
            ),
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            file_okay=True,
            dir_okay=False,
            help="Path for the slide.json file to write.",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite the output file if it already exists.",
        ),
    ] = False,
) -> None:
    output_path = output.expanduser().resolve()

    try:
        mapping = parse_slide_mapping_spec(sample)
    except ValueError as error:
        typer.echo(f"Invalid --sample mapping: {error}", err=True)
        raise SystemExit(1) from None

    if output_path.exists() and not force:
        typer.echo(f"{output_path} already exists. Pass --force to overwrite.", err=True)
        raise SystemExit(1)

    written_path = write_slide_mapping(mapping, output_path)
    typer.echo(f"Wrote slide mapping: {written_path}")
    _print_mapping(mapping)
