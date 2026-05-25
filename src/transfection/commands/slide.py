from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from transfection.app import app
from transfection.services.slide import SlideOutputExistsError, format_mapping_lines, run_slide

NAME = "slide"
HELP = "Write slide.json from a compact slide mapping string."


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
    try:
        written_path, mapping = run_slide(sample=sample, output=output, force=force)
    except ValueError as error:
        typer.echo(f"Invalid --sample mapping: {error}", err=True)
        raise SystemExit(1) from None
    except SlideOutputExistsError as error:
        typer.echo(str(error), err=True)
        raise SystemExit(1) from None

    typer.echo(f"Wrote slide mapping: {written_path}")
    for line in format_mapping_lines(mapping):
        typer.echo(line)
